<#
.SYNOPSIS
    Deja lista una toolchain de Android 100% por línea de comandos (sin Android
    Studio): JDK 17, Android SDK command-line tools, y el Gradle wrapper del
    proyecto (gradlew.bat), que no está commiteado porque el .jar es binario.

.DESCRIPTION
    Idempotente: cada paso chequea si ya está hecho antes de instalar/descargar
    nada, así que correrlo de nuevo no rompe ni duplica trabajo.

    Fuentes de descarga, todas oficiales:
      - JDK 17: Eclipse Temurin, .zip portable (releases de GitHub de
        adoptium/temurin17-binaries) verificado por SHA-256 y extraído a
        %LOCALAPPDATA% — sin instalador, no hace falta ser administrador.
        (El MSI de winget dispara un prompt de UAC que se cuelga en sesiones
        no interactivas; por eso el .zip en vez del instalador.)
      - Android cmdline-tools: dl.google.com/android/repository (mismo dominio
        que usa sdkmanager para el resto de los paquetes del SDK)
      - Gradle 8.7: services.gradle.org (usado una sola vez, para generar el
        wrapper; de ahí en adelante gradlew.bat se banca solo)

.NOTES
    Después de correr esto puede hacer falta abrir una terminal nueva para que
    las variables de entorno (JAVA_HOME, ANDROID_HOME, PATH) se refresquen.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SdkRoot = "$env:LOCALAPPDATA\Android\Sdk"
$ScratchDir = Join-Path $env:TEMP "jarvis-android-setup"
$PackageId = "com.jarvisremote.app"
$AccessibilityServiceId = "$PackageId/$PackageId.phone.JarvisAccessibilityService"

$JdkInstallDir = "$env:LOCALAPPDATA\Programs\Eclipse Adoptium"
$JdkZipUrl = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.19%2B10/OpenJDK17U-jdk_x64_windows_hotspot_17.0.19_10.zip"
$JdkZipSha256 = "b5b235c48adf6a081874b812c630b9f4b5f637b7a5ed18b9174d08a41ec4c235"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Set-PersistentEnvVar($name, $value) {
    if ([Environment]::GetEnvironmentVariable($name, "User") -ne $value) {
        [Environment]::SetEnvironmentVariable($name, $value, "User")
    }
    Set-Item -Path "env:$name" -Value $value
}

function Add-ToUserPath($dir) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = $current -split ";" | Where-Object { $_ -ne "" }
    if ($parts -notcontains $dir) {
        $updated = ($parts + $dir) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    }
    if (($env:Path -split ";") -notcontains $dir) {
        $env:Path = "$env:Path;$dir"
    }
}

New-Item -ItemType Directory -Force -Path $ScratchDir | Out-Null

# --- 1. JDK 17 ---------------------------------------------------------
Write-Step "JDK 17"
New-Item -ItemType Directory -Force -Path $JdkInstallDir | Out-Null
$jdkDir = Get-ChildItem $JdkInstallDir -Filter "jdk-17*" -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1

if (-not $jdkDir) {
    $jdkZip = Join-Path $ScratchDir "temurin17.zip"
    if (-not (Test-Path $jdkZip)) {
        Write-Host "Descargando Eclipse Temurin 17 JDK, portable .zip (~180MB)..."
        Invoke-WebRequest -Uri $JdkZipUrl -OutFile $jdkZip
    }
    $actualHash = (Get-FileHash -Path $jdkZip -Algorithm SHA256).Hash
    if ($actualHash -ne $JdkZipSha256.ToUpper()) {
        Remove-Item $jdkZip -Force
        throw "El SHA-256 del JDK descargado no coincide con el esperado (posible descarga corrupta o URL desactualizada). Borré el .zip, correlo de nuevo."
    }
    Write-Host "Checksum verificado. Extrayendo a $JdkInstallDir..."
    Expand-Archive -Path $jdkZip -DestinationPath $JdkInstallDir -Force
    $jdkDir = Get-ChildItem $JdkInstallDir -Filter "jdk-17*" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $jdkDir) { throw "Se extrajo el JDK pero no encontré la carpeta 'jdk-17*' dentro de $JdkInstallDir" }
} else {
    Write-Host "Ya está instalado: $($jdkDir.FullName)"
}
Set-PersistentEnvVar "JAVA_HOME" $jdkDir.FullName
Add-ToUserPath "$($jdkDir.FullName)\bin"

# --- 2. Android SDK command-line tools ---------------------------------
Write-Step "Android SDK command-line tools"
New-Item -ItemType Directory -Force -Path $SdkRoot | Out-Null
$sdkManagerBat = "$SdkRoot\cmdline-tools\latest\bin\sdkmanager.bat"

