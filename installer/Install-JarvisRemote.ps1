<#
.SYNOPSIS
    Wizard de instalación de un click para JarvisRemote (backend + tray-app en PC).

.DESCRIPTION
    Deja el lado PC del proyecto listo para arrancar sin pasos manuales de LLM:
      1. Detecta hardware (GPU/vendor/VRAM, RAM, disco libre) y recomienda un tier
         (Lite = Qwen3-8B, Medio = Qwen3-30B-A3B, Hard = Medio + generación de video).
      2. Verifica Python (venv para backend/ y tray-app/) y Ollama; si no están,
         ofrece descargar e instalar el .exe oficial (pide confirmación, nunca
         silencioso sin avisar).
      3. Baja el modelo Ollama del tier elegido y lo alias-ea con el nombre que
         ya espera tray-app/config.py (jarvis-text-lite / jarvis-text-v2 /
         jarvis-text-hard, ver el comentario ahí sobre `ollama cp`).
      4. Crea/actualiza backend/.env: API_KEY, LMSTUDIO_BASE_URL apuntando al
         endpoint OpenAI-compatible de Ollama (puerto 11434, no 1234 de LM
         Studio), LMSTUDIO_MODEL con el alias del tier, FS_ALLOWED_ROOT.
      5. Instala dependencias de backend/ y tray-app/ en sus propios venvs.
      6. Para el tier Hard, NO intenta automatizar ComfyUI+Wan2.2 a ciegas
         (son varios GB de pesos específicos + en GPUs AMD un parche de ROCm
         a mano) -- deja una guía clara de qué falta en vez de fingir que lo
         hizo. Ver la sección final del resumen impreso al terminar.

    Lo que sigue siendo manual a propósito, fuera del alcance de este script:
    Tailscale (se detecta si ya está pero no se instala), Termux/Accessibility
    Service del celular, compilar e instalar la app Android, y TLS.

.PARAMETER Tier
    "Lite", "Medio" o "Hard". Si no se pasa, el wizard lo pregunta interactivamente
    (mostrando una recomendación basada en el hardware detectado).

.PARAMETER IncludeDevDeps
    Instala requirements-dev.txt (pytest, etc.) en vez de solo requirements.txt.

.PARAMETER SkipOllama
    No toca Ollama ni modelos -- útil para re-correr solo la parte de venvs/.env.

.PARAMETER SkipVenv
    No toca los venvs de backend/tray-app -- útil para re-correr solo Ollama/.env.

.PARAMETER Force
    Por default, si el alias de Ollama del tier elegido YA EXISTE (ej.
    "jarvis-text-v2" construido a mano desde un GGUF propio con un Modelfile/
    TEMPLATE corregido), el script NO lo toca -- pull/cp podría pisar un
    modelo customizado que ya funciona con uno genérico de la librería de
    Ollama. -Force salta esa protección y sobreescribe igual.

.PARAMETER DryRun
    Muestra qué haría cada paso sin ejecutar instalaciones, descargas ni pulls
    reales. Pensado para revisar el script antes de correrlo en serio.

.EXAMPLE
    .\Install-JarvisRemote.ps1
    Wizard interactivo completo.

.EXAMPLE
    .\Install-JarvisRemote.ps1 -Tier Lite -DryRun
    Simula una instalación Lite sin tocar nada, para ver los pasos.
#>

