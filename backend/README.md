# backend

Servicio FastAPI que conecta con LM Studio y expone `POST /api/chat` para
mandarle órdenes al modelo, con un framework de tools que el LLM puede invocar.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # incluye requirements.txt + pytest/httpx
playwright install chromium
copy .env.example .env
```

Editá `.env`:
- `API_KEY`: poné un valor fijo (si lo dejás vacío se genera uno random en cada
  arranque y lo ves en la consola, pero no persiste).
- `HOST`: idealmente tu IP de Tailscale (`tailscale ip -4`), para que el server
  literalmente no escuche fuera de la VPN.
- `LMSTUDIO_BASE_URL` / `LMSTUDIO_MODEL`: revisá en LM Studio → Developer → Local
  Server qué puerto y nombre de modelo está usando.
- `FS_ALLOWED_ROOT`: carpeta raíz a la que quedan limitadas las tools de
  filesystem.
- `DESKTOP_CONTROL_ENABLED`: prende/apaga las tools `desktop_*` (control de
  mouse/teclado/ventanas de la PC, ver sección de seguridad más abajo).
  Default `true`.
- `PHONE_SHELL_ENABLED`: prende/apaga `phone_run_command` (ejecución de shell
  real en el celular vía Termux, ver sección de seguridad más abajo). Default
  `true`. No confundir con la conexión del celular en sí (eso lo prende el
  usuario desde la app Android) — este flag es una segunda llave del lado del
  backend, específica para la tool más invasiva.

## Correr

En LM Studio: cargar el modelo de 30B y arrancar el "Local Server" (por defecto
`http://localhost:1234`).

```bash
python run.py
```

