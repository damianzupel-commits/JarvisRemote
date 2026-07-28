<#
.SYNOPSIS
    Instalador de un solo comando para JarvisRemote en Windows: detecta tu
    hardware, instala/verifica Ollama, baja y arma el modelo de texto del tier
    que corresponda, y deja el backend + la tray-app listos para correr.

.DESCRIPTION
    Cubre la parte que es igual para cualquier instalación (texto/chat +
    control de PC vía tools). Lo que NO cubre, a propósito, porque depende de
    hardware/software específico que este script no puede asumir con
    seguridad:
      - ComfyUI (generate_image/generate_video): instalación portable propia,
        con un intérprete Python distinto según tu GPU (ver
        backend/README.md, sección de generate_image/generate_video, y las
        limitaciones conocidas de estabilidad ahí documentadas). Si no te
        interesa generar imágenes/video, no hace falta tocar nada de esto.
      - La app Android: ver android-app/README.md y
        android-app/setup-android-sdk.ps1 + deploy.ps1.
      - Termux/phone_run_command, TLS, Tailscale: pasos manuales documentados
        en backend/README.md (sección de seguridad) -- son decisiones
        conscientes del usuario, no algo para automatizar a ciegas.

    Idempotente: correrlo de nuevo no reinstala Ollama si ya está, ni vuelve a
    bajar un modelo que ya existe, ni pisa un backend/.env que ya tengas.

.NOTES
    Necesita PowerShell 5.1+ (viene con Windows) y una conexión a internet
    para bajar Ollama (si no lo tenés) y el modelo elegido (varios GB).
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RepoRoot "backend"
$TrayDir = Join-Path $RepoRoot "tray-app"
$ModelfileDir = Join-Path $RepoRoot "installer\ollama"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Info($msg) {
    Write-Host "    $msg" -ForegroundColor DarkGray
}

function Write-Warn($msg) {
    Write-Host "    $msg" -ForegroundColor Yellow
}

# --- 1. Detectar hardware ---------------------------------------------------
Write-Step "Detectando hardware"

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$gpus = Get-CimInstance Win32_VideoController | Where-Object { $_.AdapterRAM -gt 0 }

Write-Info "CPU: $($cpu.Name)"
Write-Info "RAM total: ${ramGb}GB"

$vramGb = 0
foreach ($gpu in $gpus) {
    # AdapterRAM es un uint32 en WMI -- en GPUs con más de 4GB se desborda y
    # queda en un valor absurdo (ej. 4294967295 o un negativo). No hay forma
    # 100% confiable de sacar la VRAM real solo con WMI en esos casos; se
    # reporta igual el nombre de la GPU y se usa el valor si parece razonable
    # (entre 0 y 64GB), si no se avisa y se sigue con la estimación por RAM.
    $gpuVramGb = [math]::Round($gpu.AdapterRAM / 1GB, 1)
    Write-Info "GPU: $($gpu.Name) (VRAM reportada por WMI: ${gpuVramGb}GB)"
    if ($gpuVramGb -gt 0 -and $gpuVramGb -le 64) {
        $vramGb = [math]::Max($vramGb, $gpuVramGb)
    }
}

if ($vramGb -eq 0) {
    Write-Warn "No pude leer la VRAM de forma confiable (limitación conocida de WMI en GPUs >4GB)."
    Write-Warn "Voy a recomendar el tier según la RAM total en su lugar -- es una aproximación, no una medición real."
}

# --- 2. Elegir tier ----------------------------------------------------------
Write-Step "Eligiendo tier de modelo"

# Heurística, no ciencia exacta: "Medio/Hard" es Qwen3-30B-A3B (Q4_K_M, ~18GB
# en disco) -- para correrlo con margen razonable en RAM/VRAM combinada (esta
# arquitectura MoE permite offloading parcial a RAM sin ser insoportable)
# conviene tener por lo menos ~20GB entre VRAM+RAM libres. "Lite" es
# Qwen3-8B (Q4_K_M, ~5GB) y corre cómodo con bastante menos.
$effectiveGb = if ($vramGb -gt 0) { $vramGb + $ramGb } else { $ramGb }
$recommendedTier = if ($effectiveGb -ge 24) { "v2" } else { "lite" }

Write-Info "Estimación combinada VRAM+RAM: ${effectiveGb}GB"
Write-Info "Tier recomendado: $recommendedTier ($(if ($recommendedTier -eq 'v2') { 'Qwen3-30B-A3B, ~18GB' } else { 'Qwen3-8B, ~5GB' }))"

