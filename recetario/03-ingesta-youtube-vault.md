# 03 — Ingesta de playlist de YouTube al vault 🤖

> Convierte los videos que Damian suma a su playlist "Info para Jarvis" en notas
> del vault de Obsidian, sin pasar cada uno por NotebookLM a mano. **Ya es skill:**
> existe como módulo y como tool del agente. Esta receta documenta cómo dispararla.
>
> Basada en [`../vision/AUTO-INGESTA-PLAYLIST.md`](../vision/AUTO-INGESTA-PLAYLIST.md)
> y el módulo [`../backend/app/ingestion/youtube_playlist.py`](../backend/app/ingestion/youtube_playlist.py).

## Qué produce

Una nota `.md` en el vault por cada video **nuevo** de la playlist: frontmatter
`author=jarvis`, tags `[info-para-jarvis, video, <categoría>]`, secciones Fuente /
Resumen / Temas clave / Notas relacionadas con wikilinks, más el índice de la
playlist actualizado. **Idempotente:** correrlo dos veces no duplica (detecta por
video ID, no por título).

## Estación / especialista

El pase / **Bibliotecario** (vault / conocimiento). Los **commis** (modelos
baratos) hacen la prep: transcripción → resumen. **Requiere PC** con el LLM de
Raphael levantado y **red a YouTube**.

## Ingredientes (requisitos previos)

- LLM de Raphael disponible en el momento de correr (Ollama local levantado, o
  cloud/OpenRouter — ver receta 02).
- Red a YouTube (`yt-dlp` + `youtube-transcript-api`).
- El vault de Obsidian y su nota-índice de la playlist (ya existen).

## Pasos

**Cómo se dispara — tres formas:**

1. **CLI, prueba con un solo video (recomendado la primera vez):**

   ```bash
   cd backend
   python -m app.ingestion.youtube_playlist --max-videos 1
   ```

2. **CLI, procesar todos los nuevos** (sin el flag):

   ```bash
   cd backend
   python -m app.ingestion.youtube_playlist
   ```

3. **Como tool del agente:** `youtube_ingest_playlist` (registrada en
   `app/tools/ingestion.py`) — Raphael la dispara por voz/chat.

**Para que corra sola (programada):** ver receta relacionada de auto-ingesta. El
comando de alta (Programador de tareas de Windows, diario 20:00):

```
schtasks /Create /TN "Jarvis - Auto-ingesta playlist" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\dam\Documents\JarvisRemote\scripts\auto_ingest_playlist.ps1\"" /SC DAILY /ST 20:00 /F
```

Dispararla ya sin esperar: `schtasks /Run /TN "Jarvis - Auto-ingesta playlist"`.

## Tiempo estimado

Segundos a minutos por video (transcripción + resumen). La primera corrida, sumar
la validación end-to-end.

## Notas / errores comunes

- **⚠️ Nunca corrió end-to-end contra YouTube real** (el entorno donde se escribió
  tiene YouTube bloqueado). La lógica de vault/detección/formato/idempotencia sí
  está testeada con mocks. **Correlo una vez a mano** con `--max-videos 1` y revisá
  el resultado antes de confiar en la automatización.
- Un video **sin transcripción** disponible se saltea con gracia (se reporta, no
  crea nota vacía ni rompe la corrida).
- **Dependencia del modelo:** con Ollama local, solo funciona si Ollama está
  corriendo en ese momento; si no, la corrida falla global (queda en el log, la
  tarea igual termina en verde). Con OpenRouter/cloud funciona siempre que haya
  red. **Recomendación:** activar la tarea programada después del cambio a cloud.
- Logs por día en `logs/auto-ingest/YYYY-MM-DD.log` (gitignoreado): `fin OK` =
  limpia; `fin CON FALLO` = pipeline falló global; `EXCEPCION del wrapper` =
  problema del script (ej. `python` no en PATH).

## ¿Candidata a skill?

**🤖 Ya es skill.** Completó el viaje receta → automatización: módulo idempotente
(`youtube_ingest_playlist`) + tool del agente + wrapper para corrida desatendida
por `schtasks`. Es el ejemplo de referencia de una receta graduada. Lo único
pendiente es la validación contra YouTube real (paso humano, una vez).