[CmdletBinding()]
param(
    [ValidateSet("Lite", "Medio", "Hard")]
    [string]$Tier,

    [switch]$IncludeDevDeps,
    [switch]$SkipOllama,
    [switch]$SkipVenv,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $RepoRoot "backend"
$TrayDir    = Join-Path $RepoRoot "tray-app"
$EnvPath    = Join-Path $BackendDir ".env"
$EnvExamplePath = Join-Path $BackendDir ".env.example"

# --- Helpers de output, mismo estilo que android-app/deploy.ps1 ------------

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Info($msg) {
    Write-Host "    $msg" -ForegroundColor Gray
}

function Write-Ok($msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    [!] $msg" -ForegroundColor Yellow
}

function Write-ErrorMsg($msg) {
    Write-Host "    [ERROR] $msg" -ForegroundColor Red
}

function Invoke-MaybeReal {
    <# Envuelve un scriptblock: en -DryRun solo lo describe, si no lo ejecuta. #>
    param([string]$Description, [scriptblock]$Action)
    if ($DryRun) {
        Write-Info "(dry-run) $Description"
        return $null
    }
    Write-Info $Description
    return & $Action
}

function Confirm-Action($Prompt) {
    if ($DryRun) { return $true }
    try {
        $resp = Read-Host "$Prompt (s/N)"
        return $resp -match '^[sSyY]'
    } catch {
        # Read-Host tira (no cuelga) si PowerShell corre en modo no interactivo
        # (ej. invocado por otra herramienta sin consola real, o -NonInteractive).
        # Ante la duda, declinar es la opción segura -- nunca asumir "sí" para
        # una acción que el usuario no pudo confirmar de verdad.
        Write-Warn "No pude preguntar interactivamente ('$Prompt') -- asumo que no."
        return $false
    }
}

# ============================================================================
# 0. Validación de entorno
# ============================================================================

# Si alguien copió solo la carpeta installer/ afuera del repo (o la corrió
# contra un checkout incompleto), todo lo que sigue falla de formas confusas
# más adelante -- mejor cortar acá con un mensaje claro.
if (-not (Test-Path $BackendDir) -or -not (Test-Path $TrayDir)) {
    Write-Host ""
    Write-Host "[ERROR] No encontré backend/ y tray-app/ junto a installer/." -ForegroundColor Red
    Write-Host "        Este script asume que vive dentro del repo de JarvisRemote" -ForegroundColor Red
    Write-Host "        completo -- verificá que no lo copiaste suelto." -ForegroundColor Red
    exit 1
}

# ============================================================================
# 1. Detección de hardware
# ============================================================================

Write-Step "Detectando hardware"

$totalRamGb = $null
try {
    $totalRamGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
    Write-Info "RAM total: $totalRamGb GB"
} catch {
    Write-Warn "No pude leer la RAM total (¿WMI no responde?) -- sigo sin ese dato."
}

$freeGb = $null
try {
    $repoDrive = (Split-Path -Qualifier $RepoRoot).TrimEnd(':')
    $freeGb = [math]::Round((Get-PSDrive -Name $repoDrive).Free / 1GB, 1)
    Write-Info "Espacio libre en disco ${repoDrive}: $freeGb GB"
} catch {
    Write-Warn "No pude leer espacio libre en disco (¿ruta de red o unidad no estándar?)."
}

$gpuName = $null
$gpuVendor = "Desconocido"
$vramGb = $null

# nvidia-smi es la fuente más confiable para VRAM real de NVIDIA (WMI trunca
# AdapterRAM a 32 bits y reporta basura en tarjetas con más de 4GB).
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    try {
        $raw = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
        if ($raw) {
            $first = ($raw -split "`n")[0]
            $parts = $first -split ','
            $gpuName = $parts[0].Trim()
            $vramGb = [math]::Round(([double]($parts[1].Trim() -replace '[^\d.]', '')) / 1024, 1)
            $gpuVendor = "NVIDIA"
        }
    } catch { }
}

if (-not $gpuName) {
    try {
        # Fallback: WMI (AdapterRAM puede venir mal para VRAM > 4GB, así que si
        # detectamos AMD/Intel sin nvidia-smi, avisamos que el número es aproximado).
        $videoControllers = Get-CimInstance Win32_VideoController -ErrorAction Stop | Where-Object { $_.Name -notmatch 'Basic|Remote|Virtual' }
        $gpu = $videoControllers | Select-Object -First 1
        if ($gpu) {
            $gpuName = $gpu.Name
            if ($gpuName -match 'NVIDIA') { $gpuVendor = "NVIDIA" }
            elseif ($gpuName -match 'AMD|Radeon') { $gpuVendor = "AMD" }
            elseif ($gpuName -match 'Intel') { $gpuVendor = "Intel" }

            # Intento leer el tamaño real de VRAM desde el registro (más confiable
            # que Win32_VideoController.AdapterRAM para tarjetas > 4GB).
            try {
                $regBase = "HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
                $qwordVram = Get-ChildItem $regBase -ErrorAction SilentlyContinue |
                    ForEach-Object { Get-ItemProperty -Path $_.PsPath -Name "HardwareInformation.qwMemorySize" -ErrorAction SilentlyContinue } |
                    Where-Object { $_."HardwareInformation.qwMemorySize" -gt 0 } |
                    Select-Object -First 1
                if ($qwordVram) {
                    $vramGb = [math]::Round($qwordVram."HardwareInformation.qwMemorySize" / 1GB, 1)
                }
            } catch { }

            if (-not $vramGb -and $gpu.AdapterRAM -gt 0) {
                $vramGb = [math]::Round($gpu.AdapterRAM / 1GB, 1)
                Write-Warn "VRAM leída de WMI (AdapterRAM) -- puede estar mal si la placa tiene más de 4GB."
            }
        }
    } catch {
        Write-Warn "No pude consultar WMI para detectar la GPU -- sigo sin ese dato."
    }
}