if (-not (Test-Path $sdkManagerBat)) {
    $zipPath = Join-Path $ScratchDir "cmdline-tools.zip"
    if (-not (Test-Path $zipPath)) {
        Write-Host "Descargando Android command-line tools (~150MB) desde dl.google.com..."
        Invoke-WebRequest -Uri "https://dl.google.com/android/repository/commandlinetools-win-14742923_latest.zip" -OutFile $zipPath
    }
    Write-Host "Extrayendo..."
    $extractDir = Join-Path $ScratchDir "cmdline-tools-extract"
    if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    # El zip trae una carpeta "cmdline-tools" plana; sdkmanager espera que esté
    # anidada un nivel más adentro como ".../cmdline-tools/latest/..." (así
    # sabe versionar futuras actualizaciones sin pisarse).
    $latestDir = "$SdkRoot\cmdline-tools\latest"
    New-Item -ItemType Directory -Force -Path "$SdkRoot\cmdline-tools" | Out-Null
    if (Test-Path $latestDir) { Remove-Item -Recurse -Force $latestDir }
    Move-Item "$extractDir\cmdline-tools" $latestDir
} else {
    Write-Host "Ya están instaladas en $SdkRoot\cmdline-tools\latest"
}

Set-PersistentEnvVar "ANDROID_HOME" $SdkRoot
Set-PersistentEnvVar "ANDROID_SDK_ROOT" $SdkRoot
Add-ToUserPath "$SdkRoot\cmdline-tools\latest\bin"
Add-ToUserPath "$SdkRoot\platform-tools"

# --- 3. Licencias + paquetes del SDK ------------------------------------
# NOTA: enviar "y" por un pipe en vivo de PowerShell (`$yesBlock | & sdkmanager`)
# puede colgarse en Windows: sdkmanager redibuja una barra de progreso con
# caracteres de control mientras espera más input, y esa combinación de
# pipe-de-stdin-en-vivo + redraw-de-stdout-en-vivo puede generar un deadlock
# de buffering (el proceso hijo bloqueado escribiendo progreso mientras
# PowerShell no lo está leyendo lo bastante rápido). La forma robusta es
# redirigir stdin/stdout a ARCHIVOS reales (no pipes en vivo) vía cmd.exe, lo
# que elimina el deadlock por completo.
#
# Como refuerzo adicional, escribimos directamente los hashes de licencia
# estándar de Google (los mismos que emite sdkmanager al aceptar) en
# licenses/, así ni siquiera hace falta que sdkmanager pregunte nada.
Write-Step "Licencias del SDK (escritas directamente, sin prompt)"
$licensesDir = Join-Path $SdkRoot "licenses"
New-Item -ItemType Directory -Force -Path $licensesDir | Out-Null

$knownLicenses = @{
    # Las primeras tres son las constantes "clásicas" que circulan en scripts
    # de CI para versiones previas del texto de la licencia. Las últimas dos
    # (efa68a6b... y 9002c006...) las calculé yo mismo con SHA-1 sobre el
    # texto exacto que sdkmanager tiene cacheado en
    # ~/.android/cache/sdkbin-*-repository2-*_xml para la versión vigente
    # (fechada "January 16, 2019") — son las que de verdad importan acá.
    "android-sdk-license" = @(
        "24333f8a63b6825ea9c5514f83c2829b004d1fee",
        "d56f5187479451eabf01fb78af6dfcb131a6481e",
        "8933bad161af4178b1185d1a37fbf41ea5269c55",
        "efa68a6b3c661d18699d5c026771d5911cdc2f83",
        "9002c006f4b8d9a16e715a9fa4df30ddb8abf9d9"
    )
    "android-sdk-preview-license" = @(
        "84831b9409646a918e30573bab4c9c91346d8abd",
        "504667f4c0de7af1a06de9f4b1727b84351f2b7"
    )
}
foreach ($licenseName in $knownLicenses.Keys) {
    $licenseFile = Join-Path $licensesDir $licenseName
    $existingHashes = @()
    if (Test-Path $licenseFile) {
        $existingHashes = Get-Content $licenseFile | Where-Object { $_.Trim() -ne "" }
    }
    $allHashes = @($existingHashes + $knownLicenses[$licenseName] | Select-Object -Unique)
    Set-Content -Path $licenseFile -Value $allHashes -Encoding ASCII
}
Write-Host "Escritas: $($knownLicenses.Keys -join ', ')"

