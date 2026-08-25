# AUTO-INGESTA-PLAYLIST.md — Ingesta automática y programada de la playlist

> Guía operativa. Deja lista la **primera pieza del scheduler** de la orquestación
> (ver `vision/ORQUESTACION-ESTRUCTURA.md`, Capa A / Fase 2): que los videos que
> Damian va sumando a la playlist "Info para Jarvis" se procesen **solos**, sin
> correr el comando a mano.
>
> Creado: 2026-08-23. No commiteado/pusheado por quien lo dejó listo — Damian
> decide cuándo activarlo.

---

## Qué hace

Corre en forma programada el pipeline REAL ya existente e idempotente:

```
python -m app.ingestion.youtube_playlist
```

(módulo `backend/app/ingestion/youtube_playlist.py`). El pipeline:

1. Enumera la playlist "Info para Jarvis" con `yt-dlp` (solo id/título/canal).
2. Detecta por **VIDEO ID** los que todavía no tienen nota en el vault (idempotente:
   correrlo dos veces **no** duplica).
3. Para cada nuevo: transcripción → resumen + puntaje de relevancia con el LLM de
   Jarvis → nota en el vault de Obsidian + actualización del índice.

El único agregado del wrapper `scripts/auto_ingest_playlist.ps1` es infraestructura
de corrida desatendida: se para en `backend/`, usa el **Python global de Windows**
(este proyecto no tiene venv), loguea con fecha, y **nunca sale en error** para que
la tarea programada no quede marcada "Error" cuando un video individual falla (esos
errores técnicos ya los reporta el pipeline dentro del log).

---

## ⚠️ Dependencia del modelo — leer antes de activar

El pipeline necesita el LLM de Jarvis disponible en el momento de la corrida:

- **Con Ollama LOCAL (hoy):** la tarea **solo funciona si Ollama está corriendo**
  en ese momento. Si la PC está encendida pero Ollama no está levantado, la corrida
  falla globalmente (queda registrada en el log; la tarea igual termina en verde).
- **Con OpenRouter / DeepSeek (cloud, transición en curso):** funciona **siempre**
  que haya red, sin depender de tener un servidor local levantado.

**Recomendación:** activar la tarea **después** del cambio a OpenRouter, para que sea
realmente desatendida. Si se activa ahora con Ollama local, conviene una hora en la
que Ollama suela estar corriendo, y asumir que algunas corridas se saltearán.

**Validación previa (una sola vez):** el pipeline nunca corrió end-to-end contra
YouTube real (el entorno donde se escribió tiene YouTube bloqueado). Antes de confiar
en la automatización, correlo **una vez a mano** con red a YouTube y el LLM levantado:

```powershell
cd C:\Users\dam\Documents\JarvisRemote\backend
python -m app.ingestion.youtube_playlist
```

---

## Cómo activarla (un solo comando)

Programador de tareas de Windows, **una vez al día a las 20:00** (ajustá `/ST` a una
hora en que la PC suele estar encendida). Pegar en PowerShell o CMD:

```
schtasks /Create /TN "Jarvis - Auto-ingesta playlist" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\dam\Documents\JarvisRemote\scripts\auto_ingest_playlist.ps1\"" /SC DAILY /ST 20:00 /F
```

`/F` sobrescribe si la tarea ya existe (así este mismo comando sirve para reprogramar
la hora). La tarea corre bajo tu usuario y se dispara cuando estás logueado — que es
justo cuando YouTube y (si aplica) Ollama están disponibles.

**Probar que quedó bien (dispararla ya mismo, sin esperar a las 20:00):**

```
schtasks /Run /TN "Jarvis - Auto-ingesta playlist"
```

Después revisá el log del día (ver abajo).

---

## Cambiar la frecuencia

**Cada 6 horas** (en vez de una vez al día), por si preferís más seguido:

```
schtasks /Create /TN "Jarvis - Auto-ingesta playlist" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\dam\Documents\JarvisRemote\scripts\auto_ingest_playlist.ps1\"" /SC HOURLY /MO 6 /ST 06:00 /F
```

`/SC HOURLY /MO 6` = cada 6 horas, empezando a las 06:00 (06, 12, 18, 00). Como el
pipeline es idempotente, correr de más no hace daño: si no hay videos nuevos, no
hace nada.

Otras cadencias útiles: `/SC DAILY /ST HH:MM` (diario), `/SC WEEKLY /D MON /ST HH:MM`
(semanal). Para solo cambiar la hora de una tarea diaria ya creada, volvé a correr el
comando de activación con la nueva `/ST` (el `/F` la pisa).

---

## Cómo ver los logs

Cada corrida agrega su salida (stdout+stderr) a un archivo por día:

```
C:\Users\dam\Documents\JarvisRemote\logs\auto-ingest\YYYY-MM-DD.log
```

Ver el log de hoy en PowerShell:

```powershell
Get-Content "C:\Users\dam\Documents\JarvisRemote\logs\auto-ingest\$(Get-Date -Format yyyy-MM-dd).log" -Tail 60
```

Qué buscar: `fin OK` = corrida limpia; `fin CON FALLO` = el pipeline falló global
(ej. Ollama caído / sin red — la traza queda arriba en el mismo log); `EXCEPCION del
wrapper` = problema del propio script (ej. `python` no está en PATH). Los errores
técnicos por video se listan en el resumen que imprime el pipeline. La carpeta
`logs/auto-ingest/` está **gitignoreada**: nunca se versiona.

---

## Cómo desactivarla

**Pausar sin borrar** (se puede reactivar después):

```
schtasks /Change /TN "Jarvis - Auto-ingesta playlist" /DISABLE
```

**Reactivar:**

```
schtasks /Change /TN "Jarvis - Auto-ingesta playlist" /ENABLE
```

**Borrar del todo:**

```
schtasks /Delete /TN "Jarvis - Auto-ingesta playlist" /F
```

**Ver si existe / su estado:**

```
schtasks /Query /TN "Jarvis - Auto-ingesta playlist" /V /FO LIST
```

---

## Encuadre en la orquestación

Esto es un **flujo determinístico de la Capa A** (`ORQUESTACION-ESTRUCTURA.md §3.2`):
cron → pasos fijos → salida, sin que un LLM decida el flujo (el LLM solo entra a
redactar el resumen de cada nota). Corre **AUTÓNOMO** por default — el propio módulo
declara `OperationMode.AUTONOMOUS` en su entrypoint. Es la versión mínima y por-fuera
(schtasks) del *"scheduler general de tareas del agente"* que `HACIA-RAPHAEL` Etapa 6
marca FALTA; cuando exista el scheduler interno, este flujo migra a él sin cambiar el
pipeline.