if ($gpuName) {
    Write-Info "GPU: $gpuName ($gpuVendor)"
    if ($vramGb) { Write-Info "VRAM detectada: ~$vramGb GB" }
    else { Write-Warn "No pude determinar la VRAM exacta." }
} else {
    Write-Warn "No detecté una GPU dedicada -- si tenés una, revisá que los drivers estén instalados."
}

# ============================================================================
# 2. Selección de tier
# ============================================================================

Write-Step "Eligiendo tier de modelo"

$vramForRecommendation = if ($vramGb) { $vramGb } else { 0 }
$recommended =
    if ($vramForRecommendation -ge 24) { "Hard" }
    elseif ($vramForRecommendation -ge 12) { "Medio" }
    else { "Lite" }

Write-Info "Lite  -> Qwen3-8B (~6GB VRAM), texto/tools, el más liviano."
Write-Info "Medio -> Qwen3-30B-A3B (MoE, ~19GB de pesos en disco), mejor calidad de razonamiento."
Write-Info "Hard  -> Medio + generación de video (ComfyUI + Wan2.2), necesita VRAM extra y una GPU sin ROCm problemático si es AMD."
Write-Info "Recomendación según tu hardware: $recommended"

if (-not $Tier) {
    if ($DryRun) {
        $Tier = $recommended
        Write-Info "(dry-run) usando la recomendación: $Tier"
    } else {
        while (-not $Tier) {
            $choice = Read-Host "Elegí tier [Lite/Medio/Hard] (enter = $recommended)"
            if ([string]::IsNullOrWhiteSpace($choice)) { $Tier = $recommended; break }
            if ($choice -match '^(?i)lite$') { $Tier = "Lite" }
            elseif ($choice -match '^(?i)medio$') { $Tier = "Medio" }
            elseif ($choice -match '^(?i)hard$') { $Tier = "Hard" }
            else { Write-Warn "No entendí '$choice', probá de nuevo." }
        }
    }
}
Write-Ok "Tier elegido: $Tier"

# --- Caso raro: sin GPU dedicada y el usuario (o la recomendación en
# -DryRun/-Tier) eligió Medio o Hard -- confirmar que sabe que va a correr en
# CPU antes de bajar ~19GB de modelo para algo que puede ser inutilizablemente
# lento en esa máquina. ------------------------------------------------------
if (-not $gpuName -and $Tier -ne "Lite") {
    Write-Warn "No detecté GPU dedicada. El tier $Tier sin GPU corre en CPU:"
    Write-Warn "esperá varios minutos por respuesta (y el tier Hard probablemente"
    Write-Warn "no pueda generar video en un tiempo razonable)."
    if (-not (Confirm-Action "¿Seguir igual con $Tier en CPU?")) {
        $Tier = "Lite"
        Write-Info "Cambiado a Lite."
    }
}

# --- Espacio en disco: estimación gruesa de modelo + venvs por tier ---------
$TierDiskEstimateGb = @{ "Lite" = 8; "Medio" = 25; "Hard" = 25 }
if ($freeGb) {
    $needed = $TierDiskEstimateGb[$Tier]
    if ($freeGb -lt $needed) {
        Write-Warn "Espacio libre ($freeGb GB) por debajo de lo estimado para $Tier (~$needed GB entre el modelo de Ollama y los venvs de Python)."
        if (-not (Confirm-Action "¿Continuar igual? (puede fallar a mitad de camino por falta de espacio)")) {
            Write-ErrorMsg "Cancelado -- liberá espacio y volvé a correr el script."
            exit 1
        }
    } else {
        Write-Ok "Espacio en disco suficiente para $Tier (~$needed GB estimados, hay $freeGb GB libres)."
    }
} else {
    Write-Warn "No pude verificar espacio en disco -- si falla a mitad de un 'ollama pull' o 'pip install', probablemente sea por eso."
}