Probar:

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Listame los archivos de mi escritorio\"}"
```

## Tests

```bash
pytest
```

## Cómo está armado

- `app/config.py` — settings desde `.env` (host/puerto, API key, LM Studio, sandbox
  de filesystem, headless del browser, tope de iteraciones del agente).
- `app/auth.py` — dependency de FastAPI que valida el header `Authorization: Bearer`.
- `app/llm_client.py` — cliente OpenAI apuntando a LM Studio.
- `app/agent.py` — el loop del agente: manda mensajes + tool schemas a LM Studio,
  ejecuta las tool calls que pida el modelo, le devuelve los resultados, repite
  hasta que conteste en texto o se llegue a `MAX_AGENT_ITERATIONS`. Guarda historial
  en memoria por `conversation_id`.
- `app/tools/__init__.py` — registry de tools (`register_tool` / `get_tools` /
  `openai_tool_schemas` / `call_tool`). Soporta handlers sync y async.
- `app/tools/filesystem.py` — `fs_list_dir`, `fs_read_file`, `fs_write_file`,
  `fs_create_dir`, `fs_move_path`, `fs_delete_path` (deshabilitada por default).
  Todo sandboxeado a `FS_ALLOWED_ROOT`.
- `app/tools/browser.py` — `browser_open`, `browser_click`, `browser_type`,
  `browser_get_text`, `browser_screenshot`, `browser_close`, con Playwright
  (Chromium, una sola página persistente entre llamadas).
- `app/tools/desktop.py` — `desktop_screenshot`, `desktop_list_windows`,
  `desktop_focus_window`, `desktop_click`, `desktop_click_element`,
  `desktop_type_text`, `desktop_press_key`, `desktop_move_mouse`,
  `desktop_scroll`, `desktop_launch_app`. Control general del escritorio
  (cualquier ventana/app), vía `pywinauto` (UI Automation) + `pyautogui`
  (coordenadas). `desktop_launch_app` (vía `os.startfile`, con fallback a
  `cmd /c start`) es la única forma soportada de abrir programas — probado en
  vivo que simular Win+buscar+escribir+enter con las otras tools es frágil y
  no abre la app de forma confiable. `desktop_focus_window`/
  `desktop_click_element` devuelven el proceso dueño de la ventana matcheada
  (el matching es por substring del título, así que puede haber falsos
  positivos). Ver sección de seguridad más abajo — es tan invasivo como el
  Accessibility Service del celular.
- `app/tools/phone.py` — tools con `target="phone"`, despachadas al celular por
  WebSocket (`app/phone_link.py`): `phone_open_app`, `phone_list_dir`/
  `read_file`/`write_file`, `phone_tap`/`swipe`/`type_text`/`read_screen`/
  `global_action` (Accessibility Service), y `phone_run_command` — shell real
  en el celular vía Termux, el nivel más invasivo posible (código arbitrario,
  no solo UI). Gateada por `PHONE_SHELL_ENABLED` y logueada como auditoría en
  `phone_link.dispatch_to_phone`. Ver sección de seguridad más abajo.
- `app/main.py` — endpoints `GET /api/health` y `POST /api/chat`.

## Agregar una tool nueva

1. Crear (o reusar) un módulo en `app/tools/`.
2. Definir una función sync o async, decorada con `@register_tool(name=..., description=..., parameters=<json-schema>)`.
3. Importar el módulo al final de `app/tools/__init__.py` si es un archivo nuevo.

No hace falta tocar `agent.py` ni `main.py`: el agente arma los schemas y despacha
las tool calls automáticamente contra el registry.

## Notas de seguridad

- El backend no valida quién está del otro lado más allá del Bearer token: la
  barrera principal es que solo es alcanzable a través de tu tailnet.
- `fs_delete_path` está apagada por default (`FS_ALLOW_DELETE=false`).
- Las tools de filesystem no pueden salir de `FS_ALLOWED_ROOT`.
- El modelo necesita soportar tool/function calling en el formato de LM Studio
  para que el loop de tools funcione (la mayoría de los modelos instruct
  modernos —Qwen2.5-Instruct, Llama-3.1-Instruct, Hermes, etc.— lo soportan).
- **Las tools `desktop_*` (`app/tools/desktop.py`) son control total e
  invasivo del escritorio de Windows**: el modelo puede ver la pantalla
  (`desktop_screenshot`), listar y enfocar cualquier ventana, mover el mouse,
  clickear (por coordenadas o por control de UI Automation), escribir texto y
  mandar combinaciones de teclas en CUALQUIER programa abierto — incluyendo
  banca online, gestores de contraseñas, apps de 2FA, email, lo que esté en
  pantalla en ese momento. No hay sandboxing posible para esto (a diferencia
  de filesystem): es equivalente en alcance al Accessibility Service del
  celular. Es una decisión consciente del usuario, prendida por default
  (`DESKTOP_CONTROL_ENABLED=true`); poner `DESKTOP_CONTROL_ENABLED=false` en
  `.env` para desactivar todas las tools de escritorio sin tocar código.
  Cada acción de escritorio se loguea (nombre, argumentos, timestamp) al
  logger `jarvis.desktop` como rastro de auditoría.
- Las tools de escritorio no pueden controlar ventanas elevadas (UAC,
  "Ejecutar como administrador", instaladores, Task Manager elevado) —
  restricción de Windows (UIPI), no un bug. Cuando se detecta ese caso se
  devuelve `ElevatedWindowError` con un mensaje claro, pero no siempre es
  detectable: `pyautogui` puede mandar clicks/teclas "al vacío" sin tirar
  ningún error si el foco está en una ventana elevada.
- **`phone_run_command` es ejecución de shell REAL en el celular, vía Termux**:
  el modelo puede correr cualquier comando/script que corra en Termux —
  código arbitrario, no acotado a interactuar con la UI. Es la tool más
  invasiva de todo el proyecto, en la misma categoría de riesgo que el
  Accessibility Service pero para código en vez de pantalla. No hay
  sandboxing posible más allá de lo que el propio entorno de Termux limite.
  Requiere que el usuario haya hecho, todo manual: instalar Termux desde
  F-Droid (no la Play Store), `allow-external-apps=true` en
  `~/.termux/termux.properties`, y otorgar el permiso Android
  `com.termux.permission.RUN_COMMAND` (botón en la app, ver
  `android-app/README.md`). Gateada del lado del backend por
  `PHONE_SHELL_ENABLED=true` (default), y cada comando se loguea (herramienta,
  argumentos, timestamp) en `phone_link.dispatch_to_phone` vía el logger
  `jarvis.phone_link`, como rastro de auditoría dado el nivel de riesgo.