$tierInput = Read-Host "Elegí tier [lite/v2] (Enter para usar la recomendación: $recommendedTier)"
$tier = if ([string]::IsNullOrWhiteSpace($tierInput)) { $recommendedTier } else { $tierInput.Trim().ToLower() }
if ($tier -notin @("lite", "v2")) {
    throw "Tier inválido: '$tier' (tiene que ser 'lite' o 'v2')"
}

$modelName = "jarvis-text-$tier"
$modelfilePath = Join-Path $ModelfileDir "jarvis-text-$tier.Modelfile"
$baseTag = if ($tier -eq "v2") { "qwen3:30b-a3b" } else { "qwen3:8b" }

# --- 3. Ollama: verificar o instalar -----------------------------------------
Write-Step "Verificando Ollama"

$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCmd) {
    Write-Info "Ya está instalado: $($ollamaCmd.Source)"
} else {
    Write-Info "No encontré Ollama. Descargando el instalador oficial..."
    $installerPath = Join-Path $env:TEMP "OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installerPath

    # Sin flag silencioso asumido a ciegas: el instalador de Ollama es un .exe
    # propio (no MSI/winget), y no hay una API pública documentada y estable
    # para instalación desatendida -- forzar un flag no verificado puede
    # colgarse igual que el MSI de winget (ver android-app/setup-android-sdk.ps1).
    # Se abre normal y se le pide al usuario un click, una sola vez.
    Write-Warn "Se va a abrir el instalador de Ollama -- hace falta un click tuyo para continuar."
    Start-Process -FilePath $installerPath -Wait

    # Refrescar PATH de esta sesión (el instalador lo actualiza a nivel de
    # usuario, pero esta consola ya tiene el PATH viejo cacheado).
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {
        throw "Instalé Ollama pero no lo encuentro en el PATH todavía. Abrí una terminal nueva y volvé a correr este script."
    }
}

# Esperar a que el servicio de Ollama (arranca solo tras instalar/con Windows)
# esté escuchando antes de pedirle nada.
Write-Info "Esperando a que Ollama responda..."
$ollamaReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
        $ollamaReady = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ollamaReady) {
    throw "Ollama no respondió en http://127.0.0.1:11434 después de 60s. Abrilo a mano (buscá 'Ollama' en el menú de inicio) y volvé a correr este script."
}
Write-Info "Ollama respondiendo en 127.0.0.1:11434."

# --- 4. Modelo: pull + create con el template arreglado ----------------------
Write-Step "Preparando el modelo '$modelName'"