if ($Tier -eq "Hard" -and $gpuVendor -eq "AMD") {
    Write-Warn "GPU AMD detectada. El video-gen con ComfyUI+Wan2.2 en ROCm no oficial"
    Write-Warn "puede necesitar un venv Python aparte para el runtime de ComfyUI (ver"
    Write-Warn "COMFYUI_PYTHON_PATH en backend/README.md) -- este script deja la guía"
    Write-Warn "al final, no lo automatiza porque depende de tu gfx específica."
}

# ============================================================================
# 3. Python: venvs de backend/ y tray-app/
# ============================================================================

function Get-PythonCommand {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.12") },
        @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $verOut = & $c.Exe @($c.Args) --version 2>&1
            if ($verOut -match 'Python 3\.(\d+)') {
                $minor = [int]$Matches[1]
                if ($minor -ge 10) {
                    return $c
                }
            }
        } catch { continue }
    }
    return $null
}

function New-VenvIfMissing($dir, $pythonCmd) {
    $venvPath = Join-Path $dir ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Ok "venv ya existe en $dir\.venv"
        return $venvPython
    }
    Invoke-MaybeReal "Crear venv en $dir\.venv" {
        Push-Location $dir
        try {
            & $pythonCmd.Exe @($pythonCmd.Args) -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw "python -m venv salió con código $LASTEXITCODE" }
        } finally {
            Pop-Location
        }
    } | Out-Null
    return $venvPython
}

function Install-Requirements($venvPython, $requirementsFile, $label) {
    if (-not (Test-Path $requirementsFile)) {
        Write-Warn "No encontré $requirementsFile, salteo instalación de deps de $label."
        return
    }
    Invoke-MaybeReal "pip install -r $requirementsFile ($label)" {
        & $venvPython -m pip install --upgrade pip --quiet
        & $venvPython -m pip install -r $requirementsFile
        if ($LASTEXITCODE -ne 0) { throw "pip install salió con código $LASTEXITCODE en $label" }
    } | Out-Null
}

if (-not $SkipVenv) {
    Write-Step "Configurando entornos Python (backend/ y tray-app/)"

    $pythonCmd = Get-PythonCommand
    if (-not $pythonCmd -and -not $DryRun) {
        Write-Warn "No encontré un Python 3.10+ instalado."
        if (Confirm-Action "¿Descargar e instalar Python 3.12 (python.org, ~25MB) ahora?") {
            $pyInstaller = Join-Path $env:TEMP "python-installer.exe"
            Write-Info "Descargando instalador de Python desde python.org..."
            Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" -OutFile $pyInstaller
            Write-Info "Instalando (esto abre el instalador oficial, seguí los pasos)..."
            Start-Process -FilePath $pyInstaller -ArgumentList "/passive InstallAllUsers=0 PrependPath=1" -Wait
            Remove-Item $pyInstaller -ErrorAction SilentlyContinue
            $pythonCmd = Get-PythonCommand
        }
    }

    if ($pythonCmd -or $DryRun) {
        if (-not $pythonCmd) { $pythonCmd = @{ Exe = "python"; Args = @() } }
        Write-Ok "Usando Python: $($pythonCmd.Exe) $($pythonCmd.Args -join ' ')"

        $depsFileBackend = if ($IncludeDevDeps) { Join-Path $BackendDir "requirements-dev.txt" } else { Join-Path $BackendDir "requirements.txt" }
        if ($IncludeDevDeps -and -not (Test-Path $depsFileBackend)) { $depsFileBackend = Join-Path $BackendDir "requirements.txt" }
        $venvPythonBackend = New-VenvIfMissing -dir $BackendDir -pythonCmd $pythonCmd
        Install-Requirements -venvPython $venvPythonBackend -requirementsFile $depsFileBackend -label "backend"

        $depsFileTray = if ($IncludeDevDeps) { Join-Path $TrayDir "requirements-dev.txt" } else { Join-Path $TrayDir "requirements.txt" }
        if ($IncludeDevDeps -and -not (Test-Path $depsFileTray)) { $depsFileTray = Join-Path $TrayDir "requirements.txt" }
        $venvPythonTray = New-VenvIfMissing -dir $TrayDir -pythonCmd $pythonCmd
        Install-Requirements -venvPython $venvPythonTray -requirementsFile $depsFileTray -label "tray-app"

        Write-Ok "Entornos Python listos."
    } else {
        Write-ErrorMsg "Sin Python no puedo seguir con esta parte. Instalalo manualmente y volvé a correr el script (o con -SkipVenv si ya lo tenés armado)."
    }
} else {
    Write-Info "Salteando setup de venvs (-SkipVenv)."
}

