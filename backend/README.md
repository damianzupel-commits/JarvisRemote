# backend

Servicio FastAPI que conecta con LM Studio y expone `POST /api/chat` para
mandarle órdenes al modelo, con un framework de tools que el LLM puede invocar.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # incluye requirements.txt + pytest/httpx
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
- `TLS_ENABLED`: sirve `https://`/`wss://` en vez de texto plano. **Preparado
  pero apagado por default** — ver `backend/certs/README.md` antes de tocar
  esto, activarlo a lo loco corta el acceso de la app.
- `COMFYUI_DIR` / `COMFYUI_PYTHON_PATH` / `COMFYUI_BASE_URL`: solo hacen falta
  para `generate_image`/`generate_video`. Apuntan a tu instalación portable de
  ComfyUI y al intérprete Python que la corre — en GPUs AMD no soportadas
  oficialmente por ROCm (ver nota más abajo) puede hacer falta un venv aparte
  al de la instalación portable.

Las tools `browser_*` (ver `app/tools/browser.py`) usan el Microsoft Edge que
ya viene instalado en Windows (`channel="msedge"` de Playwright), no un
Chromium aparte para descargar — no hace falta correr `playwright install`.
Se eligió así porque el Chromium propio de Playwright no viene firmado, y en
sistemas con cierto software de seguridad activo eso puede hacer fallar su
arranque en Windows con `BrowserType.launch: spawn UNKNOWN` (Windows no logra
activar el manifiesto interno del ejecutable). El Edge del sistema sí está
firmado y no tiene ese problema.

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
  no solo UI). Gateada por `PHONE_SHELL_ENABLED`. Ver sección de seguridad más abajo.
- `app/audit_log.py` — log de auditoría estructurado (JSON por línea, rotado
  por tamaño en `backend/audit.log`, gitignored) de cada tool call de celular
  y de escritorio, aparte del logging general de texto libre. Ver sección de
  seguridad.
- `app/tools/_comfyui_shared.py` — infraestructura común de `generate_image` y
  `generate_video` (no es una tool en sí): arranque/parada del proceso de
  ComfyUI (stdout/stderr a `backend/comfyui.log`, gitignored), coordinación de
  VRAM con Ollama (se descarga el modelo de texto antes de generar y se
  recarga al terminar, ya que compiten por la misma GPU), y el ciclo
  encolar-esperar-extraer resultado contra la API HTTP de ComfyUI
  (`127.0.0.1:8188` por default).
- `app/tools/image_gen.py` — `generate_image`: imagen a partir de texto con
  Flux.1 Schnell (GGUF Q4_K_S) vía ComfyUI. Rápido (una sola pasada de
  KSampler, 4 pasos), pero corre en la misma GPU ajustada de VRAM que el resto
  — ver nota de estabilidad de ComfyUI en seguridad/notas conocidas más abajo.
  **Deshabilitada, no importada en `tools/__init__.py` (ver ahí el porqué).**
- `app/tools/video_gen.py` — `generate_video`: clip corto (1 a 5s) con Wan 2.2
  (workflow de dos expertos, high/low noise) vía ComfyUI. Lento (varios
  minutos, medido entre ~4.3 y ~14 min para 1s de clip) y con el mismo
  encolar-esperar-extraer de `_comfyui_shared.py`. **Deshabilitada, no
  importada en `tools/__init__.py` (ver ahí el porqué).**
- `app/tools/reflect.py` — `jarvis_reflect`: memoria de reflexión del propio
  agente (`action="save"`/`"query"`), un JSONL append-only
  (`backend/reflections.jsonl`, gitignored — puede contener notas personales
  del usuario) con búsqueda simple por superposición de palabras. Para que el
  modelo recuerde decisiones no triviales entre conversaciones que no
  comparten historial.
- `app/codebase/` — indexado estructural de repos: `languages.py` (detección
  por extensión + mapeo a gramáticas de tree-sitter), `symbol_queries.py`
  (una query de tree-sitter por lenguaje soportado), `indexer.py` (recorre el
  árbol respetando `.gitignore`, extrae funciones/clases/imports vía
  tree-sitter o, si el lenguaje no tiene grammar soportada, un fallback
  regex genérico), `store.py` (cachea el índice en JSON bajo
  `settings.codebase_index_dir`, gitignored). Módulo interno, no envuelve
  ningún proceso externo.
- `app/tools/codebase.py` — `codebase_index_project`, `codebase_search_symbol`,
  `codebase_file_outline`. Solo lectura, no sandboxeadas a `FS_ALLOWED_ROOT`
  (el usuario puede pedir analizar cualquier repo del disco).
- `app/routers/codebase.py` — `GET /api/codebase/index` y `/recent`, para la
  pestaña "Codebase" de la ventana de PC (`tray-app/ui/codebase_view.py`).
