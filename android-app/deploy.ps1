<#
.SYNOPSIS
    Compila, instala y habilita el control del celular en un solo comando,
    después de correr setup-android-sdk.ps1 una vez y conectar el celular por
    USB con depuración habilitada.

.DESCRIPTION
    Hace, en cadena:
      1. Chequea que haya exactamente un celular conectado y autorizado (adb).
      2. Compila el debug APK (gradlew.bat assembleDebug).
      3. Lo instala vía adb (no hace falta habilitar "orígenes desconocidos",
         adb install no pasa por ahí).
      4. Habilita el Accessibility Service de Jarvis por `adb shell settings`,
         sin tocar otros servicios de accesibilidad que el usuario ya tuviera
         prendidos (TalkBack, etc.) — lee la lista actual y le agrega el
         nuestro en vez de pisarla.

    Lo único que sigue siendo manual e inevitable: conectar el cable y aceptar
    el popup "Permitir depuración USB" en la pantalla del celular (medida de
    seguridad de Android, no se puede saltear). Y, la primera vez que abras la
    app, cargar la URL del backend + API key en Configuración — esos datos
    viven en el almacenamiento privado de la app y no son seteables por adb.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageId = "com.jarvisremote.app"
$AccessibilityServiceId = "$PackageId/$PackageId.phone.JarvisAccessibilityService"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Get-Adb {
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $fallback = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
    if (Test-Path $fallback) { return $fallback }
    throw "No encontré 'adb'. Corré .\setup-android-sdk.ps1 primero (o abrí una terminal nueva si ya lo corriste)."
}

$adb = Get-Adb

# --- 1. Chequear celular conectado --------------------------------------
Write-Step "Buscando celular conectado"
$devicesOutput = & $adb devices | Select-Object -Skip 1 | Where-Object { $_.Trim() -ne "" }
$authorized = @($devicesOutput | Where-Object { $_ -match "\bdevice$" })
$unauthorized = @($devicesOutput | Where-Object { $_ -match "\bunauthorized$" })

if ($authorized.Count -eq 0) {
    if ($unauthorized.Count -gt 0) {
        Write-Host "Hay un celular conectado pero sin autorizar todavía." -ForegroundColor Yellow
        Write-Host "Mirá la pantalla del celular y aceptá el popup 'Permitir depuración USB'." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "No detecté ningún celular." -ForegroundColor Red
    Write-Host "Conectalo por USB con 'Depuración USB' activada en Opciones de desarrollador." -ForegroundColor Red
    exit 1
}
if ($authorized.Count -gt 1) {
    Write-Host "Hay más de un dispositivo conectado, desconectá todos menos el que querés usar:" -ForegroundColor Red
    $authorized | ForEach-Object { Write-Host "  $_" }
    exit 1
}
Write-Host "Encontrado: $($authorized[0])"

# --- 2. Compilar ----------------------------------------------------------
Write-Step "Compilando (gradlew.bat assembleDebug)"
$gradlewBat = Join-Path $RepoRoot "gradlew.bat"
if (-not (Test-Path $gradlewBat)) {
    throw "No existe gradlew.bat. Corré .\setup-android-sdk.ps1 primero."
}
Push-Location $RepoRoot
try {
    & $gradlewBat assembleDebug
    if ($LASTEXITCODE -ne 0) { throw "La compilación falló (exit code $LASTEXITCODE)" }
} finally {
    Pop-Location
}

# --- 3. Instalar ------------------------------------------------------------
Write-Step "Instalando en el celular"
$apkPath = Join-Path $RepoRoot "app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path $apkPath)) { throw "No encontré el APK compilado en $apkPath" }
& $adb install -r $apkPath
if ($LASTEXITCODE -ne 0) { throw "adb install falló (exit code $LASTEXITCODE)" }

# --- 4. Habilitar Accessibility Service -------------------------------------
Write-Step "Habilitando el Accessibility Service de Jarvis"
$current = (& $adb shell settings get secure enabled_accessibility_services).Trim()
if ($current -eq "null" -or [string]::IsNullOrWhiteSpace($current)) {
    $existing = @()
} else {
    $existing = $current -split ":" | Where-Object { $_ -ne "" }
}

if ($existing -contains $AccessibilityServiceId) {
    Write-Host "Ya estaba habilitado."
} else {
    $updated = ($existing + $AccessibilityServiceId) -join ":"
    & $adb shell settings put secure enabled_accessibility_services "$updated"
    & $adb shell settings put secure accessibility_enabled 1

    $verify = (& $adb shell settings get secure enabled_accessibility_services).Trim()
    if ($verify -split ":" -contains $AccessibilityServiceId) {
        Write-Host "Habilitado correctamente."
    } else {
        Write-Host "No pude confirmar que haya quedado habilitado. Revisalo a mano en" -ForegroundColor Yellow
        Write-Host "Ajustes -> Accesibilidad -> Jarvis Remote (botón en la pantalla de" -ForegroundColor Yellow
        Write-Host "Configuración de la app)." -ForegroundColor Yellow
    }
}

Write-Step "Listo"
Write-Host "APK instalado y Accessibility Service habilitado." -ForegroundColor Green
Write-Host ""
Write-Host "Falta un solo paso manual dentro de la app (no automatizable por adb," -ForegroundColor Yellow
Write-Host "esos datos viven en almacenamiento privado de la app): abrí Jarvis Remote" -ForegroundColor Yellow
Write-Host "y en Configuración cargá la URL del backend + API key, elegí la carpeta" -ForegroundColor Yellow
Write-Host "de Storage Access Framework, y prendé el switch 'Conexión con Jarvis'." -ForegroundColor Yellow