# Por si algún paquete pidiera una licencia que no está en la lista de
# arriba, corremos --licenses igual, pero con stdin/stdout redirigidos a
# archivos (no pipes en vivo) para que no pueda colgarse.
$answersFile = Join-Path $ScratchDir "sdk-license-answers.txt"
(@("y") * 30) -join "`r`n" | Set-Content -Path $answersFile -Encoding ASCII
$licensesLog = Join-Path $ScratchDir "sdkmanager-licenses.log"
Write-Step "Verificando que no quede ninguna licencia pendiente"
cmd /c "`"$sdkManagerBat`" --licenses --sdk_root=`"$SdkRoot`" < `"$answersFile`" > `"$licensesLog`" 2>&1"
if ($LASTEXITCODE -ne 0) {
    Get-Content $licensesLog -Tail 40
    throw "sdkmanager --licenses falló (exit code $LASTEXITCODE). Ver log arriba: $licensesLog"
}

Write-Step "Instalando platform-tools, platform 34 y build-tools 34.0.0"
$installLog = Join-Path $ScratchDir "sdkmanager-install.log"
cmd /c "`"$sdkManagerBat`" --sdk_root=`"$SdkRoot`" `"platform-tools`" `"platforms;android-34`" `"build-tools;34.0.0`" < `"$answersFile`" > `"$installLog`" 2>&1"
if ($LASTEXITCODE -ne 0) {
    Get-Content $installLog -Tail 60
    throw "sdkmanager falló instalando paquetes (exit code $LASTEXITCODE). Ver log arriba: $installLog"
}
Write-Host "Instalación de paquetes completa. Log: $installLog"

# --- 4. local.properties del proyecto -----------------------------------
Write-Step "local.properties"
$sdkDirForProps = $SdkRoot -replace "\\", "/"
Set-Content -Path (Join-Path $RepoRoot "local.properties") -Value "sdk.dir=$sdkDirForProps" -Encoding ASCII
Write-Host "Escrito android-app/local.properties -> sdk.dir=$sdkDirForProps"

# --- 5. Gradle wrapper (gradlew.bat) -------------------------------------
Write-Step "Gradle wrapper"
$gradlewBat = Join-Path $RepoRoot "gradlew.bat"
if (-not (Test-Path $gradlewBat)) {
    $gradleZip = Join-Path $ScratchDir "gradle-8.7-bin.zip"
    if (-not (Test-Path $gradleZip)) {
        Write-Host "Descargando Gradle 8.7 (~130MB) desde services.gradle.org, solo para generar el wrapper..."
        Invoke-WebRequest -Uri "https://services.gradle.org/distributions/gradle-8.7-bin.zip" -OutFile $gradleZip
    }
    $gradleExtractDir = Join-Path $ScratchDir "gradle-extract"
    if (-not (Test-Path "$gradleExtractDir\gradle-8.7\bin\gradle.bat")) {
        Expand-Archive -Path $gradleZip -DestinationPath $gradleExtractDir -Force
    }

    Write-Host "Generando gradlew.bat / gradlew / gradle-wrapper.jar..."
    Push-Location $RepoRoot
    try {
        & "$gradleExtractDir\gradle-8.7\bin\gradle.bat" wrapper --gradle-version 8.7
        if ($LASTEXITCODE -ne 0) { throw "gradle wrapper falló (exit code $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
    # El Gradle standalone ya cumplió su propósito (generar el wrapper); no
    # hace falta dejarlo instalado, gradlew.bat se descarga su propia copia
    # cacheada la primera vez que se use de verdad.
} else {
    Write-Host "gradlew.bat ya existe, no hace falta regenerarlo."
}

Write-Step "Listo"
Write-Host "JAVA_HOME:          $($jdkDir.FullName)"
Write-Host "ANDROID_HOME:       $SdkRoot"
Write-Host "gradlew.bat:        $gradlewBat"
Write-Host "Accessibility Svc:  $AccessibilityServiceId"
Write-Host ""
Write-Host "Si esta es la terminal donde vas a seguir trabajando, las variables de" -ForegroundColor Yellow
Write-Host "entorno ya están seteadas para esta sesión. Si abrís una terminal nueva" -ForegroundColor Yellow
Write-Host "más tarde, también las va a heredar (quedaron persistidas a nivel usuario)." -ForegroundColor Yellow
Write-Host ""
Write-Host "Siguiente paso: conectar el celular por USB con 'Depuración USB' activada" -ForegroundColor Green
Write-Host "en Opciones de desarrollador, aceptar el popup de 'Permitir depuración USB'" -ForegroundColor Green
Write-Host "en el celular (única cosa manual e inevitable), y correr:" -ForegroundColor Green
Write-Host "    .\deploy.ps1" -ForegroundColor Green