- `app/obsidian/vault.py` — vault de notas estilo Obsidian: archivos Markdown
  reales con frontmatter YAML, en carpetas separadas por autor
  (`obsidian_vault/jarvis/`, `obsidian_vault/human/`, gitignored). Evolución
  más rica de `jarvis_reflect` (que queda intacto, para notas de una sola
  línea).
- `app/tools/obsidian.py` — `obsidian_save_note` (siempre autor "jarvis" --
  la tool no expone el parámetro `author`, así el modelo no puede escribir
  notas humanas), `obsidian_search_notes`, `obsidian_list_notes`.
- `app/routers/obsidian.py` — CRUD de notas humanas para la pestaña
  "Obsidian" de la ventana de PC (`tray-app/ui/obsidian_view.py`); el POST
  está fijado a autor "human", es el único punto de escritura de la UI.
- `app/tools/reflect.py` — `jarvis_reflect`: memoria de reflexión del propio
  agente (`action="save"`/`"query"`), un JSONL append-only
  (`backend/reflections.jsonl`, gitignored — puede contener notas personales
  del usuario) con búsqueda simple por superposición de palabras. Para que el
  modelo recuerde decisiones no triviales entre conversaciones que no
  comparten historial.
- `app/security/` — Fase 1 del roadmap de "profesiones" de Jarvis: centinela de
  seguridad de código. `scanners.py` (wrappers de subprocess sobre Semgrep,
  Bandit, cppcheck, clang-tidy y Trivy reales -- no reimplementa ningún
  analizador, el LLM no debe "adivinar" vulnerabilidades por su cuenta),
  `runner.py` (decide qué escáner correr según los lenguajes que ya detectó
  `app/codebase/`: Semgrep siempre, Bandit solo si hay Python, cppcheck solo
  si hay C/C++ (Semgrep `--config auto` casi no tiene reglas efectivas para
  ese stack, confirmado real auditando Luanti el 2026-07-29: 0 hallazgos por
  falta de herramienta, no de bugs), clang-tidy además si hay C/C++ Y el
  proyecto trae un `compile_commands.json` real (dataflow interprocedural
  real vía `clang-analyzer-*`, más profundo que cppcheck -- pero a propósito
  NUNCA corre sin compilation database: sin las flags de include/macros
  reales, clang-tidy no puede parsear ni un solo `#include` de la librería
  estándar, confirmado real el 2026-07-30 -- ver el docstring de
  `run_clang_tidy`), Trivy si el binario está instalado -- no viene por pip,
  instalación aparte), `store.py` (cachea el último escaneo por
  proyecto en `settings.security_scan_dir`, gitignored, para que
  `security_apply_fix` pueda resolver un `finding_id` sin re-escanear),
  `fixer.py` (aplica un fix puntual: dry-run con diff por default, y si se
  confirma, escribe + commitea SOLO ese archivo en un commit propio y
  reversible con `git revert`, sin tocar nada más que esté en stage).
- `app/tools/security_scan.py` — `security_scan_project`, `security_get_finding`,
  `security_apply_fix`. El flujo esperado: escanear (herramienta real) →
  interpretar cada hallazgo consultando `obsidian_search_notes` (la base de
  conocimiento de ciberseguridad ya tiene notas por vulnerabilidad/OWASP/cómo
  leer falsos positivos de cada escáner) → si hay fix seguro, aplicarlo con
  `confirm=true` recién en una segunda llamada explícita, nunca de una.
- `app/main.py` — endpoints `GET /api/health` y `POST /api/chat`.

## Agregar una tool nueva

1. Crear (o reusar) un módulo en `app/tools/`.
2. Definir una función sync o async, decorada con `@register_tool(name=..., description=..., parameters=<json-schema>)`.
3. Importar el módulo al final de `app/tools/__init__.py` si es un archivo nuevo.

No hace falta tocar `agent.py` ni `main.py`: el agente arma los schemas y despacha
las tool calls automáticamente contra el registry.

## Limitaciones conocidas

- **`generate_image`/`generate_video` están deshabilitadas por precaución de
  hardware, no reactivar sin investigar primero.** El 2026-07-27 la PC se
  apagó **físicamente** (no un crash de proceso) al menos dos veces,
  coincidiendo al segundo con el arranque de una de estas dos tools
  (confirmado cruzando `backend.log` contra el Event Log de Windows, Event
  ID 41/6008), más un patrón de apagados similares en días previos. Se
  comentaron los imports en `app/tools/__init__.py` (código intacto,
  reactivable con dos líneas) hasta entender si es térmico, de fuente de
  poder, o un crash de driver forzando un reset de hardware. Ver
  `INFORME_COMPLETO.md`, sección 4.5, para el detalle completo con
  timestamps y evidencia.