# ============================================================================
# 4. Ollama: verificar/instalar + bajar modelo del tier
# ============================================================================

# Mapeo tier -> tag de Ollama + alias que ya espera tray-app/config.py
# (AVAILABLE_MODELS: jarvis-text-lite / jarvis-text-v2 / jarvis-text-hard).
$TierModelTag = @{
    "Lite"  = "qwen3:8b"
    "Medio" = "qwen3:30b-a3b"
    "Hard"  = "qwen3:30b-a3b"
}
$TierAlias = @{
    "Lite"  = "jarvis-text-lite"
    "Medio" = "jarvis-text-v2"
    "Hard"  = "jarvis-text-hard"
}

# Si Ollama corre en un host/puerto no default (OLLAMA_HOST seteado por el
# usuario, ej. para exponerlo en la LAN), respetamos eso en vez de asumir
# siempre 127.0.0.1:11434 -- si no, los chequeos de "¿está arriba?" fallarían
# igual aunque Ollama esté corriendo perfectamente.
$OllamaHostPort = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { "127.0.0.1:11434" }
if ($env:OLLAMA_HOST) { Write-Info "OLLAMA_HOST seteado en el entorno: usando $OllamaHostPort en vez del default." }

function Test-OllamaUp($hostPort, $timeoutSec) {
    <# Chequea no solo que el puerto responda, sino que el contenido sea
       realmente la API de Ollama -- otro proceso podría estar escuchando en
       ese puerto por casualidad y un simple "no tiró excepción" sería un
       falso positivo. #>
    try {
        $resp = Invoke-WebRequest -Uri "http://$hostPort/api/version" -UseBasicParsing -TimeoutSec $timeoutSec
        return $resp.Content -match '"version"'
    } catch {
        return $false
    }
}

