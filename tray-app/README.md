# tray-app

Tray app de Windows que arranca/administra el `backend` como subproceso y
muestra su estado desde un ícono en la bandeja del sistema.

## Setup

```bash
cd tray-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt          # o requirements-dev.txt para correr los tests
```

Requiere que `backend/` ya tenga su propio venv con las dependencias instaladas
(ver `backend/README.md`) — la tray usa `backend/.venv/Scripts/python.exe` para
lanzar `run.py`. Si ese venv no existe, cae a `python` del PATH.

Para la escucha de voz (`voice_listener.py`), hace falta el modelo custom
`models/hey_jarvis.onnx` (entrenado con TTS en varios acentos de español,
no viene con `pip install`) — sin él, `VoiceListener` falla al cargar el
modelo cuando se prende el toggle de voz.

## Tests

```bash
pytest
```

`pytest-qt` maneja el ciclo de vida de `QApplication` para testear la UI sin
abrir ventanas reales.

## Correr

```bash
python tray.py
```

(Para que no abra una consola visible, usar `pythonw.exe tray.py` en su lugar.)

Al arrancar:
- Autoarranca el backend como subproceso (`backend/run.py`), con stdout/stderr
  redirigidos a `tray-app/backend.log`.
- Empieza a hacer poll a `GET /api/health` cada `POLL_INTERVAL_SECONDS` (default 3s)
  y pinta el ícono según el estado: verde (corriendo), amarillo (iniciando),
  gris (detenido), rojo (caído / no responde).

Menú del ícono (click derecho / click):
- **Estado: ...** / **Backend: http://...** — informativos.
- **Iniciar backend** / **Detener backend**.
- **Abrir Jarvis** (acción default, ver `ui/main_window.py`) — abre la ventana
  principal de chat (PySide6, tema oscuro fijo) para hablarle a Jarvis desde
  la PC contra el mismo `POST /api/chat` que usa la app Android: mismas
  tools, incluidas las de `target="phone"` si el celular está conectado por
  WS (control bidireccional PC↔celular desde un único backend). Usa
  `API_KEY` de `backend/.env` (mismo `.env` que ya lee `config.py`). La
  ventana también se auto-abre al arrancar la tray, así no depende de
  clickear el ícono cada vez.
- **Abrir documentación de la API** — abre `/docs` (Swagger) del backend en el navegador.
- **Ver logs** — abre `backend.log` con la app asociada a `.log` (normalmente el Bloc de notas).
- **Salir** — para el backend y cierra la tray.

## Ventana principal (`ui/main_window.py`)

Tres pestañas (`QTabWidget`) bajo una barra superior compartida — sin
Tkinter, todo PySide6:

- **Selector Lite/Medio/Hard** (arriba, fuera de las pestañas): cambia
  `LMSTUDIO_MODEL` en `backend/.env` y **reinicia el backend** para que lo
  tome (el backend solo lee el `.env` al arrancar, ver
  `process_manager.set_active_model`). Cada cambio de modelo = un reinicio
  real, no es instantáneo.
- **Pestaña 💬 Chat** (`ui/chat_view.py`): sidebar de accesos directos (vacía
  hoy, ver nota de seguridad sobre `generate_image`/`generate_video` en
  `backend/README.md`) + 🎙 escucha continua de "hey Jarvis"
  (`voice_listener.py`), columna de mensajes con indicador de "pensando..."
  mientras se espera la respuesta del backend.
- **Pestaña 🗂 Codebase** (`ui/codebase_view.py`): le pedís que indexe una
  carpeta (`GET /api/codebase/index` del backend) y muestra el árbol de
  archivos coloreado por lenguaje, con desglose de lenguajes arriba y los
  símbolos (funciones/clases/imports) del archivo seleccionado a la derecha.
