# 12 · Tray-app de escritorio (`tray-app/`)

Aplicación de escritorio Windows que administra el backend como subproceso y ofrece la interfaz de
usuario (chat, codebase, obsidian, investigación) más la entrada por voz. Hecha con **pystray** (ícono de
bandeja) + **PySide6** (ventanas). Usa imports planos (`import config`, `import process_manager`), no un
paquete instalado; `conftest.py` ajusta `sys.path` para los tests. Comparte el mismo `backend/.env`.

## Componentes raíz

- **`config.py`** — lee `backend/.env` (`ENV_PATH`), expone la URL del backend, el API key y rutas
  (`TRAY_DIR`, `BACKEND_DIR`).
- **`tray.py`** — la app de bandeja. `main()` arranca pystray; `_acquire_single_instance_lock()` evita dos
  instancias; `_poll_health(icon)` consulta `/api/health` y actualiza el estado/ícono
  (`_set_state`/`_get_state`); menú con Start/Stop (`_on_start`/`_on_stop` → `process_manager`), abrir la
  ventana (`_on_open_docs`), abrir logs (`_on_open_logs`), salir (`_on_quit`). Etiquetas dinámicas
  (`_label_estado`, `_label_backend_url`).
- **`process_manager.py`** — arranca/para el backend como subproceso, redirigiendo stdout+stderr a un log
  file (por eso el logging general "persiste" cuando se corre vía tray). `start()`, `stop()`,
  `is_running()`, `_find_listening_pid(port)`, y `set_active_model(model_id)` (escribe `LMSTUDIO_MODEL` en
  el `.env` — el selector de tiers Lite/Medio/Hard).
- **`icon.py`** — genera el ícono de bandeja al vuelo con Pillow (`build_image(state)`), sin assets
  binarios en el repo, coloreado según el estado.
- **`voice_listener.py`** — escucha continua de voz por PC, 100% local (misma filosofía que el resto):
  mic 16 kHz → openWakeWord "hey jarvis" → beep de confirmación → grabación hasta silencio (Silero VAD
  del `.onnx` que trae openwakeword) → transcripción con **faster-whisper** → `POST /api/chat` (el mismo
  endpoint que la app Android y el chat). Clase `VoiceListener` (`start`/`stop`/`is_running`,
  `_load_models`, `_run`, `_record_command`, `_transcribe_and_send`, `_beep`, `_save_debug_wav`).
  `voice_debug/score_wavs.py` es una utilidad de tuning.

## Interfaz (`tray-app/ui/`)

- **`main_window.py`** — ventana principal PySide6 (reemplaza la vieja de Tkinter). Chat al centro,
  selector de modelo arriba, sidebar de utilidades, toggle de voz. Aloja las pestañas Chat / Codebase /
  Obsidian / Investigación. Usa `theming.py` (compartido, en módulo propio para evitar import circular
  con `settings_window.py`).
- **`chat_view.py`** — pestaña "Chat": sidebar de utilidades + columna de mensajes + input + voz.
- **`codebase_view.py`** — pestaña "Codebase": pide al backend indexar un proyecto
  (`/api/codebase/index`) y dibuja el grafo de imports coloreado por lenguaje (`/api/codebase/graph`);
  panel derecho con outline de símbolos + contenido del archivo (`/api/codebase/file`).
- **`obsidian_view.py`** — pestaña "Obsidian": grafo de notas del vault (`/api/obsidian/graph`) coloreado
  por autor (Jarvis vs. humano), edges por wikilinks. Las notas humanas se crean/editan/borran desde acá;
  las de Jarvis son de solo lectura.
- **`investigation_view.py`** — pestaña "Investigación": selector de casos + grafo de entidades
  (`/api/investigation/{case_id}/graph`) coloreado por tipo, con halo de centralidad+confianza
  (`investigation_colors.py`). Solo lectura.
- **`graph_view.py`** — widget de grafo de nodos reutilizable (lo usan Codebase, Obsidian e
  Investigación); cada dominio le pasa sus nodos/edges/función de color/label. No sabe nada de archivos
  ni notas.
- **`settings_window.py`** — ventana de configuración (permisos/conectores) separada del chat a pedido de
  Damian: la vista de chat queda "limpia, nada técnica"; prender/apagar capacidades invasivas (control de
  PC, shell del celular, cámara, etc.) vive acá.
- **`colors.py` / `investigation_colors.py` / `theming.py` / `widgets.py`** — utilidades de estilo y
  componentes compartidos.

## Cómo se conecta al backend

Habla exclusivamente por HTTP contra el backend local (`/api/health`, `/api/chat`, y los routers de
lectura `/api/codebase`, `/api/obsidian`, `/api/investigation`), con el mismo Bearer token del `.env`. El
`process_manager` administra el ciclo de vida del proceso del backend; la voz manda al mismo `/api/chat`.

Tests en `tray-app/tests/` (una batería por vista + config + process_manager + voz).

---

*Segunda pasada sugerida:* documentar función por función de `main_window.py`, el modelo de eventos de
PySide6 y el pipeline exacto de `voice_listener._run`.