if (-not $SkipOllama) {
    Write-Step "Verificando Ollama"

    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd -and -not $DryRun) {
        Write-Warn "No encontré 'ollama' en el PATH."
        if (Confirm-Action "¿Descargar e instalar Ollama para Windows (ollama.com, ~700MB) ahora?") {
            $ollamaInstaller = Join-Path $env:TEMP "OllamaSetup.exe"
            Write-Info "Descargando OllamaSetup.exe..."
            Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $ollamaInstaller
            Write-Info "Instalando (silencioso, puede tardar un minuto)..."
            try {
                Start-Process -FilePath $ollamaInstaller -ArgumentList "/VERYSILENT" -Wait
            } catch {
                Write-Warn "La instalación silenciosa falló, abriendo el instalador normal -- completalo a mano."
                Start-Process -FilePath $ollamaInstaller -Wait
            }
            Remove-Item $ollamaInstaller -ErrorAction SilentlyContinue
            # El instalador agrega Ollama al PATH del usuario, pero esta sesión de
            # PowerShell no lo recarga solo -- lo agregamos a mano para poder seguir.
            $ollamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
            if (Test-Path $ollamaDir) { $env:Path = "$env:Path;$ollamaDir" }
            $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
        }
    }

    if ($ollamaCmd -or $DryRun) {
        if ($ollamaCmd) { Write-Ok "Ollama encontrado: $($ollamaCmd.Source)" }

        # Asegurar que el server esté escuchando (el instalador de Windows deja
        # un ícono en la bandeja que lo arranca solo, pero por si está recién
        # instalado en esta misma sesión, lo prendemos a mano si hace falta).
        $serverUp = $false
        if (-not $DryRun) {
            $serverUp = Test-OllamaUp -hostPort $OllamaHostPort -timeoutSec 3

            if (-not $serverUp) {
                Write-Info "Arrancando 'ollama serve' en segundo plano..."
                Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
                for ($i = 0; $i -lt 15 -and -not $serverUp; $i++) {
                    Start-Sleep -Seconds 1
                    $serverUp = Test-OllamaUp -hostPort $OllamaHostPort -timeoutSec 2
                }
            }
        }
        if ($serverUp -or $DryRun) { Write-Ok "Servidor de Ollama respondiendo en $OllamaHostPort." }
        else { Write-Warn "No pude confirmar que el servidor de Ollama esté arriba -- puede necesitar iniciarlo a mano ('ollama serve')." }

        # Caso raro: Ollama ya tiene otro modelo cargado en VRAM (de una sesión
        # de la tray-app corriendo, por ejemplo). No es un problema para
        # pull/cp -- Ollama descarga modelos de VRAM solo cuando necesita
        # lugar -- pero avisamos para que no sorprenda.
        if ($serverUp -and -not $DryRun) {
            try {
                $psLines = (& ollama ps 2>$null) | Select-Object -Skip 1 | Where-Object { $_.Trim() -ne "" }
                if ($psLines) {
                    Write-Info "Ollama ya tiene cargado en memoria: $($psLines -join '; '). No es un problema, se descarga solo cuando haga falta VRAM."
                }
            } catch { }
        }

        $modelTag = $TierModelTag[$Tier]
        $alias = $TierAlias[$Tier]

        function Test-OllamaAliasExists($name) {
            # Ojo: esto corre incluso en -DryRun -- es de solo lectura ('ollama
            # list'), y sin esto el dry-run mentiría sobre si va a pisar un
            # alias existente o no.
            try {
                $hit = (& ollama list 2>$null) | Select-Object -Skip 1 | Where-Object { ($_ -split '\s+')[0] -eq "$name`:latest" -or ($_ -split '\s+')[0] -eq $name }
                return [bool]$hit
            } catch { return $false }
        }

        function Install-OllamaTierModel($tag, $aliasName) {
            # Protección clave: si el alias YA existe, asumimos que es un
            # modelo customizado (ej. construido a mano desde un GGUF propio
            # con un Modelfile/TEMPLATE corregido -- pasó de verdad en esta
            # migración, ver el comentario sobre "bug de template" en
            # backend/.env) y NO lo tocamos. 'ollama cp' sobreescribe sin
            # preguntar, así que la protección tiene que estar ANTES de
            # llamarlo, no depender de que el usuario confirme a tiempo.
            if ((Test-OllamaAliasExists $aliasName) -and -not $Force) {
                Write-Ok "El alias '$aliasName' ya existe en Ollama -- lo dejo como está (no lo piso). Usá -Force si de verdad querés reemplazarlo por '$tag' de la librería de Ollama."
                return
            }
            if ((Test-OllamaAliasExists $aliasName) -and $Force) {
                Write-Warn "El alias '$aliasName' ya existía -- '-Force' está seteado, se sobreescribe con '$tag'."
            }

            Write-Info "Bajando modelo '$tag' (puede tardar bastante según tu conexión)..."
            Invoke-MaybeReal "ollama pull $tag" {
                $attempt = 0
                $maxAttempts = 2
                $pullOk = $false
                do {
                    $attempt++
                    & ollama pull $tag
                    $pullOk = ($LASTEXITCODE -eq 0)
                    if (-not $pullOk -and $attempt -lt $maxAttempts) {
                        Write-Warn "'ollama pull' falló (intento $attempt de $maxAttempts) -- reintentando en unos segundos. 'ollama pull' resume desde donde quedó, no vuelve a bajar todo."
                        Start-Sleep -Seconds 5
                    }
                } while (-not $pullOk -and $attempt -lt $maxAttempts)
                if (-not $pullOk) {
                    throw "ollama pull salió con código $LASTEXITCODE tras $maxAttempts intentos. Volvé a correr el script -- Ollama resume la descarga en vez de empezar de cero."
                }
            } | Out-Null

            Invoke-MaybeReal "ollama cp $tag $aliasName" {
                & ollama cp $tag $aliasName
                if ($LASTEXITCODE -ne 0) { throw "ollama cp salió con código $LASTEXITCODE" }
            } | Out-Null
            Write-Ok "Modelo listo como '$aliasName'."
        }

        Install-OllamaTierModel -tag $modelTag -aliasName $alias

        # Hard reusa el modelo de texto de Medio (ver comentario en
        # tray-app/config.py) -- si el usuario eligió Hard directamente sin
        # pasar por Medio, dejamos también el alias jarvis-text-v2 disponible
        # para que pueda cambiar de tier en la tray sin re-bajar nada. Misma
        # protección: si jarvis-text-v2 ya existe, no lo tocamos.
        if ($Tier -eq "Hard") {
            Install-OllamaTierModel -tag $modelTag -aliasName "jarvis-text-v2"
        }
    } else {
        Write-ErrorMsg "Sin Ollama no puedo bajar el modelo. Instalalo manualmente desde https://ollama.com/download y volvé a correr el script."
    }
} else {
    Write-Info "Salteando setup de Ollama (-SkipOllama)."
}