- **Pestaña 🧠 Obsidian** (`ui/obsidian_view.py`): lista del vault de notas
  (`GET /api/obsidian/notes`), coloreada por autor (Jarvis vs. humano);
  permite crear/editar/borrar notas propias (autor "human" siempre) desde
  acá, las de Jarvis son de solo lectura.
- **Ícono de configuración** (⚙, ver `ui/settings_window.py`): diálogo aparte
  a propósito — la ventana de chat tiene que quedar "limpia, nada técnica".
  Prende/apaga capacidades invasivas (`DESKTOP_CONTROL_ENABLED`,
  `PHONE_SHELL_ENABLED`, `PHONE_CAMERA_ENABLED`, `FS_ALLOW_DELETE`,
  `BROWSER_HEADLESS`) escribiendo directo a `backend/.env`, y también
  reinicia el backend al guardar.

## Voz desde la PC (`voice_listener.py`)

Escucha continua de "hey Jarvis" con el micrófono de la PC, activable desde
el botón 🎙 de la ventana principal: `openWakeWord` (modelo custom entrenado
para el acento de Damian, `models/hey_jarvis.onnx`) detecta la wake word,
Silero VAD decide cuándo terminó el comando, y `faster-whisper` (`medium`,
`language="es"` fijo) lo transcribe antes de mandarlo al mismo
`POST /api/chat`. El audio de cada comando se guarda en `voice_debug/`
(gitignored — es audio real, nunca se publica) para poder diagnosticar
transcripciones raras sin depender de que el usuario repita el intento.

## Cómo está armado

- `config.py` — lee `backend/.env` (mismo HOST/PORT que usa el backend) y arma
  las URLs de health/docs, resuelve qué intérprete de Python usar para
  lanzar el backend, y lista los tiers de modelo disponibles (`AVAILABLE_MODELS`).
- `process_manager.py` — `start()` / `stop()` / `is_running()` sobre un
  `subprocess.Popen` del backend, más `set_active_model()` (reescribe
  `LMSTUDIO_MODEL` en el `.env` y reinicia).
- `icon.py` — dibuja el ícono (círculo de color + "J") con Pillow, sin
  depender de un archivo `.png` en el repo.
- `tray.py` — arma el menú de `pystray`, el thread de polling de salud, y
  conecta los callbacks del menú con `process_manager`.
- `ui/main_window.py` — la ventana principal: barra superior (selector de
  modelo, ajustes) + las tres pestañas.
- `ui/chat_view.py` — pestaña Chat (sidebar, columna de mensajes, voz).
- `ui/codebase_view.py` — pestaña Codebase (árbol de archivos coloreado por
  lenguaje + símbolos del archivo seleccionado).
- `ui/obsidian_view.py` — pestaña Obsidian (lista de notas coloreada por
  autor + panel de detalle + alta/edición/borrado de notas humanas).
- `ui/colors.py` — asignación determinística de color por lenguaje (Codebase)
  y por autor (Obsidian), compartida entre las dos vistas.
- `ui/settings_window.py` — el diálogo de permisos/conectores.
- `ui/theming.py` — helpers de tema oscuro (incluye forzar la barra de título
  oscura en Windows).
- `voice_listener.py` — pipeline de voz de la PC (wake word + VAD + transcripción).

## Arrancar con Windows (opcional, manual)

No lo automatizamos para no tocar la configuración de arranque de tu sistema
sin que lo hagas vos explícitamente. Si querés que la tray arranque sola con
Windows: creá un acceso directo a

```
pythonw.exe C:\ruta\a\JarvisRemote\tray-app\tray.py
```

(usando el `pythonw.exe` del venv de `tray-app`) y ponelo en tu carpeta de
inicio (`Win+R` → `shell:startup`).

## Notas

- La tray asume que `backend/.env` ya existe (copiado desde `.env.example`)
  con `HOST`/`PORT` configurados.
- Si `HOST` en `.env` es `0.0.0.0`, la tray igual le pega al backend por
  `127.0.0.1` (bind-all no es una dirección a la que se pueda conectar un cliente).