- **ComfyUI puede crashear a nivel nativo (sin traceback de Python) si se le
  piden dos generaciones seguidas o en paralelo**, confirmado en la práctica
  con `backend/comfyui.log`: la primera generación termina bien (el warning
  `MIOpen: CK grouped conv library not found for device gfx1031` es ruido,
  no fatal — esa corrida completó igual), pero al arrancar la siguiente
  generación justo después el proceso muere sin ningún error ni excepción
  Python, solo silencio. Causa más probable: `gfx1031` (RX 6700 XT) no está
  oficialmente soportado por ROCm (ver el comentario de `COMFYUI_PYTHON_PATH`
  en `config.py`), y esta GPU ya tiene un historial de access violations reales
  con ciertos builds de PyTorch+ROCm.
  - **Mitigado, no solucionado** (no se puede arreglar un crash de driver
    desde Python): `_comfyui_shared.wait_for_result` ahora corta la espera en
    ~15s con un error claro tras 3 fallas de conexión seguidas al pollear
    `/history`, en vez de colgar el chat hasta `COMFYUI_GENERATION_TIMEOUT_IMAGE`
    (default 600s) esperando una respuesta que ya no va a llegar.
  - También se encontró y arregló un bug real aparte: si el proceso anterior
    quedaba zombie (crasheado pero sin liberar el lock de SQLite),
    `start_comfyui_process()` fallaba al arrancar uno nuevo con `Could not
    acquire lock on database 'comfyui.db'`. Ahora mata cualquier proceso de
    ComfyUI que haya quedado vivo pero sin responder por HTTP antes de
    arrancar uno nuevo.
  - **Recomendación práctica**: evitar pedirle a Jarvis dos
    `generate_image`/`generate_video` seguidos sin esperar a que el primero
    termine — un ciclo único confirmado end-to-end (HTTP 200 + archivo real
    en disco) funciona bien.
  - `start_comfyui_process()` manda stdout/stderr de ComfyUI a
    `backend/comfyui.log` (gitignored) para diagnosticar el próximo crash.

## Notas de seguridad

- El backend no valida quién está del otro lado más allá del Bearer token: la
  barrera principal es que solo es alcanzable a través de tu tailnet.
- **Log de auditoría persistente y estructurado** (`app/audit_log.py`): cada
  tool call de celular (`phone_link.dispatch_to_phone`, todas las `phone_*`,
  no solo `phone_run_command`) y de escritorio (`tools/desktop._audited`)
  queda registrada como una línea JSON en `backend/audit.log` (gitignored),
  con timestamp UTC, tool, argumentos, y resultado o error — rota a los 5MB
  x 5 archivos. Es aparte del logging general de texto libre
  (`logging_config.py`, que solo persiste si corrés vía `tray-app` — ver
  `tray-app/README.md`); este log de auditoría persiste siempre,
  independientemente de cómo arranques el backend.
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
- **Blocklist de comandos/lanzamientos obviamente destructivos** —
  `phone_link._check_command_blocklist` (para `phone_run_command`: `rm -rf` de
  la raíz/home, `mkfs`, `dd` hacia un block device, fork bombs, `chmod`/`chown -R`
  sobre la raíz) y `desktop._check_launch_blocklist` (para `desktop_launch_app`:
  `format`, `diskpart`, `cipher /w`, `vssadmin delete`, `bcdedit`). **Esto es una
  mitigación de "evitar el desastre obvio" por matching de texto sobre patrones
  conocidos — no es un sandbox real ni una garantía de seguridad completa.**
  Cualquier comando/lanzamiento que no matchee esos patrones se ejecuta igual
  sin restricciones; un atacante (o el propio modelo, por error) puede lograr
  el mismo resultado destructivo por una ruta que el blocklist no cubra.
- **La conexión celular↔PC viaja en texto plano (`ws://`, no `wss://`) — TLS
  está preparado pero apagado (`TLS_ENABLED=false` default).** Ver
  `backend/certs/README.md`: hay un certificado self-signed listo para generar
  (`generate_cert.sh`) y soporte en `run.py`/`config.py` para servir HTTPS/WSS,
  pero activarlo corta la conexión actual de la app hasta actualizar su URL
  guardada Y hasta que Android confíe en el certificado (necesita un Network
  Security Config en la app, no es automático) — por diseño, no se activa sin
  coordinar el corte con el usuario presente. Mientras tanto, la ruta directa
  por LAN (sin pasar por Tailscale) es la que más expone esto: cualquier otro
  dispositivo en esa misma red Wi-Fi podría en teoría capturar el tráfico,
  incluida la API key en cada request. La ruta por Tailscale ya viaja cifrada
  por WireGuard a nivel de transporte, así que el riesgo real de esto es mucho
  menor mientras el celular y la PC no compartan la misma LAN.