# ============================================================================
# 5. backend/.env
# ============================================================================

Write-Step "Configurando backend/.env"

function Set-EnvValue {
    <# Reescribe (o agrega) KEY=value en un archivo .env, preservando el resto
       de las líneas tal cual -- mismo approach que
       tray-app/process_manager.py::set_active_model. #>
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value,
        [switch]$OnlyIfEmpty
    )
    $lines = Get-Content -Path $Path -Encoding UTF8
    $prefix = "$Key="
    $found = $false
    $newLines = foreach ($line in $lines) {
        if ($line.StartsWith($prefix)) {
            $found = $true
            $currentValue = $line.Substring($prefix.Length)
            if ($OnlyIfEmpty -and -not [string]::IsNullOrWhiteSpace($currentValue)) {
                $line
            } else {
                "$Key=$Value"
            }
        } else {
            $line
        }
    }
    if (-not $found) { $newLines = $newLines + "$Key=$Value" }

    # OJO: Set-Content -Encoding UTF8 en Windows PowerShell 5.1 escribe con BOM,
    # y python-dotenv abre el archivo con encoding="utf-8" (no "utf-8-sig") --
    # un BOM al principio del archivo se cuela en el nombre de la primera
    # variable (p.ej. "HOST" pasa a ser "﻿HOST") y esa variable deja de
    # matchear en os.getenv(). Escribimos UTF-8 sin BOM a mano para evitarlo.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($Path, $newLines, $utf8NoBom)
}

if (-not (Test-Path $EnvPath)) {
    if (Test-Path $EnvExamplePath) {
        Invoke-MaybeReal "Copiar .env.example -> .env" {
            Copy-Item $EnvExamplePath $EnvPath
        } | Out-Null
    } else {
        Write-ErrorMsg "No encontré backend/.env ni backend/.env.example -- no puedo configurar el backend."
    }
}

if ((Test-Path $EnvPath) -and -not $DryRun) {
    # API_KEY: solo si está vacío, para no pisar una key ya en uso.
    $randomKeyBytes = New-Object byte[] 32
    (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomKeyBytes)
    $randomKey = [Convert]::ToBase64String($randomKeyBytes) -replace '[+/=]', ''
    Set-EnvValue -Path $EnvPath -Key "API_KEY" -Value $randomKey -OnlyIfEmpty

    # FS_ALLOWED_ROOT: solo si está vacío o todavía en el valor placeholder del ejemplo.
    $lines = Get-Content $EnvPath -Encoding UTF8
    $fsLine = $lines | Where-Object { $_.StartsWith("FS_ALLOWED_ROOT=") } | Select-Object -First 1
    $needsFsRoot = (-not $fsLine) -or ($fsLine -eq "FS_ALLOWED_ROOT=") -or ($fsLine -match 'TuUsuario')
    if ($needsFsRoot) {
        Set-EnvValue -Path $EnvPath -Key "FS_ALLOWED_ROOT" -Value $env:USERPROFILE
    }

    # LMSTUDIO_BASE_URL / LMSTUDIO_MODEL: el nombre de la variable quedó de
    # cuando el backend hablaba con LM Studio, pero hoy el LLM real es Ollama
    # (ver tray-app/config.py) -- por eso apuntamos al endpoint OpenAI-compatible
    # de Ollama (puerto 11434), no al 1234 default de LM Studio.
    if (-not $SkipOllama) {
        Set-EnvValue -Path $EnvPath -Key "LMSTUDIO_BASE_URL" -Value "http://$OllamaHostPort/v1"
        Set-EnvValue -Path $EnvPath -Key "LMSTUDIO_MODEL" -Value $TierAlias[$Tier]
    }

    Write-Ok "backend/.env actualizado."

    # Si el backend ya está corriendo (ej. lo dejaste andando de una sesión
    # anterior), este .env nuevo no se aplica solo -- lee el archivo una sola
    # vez al arrancar (ver backend/app/config.py). Avisamos para que no
    # parezca que el instalador "no funcionó".
    try {
        $backendListening = (& netstat -ano | Select-String ":8000 ") | Select-String "LISTENING"
        if ($backendListening) {
            Write-Warn "El backend parece estar corriendo ahora mismo (puerto 8000) -- estos cambios en .env no toman efecto hasta reiniciarlo (botón 'Detener'/'Iniciar backend' de la tray, o el selector de modelo, que reinicia solo)."
        }
    } catch { }
} elseif ($DryRun) {
    Write-Info "(dry-run) actualizaría API_KEY (si vacío), FS_ALLOWED_ROOT (si vacío/placeholder), LMSTUDIO_BASE_URL y LMSTUDIO_MODEL en backend/.env"
}

