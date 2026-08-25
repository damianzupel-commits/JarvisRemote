<#
.SYNOPSIS
    Ingesta automática y desatendida de la playlist "Info para Jarvis" de YouTube
    al vault de Obsidian de Jarvis.

.DESCRIPTION
    Wrapper pensado para correr desde el Programador de tareas de Windows
    (schtasks). Envuelve el pipeline REAL, ya existente e idempotente:

        python -m app.ingestion.youtube_playlist

    (módulo backend/app/ingestion/youtube_playlist.py). El pipeline detecta por
    VIDEO ID los videos que Damian fue sumando a la playlist y todavía no tienen
    nota, los procesa (transcripción -> resumen + relevancia con el LLM de
    Jarvis) y actualiza el índice del vault. Correrlo dos veces NO duplica.

    Qué agrega este wrapper y nada más:
      - Se para en backend/ (el módulo se importa como paquete `app`).
      - Usa el Python GLOBAL de Windows (este proyecto NO tiene venv).
      - Redirige stdout+stderr a logs/auto-ingest/YYYY-MM-DD.log (append),
        creando la carpeta si no existe. Esa ruta ya está gitignoreada.
      - NUNCA sale con código de error: haga lo que haga el pipeline, el wrapper
        termina con exit 0, así la tarea programada no queda en estado "Error"
        cuando un video individual falla. Los errores TÉCNICOS por video ya los
        reporta el propio pipeline dentro del log; un fallo global (ej. Ollama
        apagado, sin red) queda registrado en el log con su traza para diagnóstico.

.NOTES
    Dependencia de modelo: con Ollama LOCAL, esto sólo funciona si Ollama está
    corriendo en el momento de la corrida. Con OpenRouter/DeepSeek (cloud)
    funciona siempre. Recomendado: activar la tarea DESPUÉS del cambio a
    OpenRouter para que sea realmente desatendida. Ver vision/AUTO-INGESTA-PLAYLIST.md.

    NO commitear este comportamiento como "probado": el pipeline no corrió
    end-to-end contra YouTube real hasta que Damian lo valide una vez en su PC.
#>

# --- Rutas (absolutas, no dependen del cwd desde el que llame el scheduler) ---
$RepoRoot   = Split-Path -Parent $PSScriptRoot            # ...\JarvisRemote
$BackendDir = Join-Path $RepoRoot 'backend'
$LogDir     = Join-Path $RepoRoot 'logs\auto-ingest'
$LogFile    = Join-Path $LogDir ((Get-Date -Format 'yyyy-MM-dd') + '.log')

# --- Carpeta de logs (idempotente) ---
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -Path $LogFile -Value ""
Add-Content -Path $LogFile -Value "===== auto-ingesta playlist :: inicio $stamp ====="

try {
    Push-Location $BackendDir
    try {
        # Python global de Windows. `python -m` importa el paquete `app` desde backend/.
        # `*>>` (append) manda TODOS los streams -- stdout, stderr y demás -- al log.
        & python -m app.ingestion.youtube_playlist *>> $LogFile
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    $stampEnd = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    if ($code -eq 0) {
        Add-Content -Path $LogFile -Value "===== fin OK $stampEnd (exit $code) ====="
    }
    else {
        # Fallo global del pipeline (ej. sin red, LLM caído). Se registra pero
        # NO se propaga como error de la tarea programada.
        Add-Content -Path $LogFile -Value "===== fin CON FALLO $stampEnd (exit $code) -- revisar traza arriba ====="
    }
}
catch {
    # Error inesperado del propio wrapper (ej. python no está en PATH).
    $stampErr = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LogFile -Value "===== EXCEPCION del wrapper $stampErr ====="
    Add-Content -Path $LogFile -Value ($_ | Out-String)
}

# Salir SIEMPRE con 0: la tarea programada no debe marcarse en error por un
# video que falló ni por un problema puntual de red/modelo. El diagnóstico vive
# en el log, no en el estado de la tarea.
exit 0