$existingModels = (ollama list) -join "`n"
if ($existingModels -match [regex]::Escape($modelName)) {
    Write-Info "'$modelName' ya existe, no hace falta rehacerlo."
} else {
    if (-not (Test-Path $modelfilePath)) {
        throw "No encontré el Modelfile esperado en $modelfilePath"
    }

    Write-Info "Bajando el modelo base '$baseTag' (puede tardar bastante, son varios GB)..."
    ollama pull $baseTag
    if ($LASTEXITCODE -ne 0) { throw "'ollama pull $baseTag' falló (exit code $LASTEXITCODE)" }

    Write-Info "Armando '$modelName' con el template de tool-calling corregido..."
    Push-Location $ModelfileDir
    try {
        ollama create $modelName -f "jarvis-text-$tier.Modelfile"
        if ($LASTEXITCODE -ne 0) { throw "'ollama create $modelName' falló (exit code $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }

    if ($tier -eq "v2") {
        # "Hard" no es un modelo de texto distinto -- ver la nota en
        # tray-app/config.py::AVAILABLE_MODELS sobre por qué existe igual como
        # alias propio (el selector necesita poder distinguir cuál eligió el
        # usuario, aunque el modelo real sea el mismo).
        $existingHard = (ollama list) -join "`n"
        if ($existingHard -notmatch [regex]::Escape("jarvis-text-hard")) {
            Write-Info "Creando 'jarvis-text-hard' como alias de '$modelName'..."
            ollama cp $modelName jarvis-text-hard
        }
    }
}

# --- 5. Backend: venv + .env --------------------------------------------------
Write-Step "Configurando el backend"

$backendVenv = Join-Path $BackendDir ".venv"
if (-not (Test-Path $backendVenv)) {
    Write-Info "Creando venv de Python en backend\.venv..."
    python -m venv $backendVenv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el venv (¿está python en el PATH? probá 'python --version')" }
}

$backendPip = Join-Path $backendVenv "Scripts\pip.exe"
$backendReq = Join-Path $BackendDir "requirements.txt"
Write-Info "Instalando dependencias del backend (puede tardar unos minutos)..."
& $backendPip install -q -r $backendReq
if ($LASTEXITCODE -ne 0) { throw "pip install del backend falló (exit code $LASTEXITCODE)" }

$envPath = Join-Path $BackendDir ".env"
$envExamplePath = Join-Path $BackendDir ".env.example"
if (Test-Path $envPath) {
    Write-Info "backend\.env ya existe, no lo piso."
} else {
    Write-Info "Generando backend\.env desde .env.example..."
    $envContent = Get-Content $envExamplePath -Raw

    # API key propia, no la dejamos vacía -- ver el comentario del .env.example
    # sobre por qué (la que se genera sola al arrancar no persiste entre
    # reinicios).
    $apiKeyBytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($apiKeyBytes)
    $apiKey = [Convert]::ToBase64String($apiKeyBytes) -replace '[+/=]', ''

    # Preferimos la IP de Tailscale si ya está instalado y logueado (más a
    # prueba de balas, ver el comentario del propio .env.example); si no,
    # dejamos 0.0.0.0 tal como viene el ejemplo.
    $tailscaleCmd = Get-Command tailscale -ErrorAction SilentlyContinue
    $hostValue = "0.0.0.0"
    if ($tailscaleCmd) {
        try {
            $tsIp = (& tailscale ip -4 2>$null | Select-Object -First 1).Trim()
            if ($tsIp) { $hostValue = $tsIp }
        } catch {}
    }

    $envContent = $envContent -replace "(?m)^HOST=.*$", "HOST=$hostValue"
    $envContent = $envContent -replace "(?m)^API_KEY=.*$", "API_KEY=$apiKey"
    $envContent = $envContent -replace "(?m)^LMSTUDIO_BASE_URL=.*$", "LMSTUDIO_BASE_URL=http://127.0.0.1:11434/v1"
    $envContent = $envContent -replace "(?m)^LMSTUDIO_MODEL=.*$", "LMSTUDIO_MODEL=$modelName"
    $envContent = $envContent -replace "(?m)^FS_ALLOWED_ROOT=.*$", "FS_ALLOWED_ROOT=$env:USERPROFILE"

    Set-Content -Path $envPath -Value $envContent -Encoding utf8
    Write-Info "Listo. API key generada (guardala si vas a configurar la app Android/celular)."
    if ($hostValue -eq "0.0.0.0") {
        Write-Warn "HOST quedó en 0.0.0.0 (no encontré Tailscale). Es funcional, pero considerá instalar Tailscale"
        Write-Warn "y volver a correr este script para que el backend solo sea alcanzable por tu tailnet."
    }
}

# --- 6. tray-app: venv --------------------------------------------------------
Write-Step "Configurando la tray-app"

$trayVenv = Join-Path $TrayDir ".venv"
if (-not (Test-Path $trayVenv)) {
    Write-Info "Creando venv de Python en tray-app\.venv..."
    python -m venv $trayVenv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el venv de la tray" }
}

$trayPip = Join-Path $trayVenv "Scripts\pip.exe"
$trayReq = Join-Path $TrayDir "requirements.txt"
Write-Info "Instalando dependencias de la tray-app..."
& $trayPip install -q -r $trayReq
if ($LASTEXITCODE -ne 0) { throw "pip install de la tray falló (exit code $LASTEXITCODE)" }

# --- 7. Resumen ----------------------------------------------------------------
Write-Step "Listo"
Write-Host "Backend + tray-app configurados con el modelo '$modelName'." -ForegroundColor Green
Write-Host ""
Write-Host "Para arrancar:" -ForegroundColor Green
Write-Host "  cd tray-app"
Write-Host "  .\.venv\Scripts\pythonw.exe tray.py"
Write-Host ""
Write-Host "Lo que este script NO cubre (a propósito, ver el header de este archivo):" -ForegroundColor Yellow
Write-Host "  - generate_image/generate_video (ComfyUI): instalación aparte, ver backend/README.md."
Write-Host "  - La app Android: ver android-app/README.md."
Write-Host "  - Termux, TLS, Tailscale (si no lo tenías ya): pasos manuales en backend/README.md."
Write-Host ""
Write-Host "Nota sobre los tags base de Ollama ('qwen3:30b-a3b', 'qwen3:8b'):" -ForegroundColor Yellow
Write-Host "  se confirmaron contra el registry (manifests existen), pero no se verificó" -ForegroundColor Yellow
Write-Host "  el contenido exacto del blob -- si el tool-calling se comporta raro, comparar" -ForegroundColor Yellow
Write-Host "  con 'ollama show jarvis-text-$tier' de una instalación que ya sabés que funciona." -ForegroundColor Yellow