# Tailscale: solo detectamos, no instalamos (requiere login interactivo con
# cuenta del usuario, no tiene sentido automatizarlo a ciegas).
$tailscaleCmd = Get-Command tailscale -ErrorAction SilentlyContinue
if ($tailscaleCmd) {
    try {
        $tsIp = (& tailscale ip -4 2>$null | Select-Object -First 1)
        if ($tsIp -match '^\d+\.\d+\.\d+\.\d+$') {
            Write-Ok "Tailscale detectado, IP: $tsIp"
            if (-not $DryRun -and (Confirm-Action "¿Configurar HOST=$tsIp en backend/.env para que el backend solo escuche en tu tailnet?")) {
                Set-EnvValue -Path $EnvPath -Key "HOST" -Value $tsIp
                Write-Ok "HOST configurado a tu IP de Tailscale."
            }
        }
    } catch { }
} else {
    Write-Info "Tailscale no detectado -- instalalo manualmente si querés acceso remoto seguro (ver README.md)."
}

# ============================================================================
# 6. Tier Hard: guía de ComfyUI + Wan2.2 (no automatizado)
# ============================================================================

if ($Tier -eq "Hard") {
    Write-Step "Tier Hard: generación de video (ComfyUI + Wan2.2)"
    Write-Warn "Esta parte NO se automatiza -- son varios GB de pesos específicos y,"
    Write-Warn "en GPUs AMD, un venv de PyTorch/ROCm separado según tu gfx exacta."
    Write-Warn "Pasos manuales que quedan pendientes:"
    Write-Info "  1. Bajar ComfyUI portable (Windows) desde https://github.com/comfyanonymous/ComfyUI/releases"
    Write-Info "  2. Instalar el custom node ComfyUI-GGUF (city96) para cargar los .gguf de Wan2.2."
    Write-Info "  3. Bajar los pesos de Wan2.2 (unet + clip + vae, variante GGUF cuantizada) y ponerlos en models/ dentro de la instalación de ComfyUI."
    Write-Info "  4. Si tu GPU es AMD no soportada oficialmente por ROCm: crear un venv aparte con un build de torch+ROCm que sí detecte tu gfx (ver el comentario largo en backend/app/config.py sobre COMFYUI_PYTHON_PATH -- pasó de verdad en esta máquina con una gfx1031)."
    Write-Info "  5. Setear en backend/.env: COMFYUI_DIR (carpeta de la instalación) y, si aplica, COMFYUI_PYTHON_PATH (el venv que sí funciona)."
    Write-Info "  Ver backend/README.md, sección de generate_image/generate_video, para el detalle completo."
}

# ============================================================================
# 7. Resumen final
# ============================================================================

Write-Step "Resumen"
Write-Ok "Tier configurado: $Tier"
if (-not $SkipVenv) { Write-Ok "Venvs de backend/ y tray-app/ listos." }
if (-not $SkipOllama) { Write-Ok "Modelo Ollama '$($TierAlias[$Tier])' listo." }
Write-Ok "backend/.env configurado."
Write-Host ""
Write-Host "Para arrancar:" -ForegroundColor Cyan
Write-Host "  cd tray-app"
Write-Host "  .venv\Scripts\python.exe tray.py"
Write-Host ""
Write-Host "Pendiente manual (fuera del alcance de este instalador):" -ForegroundColor Cyan
Write-Host "  - Tailscale (si no lo configuraste arriba) para acceso remoto seguro."
Write-Host "  - Termux + Accessibility Service + compilar/instalar la app Android (ver android-app/README.md)."
if ($Tier -eq "Hard") { Write-Host "  - ComfyUI + Wan2.2 (ver guía impresa arriba)." }
Write-Host ""
