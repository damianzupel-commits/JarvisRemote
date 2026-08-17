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
- `PC_SHELL_ENABLED`: mismo criterio que `PHONE_SHELL_ENABLED` pero para
  `pc_run_command` (shell real en la PC, no solo tools puntuales). Default
  `true`.
- `SECURITY_SCAN_DIR` / `QUALITY_SCAN_DIR`: dónde se cachea el último escaneo
  de seguridad/calidad por proyecto (`app/security/`, `app/quality/`). Por
  default `backend/data/security_scans` y `backend/data/quality_scans`.
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
  `browser_select_option` (dropdowns nativos `<select>`, agregado 2026-08-16
  al toparse con uno real en el formulario de Nessus Essentials),
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
- `app/obsidian/embeddings.py` — memoria **semántica**, no solo keyword
  match: `search_notes` usa similitud coseno sobre embeddings como método
  principal (dos notas con el mismo significado pero palabras distintas se
  relacionan, ej. "contraseña en texto plano" ↔ "claves sin cifrar"), con
  overlap de palabras como fallback/complemento -- si el server de
  embeddings está caído, o una nota puntual nunca se indexó, esa nota sigue
  apareciendo por keyword, nunca desaparece de los resultados. Corre 100%
  local: pega contra un server OpenAI-compatible (`EMBEDDING_BASE_URL`,
  default `http://127.0.0.1:1234/v1` -- **no** el mismo host que
  `LMSTUDIO_BASE_URL` usa para chat, ver `app/config.py`) pidiendo el modelo
  de embeddings cargado ahí (`EMBEDDING_MODEL`, default
  `text-embedding-nomic-embed-text-v1.5`). Nada sale a una nube; si ese
  server no responde, `search_notes` degrada solo a keyword overlap (el
  comportamiento de siempre). Los vectores se guardan en un único JSON
  (`OBSIDIAN_EMBEDDINGS_PATH`, default `backend/data/obsidian_embeddings.json`,
  gitignored) -- para las ~50 notas de este vault no se justifica una base
  vectorial (Chroma/Pinecone), un archivo local con coseno vía numpy alcanza.
  `save_note`/`delete_note` mantienen el índice al día solos; `vault.reindex_all()`
  recalcula todo desde cero (backfill de notas viejas, o recuperación de un
  índice corrupto/vacío).
- `app/tools/obsidian.py` — `obsidian_save_note` (siempre autor "jarvis" --
  la tool no expone el parámetro `author`, así el modelo no puede escribir
  notas humanas), `obsidian_search_notes` (semántica + keyword, ver arriba),
  `obsidian_list_notes`.
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
  `security_apply_fix` pueda resolver un `finding_id` sin re-escanear).
- `app/quality/` — mismo esquema que `app/security/` pero para bugs/calidad
  general (no seguridad): `scanners.py`/`runner.py` corren Ruff/mypy siempre
  que hay Python (ESLint/tsc para JS/TS y detekt para Kotlin si están
  instalados aparte, no vienen por pip), `store.py` cachea en
  `settings.quality_scan_dir` (carpeta separada de la de seguridad).
- `app/findings/` — agrega los dos caches (seguridad + calidad) en un único
  índice de riesgo por archivo (`severity_index.py`, consumido por
  `GET /api/codebase/graph` y `/file` para el halo del grafo y el panel de
  hallazgos), con `noise.py` (ruido conocido por escáner que se excluye) y
  `binaries.py` (evita intentar escanear binarios).
- `app/codeedit/fixer.py` — aplica un fix de un solo archivo: dry-run con
  diff por default, y si se confirma, escribe + commitea SOLO ese archivo en
  un commit propio y reversible con `git revert`, sin tocar nada más que esté
  en stage. Usado tanto por `security_apply_fix`/`code_apply_fix` como por
  `fs_write_file` cuando el archivo cae dentro de un proyecto ya indexado.
- `app/tools/security_scan.py` — `security_scan_project`, `security_get_finding`,
  `security_apply_fix`. El flujo esperado: escanear (herramienta real) →
  interpretar cada hallazgo consultando `obsidian_search_notes` (la base de
  conocimiento de ciberseguridad ya tiene notas por vulnerabilidad/OWASP/cómo
  leer falsos positivos de cada escáner) → si hay fix seguro, aplicarlo con
  `confirm=true` recién en una segunda llamada explícita, nunca de una.
- `app/tools/quality_scan.py` — mismo flujo que `security_scan.py` pero para
  `app/quality/` (`quality_scan_project`, `quality_get_finding`,
  `quality_apply_fix`).
- `app/tools/code_edit.py` — `code_apply_fix`: mismo circuito de
  `app/codeedit/fixer.py` que las tools de seguridad/calidad, pero para
  ediciones puntuales que no vienen de un finding de escáner.
- `app/audit_report.py` / `app/tools/audit_report.py` — `audit_generate_report`:
  arma un resumen en Markdown (hallazgos de seguridad/calidad + fixes
  realmente aplicados, consultando `app/audit_log.py`) y lo guarda como nota
  del vault de Obsidian.
- `app/tools/pc_command.py` — `pc_run_command`: shell real y arbitrario en la
  PC (análogo de `phone_run_command` del lado de la PC, no solo tools
  puntuales -- instalar dependencias, correr tests/builds, git, etc.). Mismo
  criterio de blocklist + auditoría que el resto de las tools invasivas, gate
  en `PC_SHELL_ENABLED`.
- `app/forms/credential_store.py` + `app/tools/web_forms.py` — completar
  formularios/registros web reales (spec de Damian, 2026-08-16), reusando el
  MISMO navegador de `app/tools/browser.py` para el lado de interacción con
  la página. `browser_generate_password` genera contraseñas fuertes al azar
  (nunca elegidas por el LLM) y las persiste cifradas con DPAPI (mismo
  mecanismo que `investigation/keys.py`, nunca texto plano); `form_get_saved_credential`/
  `form_list_saved_credentials` las recuperan después. `browser_preview_submit`
  es el mismo patrón dry-run→`confirm=true` de `code_apply_fix`: siempre
  captura + resumen de los campos ANTES de tocar el botón de enviar, sin
  excepción. Ver sección de seguridad más abajo.
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
- **`pc_run_command` es el mismo nivel de riesgo que `phone_run_command`, pero
  del lado de la PC**: shell real y arbitrario (`cmd`/PowerShell según lo que
  resuelva el sistema), no acotado a tools puntuales. Gateada por
  `PC_SHELL_ENABLED=true` (default) y auditada vía `app/audit_log.py`.
- **Formularios/registros web (`app/forms/`, `app/tools/web_forms.py`, agregados
  2026-08-16, spec de Damian)** — Jarvis puede completar formularios y
  registrarse en sitios reales bajo pedido explícito, pensado para cuando
  Damian lo pide lejos de la PC (celular). Decisiones de diseño de la ronda de
  preguntas (todas confirmadas por Damian, mismo criterio que la ronda del
  módulo de malware):
  - **Contraseñas**: `browser_generate_password` las genera al azar (nunca el
    LLM elige/inventa una), completa el registro, y las muestra en el chat una
    vez (porque hace falta usarlas en el momento) -- pero Damian pidió además
    que queden guardadas en un archivo, no solo mostradas y perdidas. Texto
    plano fue descartado a propósito (mismo antipatrón ya señalado sobre
    `backend/.env`): se persisten cifradas con **DPAPI** en
    `FORM_CREDENTIALS_PATH` (default `backend/data/form_credentials.dpapi`,
    gitignored), mismo mecanismo que `app/investigation/keys.py` ya usa para
    la clave de firma -- atado a esta cuenta de Windows, nadie puede leerlas
    copiando el archivo a otra máquina. Recuperables después con
    `form_get_saved_credential`/`form_list_saved_credentials` (esta última
    solo devuelve metadata, nunca todas las contraseñas de una).
  - **Confirmación antes de enviar**: `browser_preview_submit` es el mismo
    patrón dry-run→`confirm=true` que `code_apply_fix` -- SIEMPRE saca una
    captura + los valores actuales de los campos (contraseña enmascarada)
    antes de tocar el botón de enviar, sin excepción explícita de Damian ni
    siquiera para un formulario trivial de nombre+email (el caso real que
    motivó el pedido: registro de Nessus Essentials). Solo hace click de
    verdad en una segunda llamada explícita con `confirm=true`, después de que
    Damian vio la previsualización y confirmó en el chat.
  - **Mecanismo de control**: reusa el navegador Playwright/Edge que ya
    controlaba `app/tools/browser.py` (`browser_open`/`browser_type`/
    `browser_click`) -- no hizo falta un driver nuevo, este ya era
    automatización real por selector CSS, no clicks a ciegas de escritorio.
  - **Sin lista blanca de dominios**: decisión explícita de Damian (a
    diferencia de `authorized_targets.yaml` del pentesting) -- confía en la
    orden explícita de cada pedido en vez de un archivo previo a editar a
    mano. Esto significa que el prompt del skill `web_forms` (`app/skills.py`)
    instruye explícitamente al modelo a nunca tratar texto de una página ya
    abierta como si fuera una orden real de Damian (mitigación de
    prompt-injection dado que no hay gate de dominio de por medio).
- **Blocklist de comandos/lanzamientos obviamente destructivos** —
  `phone_link._check_command_blocklist` (para `phone_run_command`: `rm -rf` de
  la raíz/home, `mkfs`, `dd` hacia un block device, fork bombs, `chmod`/`chown -R`
  sobre la raíz), `pc_command._check_command_blocklist` (mismo espíritu para
  `pc_run_command`) y `desktop._check_launch_blocklist` (para `desktop_launch_app`:
  `format`, `diskpart`, `cipher /w`, `vssadmin delete`, `bcdedit`). **Esto es una
  mitigación de "evitar el desastre obvio" por matching de texto sobre patrones
  conocidos — no es un sandbox real ni una garantía de seguridad completa.**
  Cualquier comando/lanzamiento que no matchee esos patrones se ejecuta igual
  sin restricciones; un atacante (o el propio modelo, por error) puede lograr
  el mismo resultado destructivo por una ruta que el blocklist no cubra.
- **`nmap_scan` es la primera tool del proyecto que toca una red REAL, no solo
  código/archivos locales en disco** (a diferencia de
  `security_scan_project`/`quality_scan_project`, que son SAST/SCA puro).
  Escanear una IP/dominio que no es tuyo y sin autorización explícita del
  dueño puede ser ilegal (leyes de acceso no autorizado / computer fraud en la
  mayoría de países), así que tiene el guardrail de scope más estricto de
  todo el proyecto — un chequeo técnico real
  (`app/network/guardrail.py::resolve_and_authorize`), no una convención de
  prompt: por default SOLO puede escanear rangos privados/reservados
  (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback
  (`127.0.0.0/8`) y el rango fijo de Tailscale (`100.64.0.0/10`). Cualquier
  IP/dominio público se rechaza antes de ejecutar nmap, salvo que esté en
  `backend/authorized_targets.yaml` (copiar de `authorized_targets.yaml.example`)
  o, retrocompatible, en `NMAP_AUTHORIZED_TARGETS` (`backend/.env`) — vacío
  por default, **solo el usuario lo llena a mano**; ni la tool ni el LLM
  pueden agregarse un target nuevo por ningún argumento de la tool call, y
  "el usuario dijo que sí en el chat" nunca es un camino de autorización
  válido. Desde 2026-08-13 `authorized_targets.yaml` es la fuente ÚNICA
  compartida por todas las tools de pentesting activo del proyecto (nmap,
  sqlmap, tshark, metasploit, zap, nessus a medida que se agregan) — un
  target ahí no necesita estar corriendo/alcanzable en este momento para
  estar autorizado (los laboratorios se levantan bajo demanda). Gateada
  además por `NMAP_ENABLED=true` (default; el guardrail de scope ya la hace
  segura por diseño aun con la tool prendida) y auditada vía
  `app/audit_log.py` (target/scan_type/aceptado-o-rechazado en cada intento).
  **Instalación de nmap: manual, no automatizable.** El instalador oficial de
  Windows (https://nmap.org/download.html) empaqueta el driver Npcap, que
  requiere un click de UAC para instalarse (un driver de captura de paquetes
  a nivel kernel no se puede instalar sin privilegios de administrador — no
  existe un build portable/sin-admin oficial que lo evite). Este proyecto no
  automatiza ese paso a propósito (mismo criterio que otras instalaciones que
  requieren UAC, ver limitaciones conocidas de Windows más abajo): corré el
  instalador vos mismo una vez, aceptando también instalar Npcap cuando lo
  pida. Sin Npcap, `nmap.exe` igual corre pero solo puede hacer TCP connect
  scan (`-sT`, vía WinSock normal) sin ping ICMP real ni SYN scan ni
  detección de SO — por eso todos los `scan_type` de `nmap_scan` usan
  `-sT -Pn` (ver `app/network/scanner.py`), para funcionar igual sin Npcap
  aunque se pierdan esas capacidades más avanzadas.
- **`phone_nmap_scan` es la contraparte de `nmap_scan` que escanea desde el
  CELULAR en vez de la PC** (ver `app/tools/network_scan.py`) — necesaria
  porque el backend corre en la PC de casa del usuario, que no tiene
  visibilidad de ninguna red a la que el celular esté conectado (dos redes
  físicas separadas, aunque el celular hable con Jarvis por Tailscale). Útil
  para auditar la red de un tercero (ej. la wifi de un local que dio la
  contraseña) sin instalar nada ni llevar una notebook: el escaneo corre
  desde el dispositivo que sí está en esa red. Comparte el MISMO guardrail de
  scope no negociable que `nmap_scan` (`resolve_and_authorize`) — correr
  desde el celular no lo relaja. No abre un canal nuevo del lado de Android:
  arma el comando de nmap en el backend y lo despacha reusando literalmente
  `phone_run_command`/Termux (`app/phone_link.py::dispatch_to_phone`), así que
  hereda sus mismos requisitos (Termux instalado desde F-Droid,
  `allow-external-apps=true`, permiso `RUN_COMMAND` otorgado,
  `PHONE_SHELL_ENABLED=true`) más uno propio: **el paquete `nmap` de Termux
  tiene que estar instalado a mano** (`pkg install nmap` dentro de Termux, no
  necesita root — soporta TCP connect scan y NSE, no SYN scan/detección de
  SO, misma limitación que la PC sin Npcap). Si falta, la tool falla con un
  mensaje explícito en vez de asumir que corrió.
- **`sqlmap_scan` (agregada 2026-08-13) es la primera tool de PENTESTING
  ACTIVO del proyecto** (ver `app/pentest/`, `app/tools/pentest_sqlmap.py`) —
  a diferencia de `nmap_scan` (reconocimiento pasivo, nunca envía payloads),
  esta SÍ envía payloads de inyección SQL reales contra el target. Comparte
  el mismo guardrail de scope no negociable de `nmap_scan`
  (`app/network/guardrail.py::resolve_and_authorize`), validado sobre el
  HOST extraído de la URL antes de tocar nada. Wrapper vía la REST API real
  de SQLMap (`sqlmapapi.py`, HTTP Basic Auth con credenciales generadas una
  vez y persistidas en `sqlmap_api_credentials.json`, gitignored) en vez de
  parsear el stdout de texto libre del CLI — mismo motivo que `nmap -oX -`:
  salida estructurada real, no texto para adivinar. Server SOLO en
  `127.0.0.1`, arrancado on-demand por Jarvis si no está corriendo ya.
  Preset cerrado de `scan_type` (`detect`/`enumerate`), nunca flags libres
  de SQLMap ni un preset de volcado de datos reales — el propósito es
  demostrar/documentar una vulnerabilidad para un reporte, no exfiltrar
  información. **Instalación de sqlmap: manual, pero SIN UAC/admin** (a
  diferencia de nmap/Npcap) — es pura Python: `git clone --depth 1
  https://github.com/sqlmapproject/sqlmap.git` y apuntar `SQLMAP_PATH` al
  `sqlmap.py` resultante (default: `~/sqlmap-dev/sqlmap.py`). Descubrimiento
  real de correr esto en Windows: el CLI de sqlmap necesita `--non-interactive`
  además de `--batch` para no colgarse en un prompt de protección contra
  doble-click (dos guardas de interactividad distintas) — la REST API
  (`sqlmapapi.py -s`) no lo dispara, así que el wrapper no necesita pasarlo.
  Validado en vivo contra un target local deliberadamente vulnerable:
  detección positiva real de 4 técnicas (boolean-based blind, error-based,
  time-based blind, UNION query) con DBMS identificado correctamente.
- **`packet_capture_scan`/`packet_capture_analyze` (agregadas 2026-08-13,
  "Wireshark" en la spec) implementadas con `scapy` (pip puro), NO
  shelleando a `tshark.exe`** — decisión de diseño tomada durante la
  implementación (no estaba en la propuesta original): analizar un `.pcap`
  ya existente no necesita NADA además de `pip install scapy` (validado en
  vivo: escribir/leer un `.pcap` real funciona sin Npcap instalado), así
  que `packet_capture_analyze` no tiene ninguna dependencia de instalación
  manual. `packet_capture_scan` (captura EN VIVO) sí sigue necesitando
  Npcap — limitación real de Windows, no de la librería (mismo click de
  UAC que nmap: https://npcap.com/#download). Guardrail ADAPTADO del resto
  del módulo: acá no hay un solo target remoto, hay una interfaz de red
  LOCAL que puede exponer tráfico de otros dispositivos — `host_filter` es
  obligatorio y nunca puede estar vacío, cada host pasa por el mismo
  `authorized_targets.yaml` compartido, armando un filtro BPF real; nunca
  se ofrece captura sin acotar de "todo lo que pasa por la interfaz".
  Verificado en dos capas independientes (defense-in-depth real, mismo
  bug ya evitado en `pentest_sqlmap.py`): tanto la tool como
  `packet_capture.capture_packets` validan el guardrail por separado, no
  solo una de las dos. `packet_capture_analyze` (sobre un `.pcap` ya
  existente) no tiene gate de target — analizar un archivo que ya tenés no
  es una acción contra un sistema real.
- **`zap_scan` (agregada 2026-08-13, checkpoint 5) usa OWASP ZAP en vez de
  Burp Suite Pro** (decisión de Damian: Burp Pro necesita licencia paga que
  no tiene, ZAP es gratis y tiene REST API completa). Mismo guardrail
  compartido de `resolve_and_authorize`, validado sobre el HOST de la URL,
  y mismo fix de pinneo a la IP resuelta para cerrar la ventana de DNS
  rebinding (ver `pentest_sqlmap.py`) — con una limitación real y
  documentada: a diferencia de sqlmap, no preserva un header `Host:`
  override (existiría vía el addon Replacer de ZAP, complejidad real no
  justificada para el caso de uso actual), así que targets de hosting
  virtual por nombre no están soportados todavía. **Instalación: manual,
  SIN UAC/admin** — ZAP se distribuye como zip "Crossplatform" (necesita
  Java 11+, ya presente en esta máquina): descargar desde
  https://github.com/zaproxy/zaproxy/releases/latest y apuntar `ZAP_PATH`
  al `zap-X.Y.Z.jar` resultante (default: `~/zap-2.17.0/zap-2.17.0.jar`).
  Descubrimiento real de correr esto en Windows: el PRIMER arranque de un
  ZAP recién descomprimido descarga e instala addons bundleados (~34s
  reales medidos); arranques siguientes, con addons ya cacheados, tardan
  ~1s real — confirmado con dos arranques consecutivos, no un supuesto.
  `scan_type='spider'` (default) solo crawlea + scan pasivo, nunca envía
  un payload de ataque; `'full'` además corre el scan activo real. Validado
  en vivo contra un target local deliberadamente vulnerable (XSS reflejado
  real): detección positiva real de "Cross Site Scripting (Reflected)"
  (risk=High, evidence=el payload real reflejado), más varios hallazgos
  reales de Medium/Low (headers de seguridad faltantes, versión de
  servidor filtrada) — 12 alertas reales en total, ninguna inventada;
  cubierto además por un test de integración real y automatizado (se
  salta si ZAP no está instalado).
- **Protección contra malware (`app/malware/`, agregada 2026-08-16, spec de Damian ampliada de "auditar código"
  a "proteger la PC real")** — detección real (YARA + ClamAV + heurística conductual, los tres desde el
  arranque, no en fases) sobre el resto de la PC, MÁS auto-protección de la propia instalación de Jarvis.
  Cada hallazgo real queda con el mismo rigor forense que el módulo de investigación: mismo `artifact_store`
  content-addressed por SHA-256 y mismo log firmado Ed25519 (`app/investigation/keys.py`/`log.py`), pero en
  su propio archivo/dominio — no entra al flujo de "casos" de investigación.
  - **YARA**: wheel con libyara embebida (`yara-python`), sin instalación aparte ni UAC. Set de reglas propio
    en `app/malware/rules/starter.yar` (EICAR, dropper de PowerShell, nota de ransomware, webshell PHP, robo
    de credenciales de navegador, persistencia por Registro) — sumar reglas de terceros (ej.
    github.com/Yara-Rules/rules) es tirar archivos `.yar`/`.yara` sueltos en esa misma carpeta, sin tocar
    código. **Validado en vivo real**: EICAR, patrón de dropper y patrón de nota de ransomware confirmados
    con matches reales (ver `tests/test_malware_yara_scanner.py`).
  - **ClamAV**: motor de firmas masivo vía el daemon `clamd` — **instalación manual, con UAC**:
    1. Instalador oficial: https://www.clamav.net/downloads (Windows installer).
    2. Durante la instalación, dejar que configure el servicio de Windows escuchando por TCP (`clamd.conf`:
       `TCPSocket 3310`, `TCPAddr 127.0.0.1`, y comentar la línea `Example` que bloquea el arranque por
       default si el instalador la deja sin comentar).
    3. Correr `freshclam.exe` (o el servicio "ClamAV FreshClam") al menos una vez para bajar la base de
       firmas real (varios cientos de MB la primera vez).
    4. Iniciar/reiniciar el servicio "ClamAV" en `services.msc`.
    5. Nada más de configurar del lado de Jarvis — `CLAMAV_ENABLED=true`, `CLAMD_HOST`/`CLAMD_PORT` en
       `backend/.env.example` ya apuntan a `127.0.0.1:3310`, el default del instalador.
    **No se pudo validar en vivo** (ClamAV no está instalado en la PC de desarrollo) — sin `clamd` corriendo,
    `malware_scan_path`/el escaneo on-access/diario siguen funcionando con YARA + heurística conductual
    solamente, ClamAV se salta con un aviso explícito (`ClamAVUnavailableError`), nunca se confunde con
    "escaneó y no encontró nada".
  - **Heurística conductual + escaneo on-access** (`watchdog` sobre Descargas/Escritorio/Temp): cada archivo
    nuevo se escanea al instante, y un patrón de muchos archivos modificados/renombrados en poco tiempo con
    entropía alta (típico de ransomware cifrando) dispara una alerta fuerte al log firmado — sin identificar
    ni poder matar el proceso responsable (limitación real, requeriría correlación a nivel de kernel).
    **Validado en vivo real de punta a punta**: un archivo dejado en una carpeta vigilada fue detectado por
    YARA, movido a cuarentena, y el evento verificado en el log firmado, todo automático.
  - **Escaneo completo diario** de `FS_ALLOWED_ROOT` (la carpeta de usuario — NO litealmente `C:\`, que sería
    enormemente más lento y en su mayoría archivos de sistema que Windows Defender ya cubre), corrido por un
    loop en background del propio backend (`app/malware/fullscan.py`), sin Task Scheduler de Windows.
  - **Cuarentena reversible por default** (mueve, nunca borra) — borrado definitivo requiere `confirm=true`
    explícito (`malware_quarantine_delete`), mismo patrón dry-run→confirm que `code_apply_fix`.
  - **VirusTotal**: confirmación SELECTIVA de hashes ya sospechosos localmente (nunca proactiva sobre todo el
    disco — la cuota gratis, 4 consultas/min, no lo bancaría con el escaneo diario ya prendido), y solo manda
    el hash SHA-256, nunca el contenido del archivo. Sacar una API key gratis: crear cuenta en
    https://www.virustotal.com/gui/join-us → perfil → "API Key" → pegarla en `VIRUSTOTAL_API_KEY` en
    `backend/.env`.
  - **Auto-protección parte A (FIM)**: hashea y vigila `authorized_targets.yaml`, la clave de firma Ed25519,
    `.env`, y el código de `app/` entero contra un baseline — **validado en vivo real** (modificación,
    borrado, y archivo nuevo bajo una carpeta vigilada, los tres detectados correctamente).
  - **Auto-protección parte B**: `psutil` sobre el propio proceso — hijos inesperados (fuera de una
    allowlist de binarios que el proyecto conoce que lanza) y conexiones salientes a puertos inusuales.
    Limitación real, dicha explícita: no verifica firma de binarios (un proceso que se hace pasar por un
    nombre de la allowlist no se detecta), y no distingue C2 real sobre HTTPS 443 de tráfico legítimo.
  - **Auto-protección parte C, EXPERIMENTAL (Damian la pidió a pesar de la advertencia explícita de que no
    es alcanzable con la misma calidad que A/B con recursos de un solo dev)**: detección tipo EDR real
    (acceso a memoria del propio proceso, hilos remotos inyectados) leyendo el Event Log de Sysmon —
    **sin escribir un driver de kernel propio**, apoyada en el driver YA FIRMADO por Microsoft que instala
    Sysmon. **Instalación manual**:
    1. Descargar Sysmon: https://learn.microsoft.com/sysinternals/downloads/sysmon.
    2. (Recomendado, para no ahogarse en ruido) usar una config curada conocida, ej.
       https://github.com/SwiftOnSecurity/sysmon-config (`sysmonconfig-export.xml`).
    3. Instalar con UAC: `sysmon64.exe -accepteula -i sysmonconfig-export.xml`.
    4. Confirmar en el Visor de eventos (Registros de aplicaciones y servicios → Microsoft → Windows →
       Sysmon → Operational) que hay eventos.
    5. `SYSMON_ENABLED=true` en `backend/.env`, reiniciar el backend.
    **No se pudo validar en vivo** (Sysmon no está instalado en la PC de desarrollo) — el código está escrito
    contra el esquema de eventos real y documentado de Sysmon (Event ID 10 ProcessAccess, Event ID 8
    CreateRemoteThread) y ambos caminos de error (capa apagada, canal inexistente) se confirmaron gracefully
    contra el Event Log real de esta máquina, pero la PRIMERA corrida con Sysmon de verdad instalado es la
    que confirma si detecta como está escrito. `ProcessAccess` es conocido por ser ruidoso incluso en SOCs
    profesionales — si la señal resulta poco útil en la práctica, la recomendación pasa a desactivarla
    (`SYSMON_ENABLED=false`) y quedarse con A+B, que sí son sólidas.
  - **Hallazgo real durante el desarrollo, no un bug de Jarvis**: al probar con el string EICAR real y con un
    patrón de dropper de PowerShell, Windows Defender interceptó esos archivos de prueba EN TIEMPO REAL antes
    de que el propio motor de Jarvis pudiera releerlos (`OSError: [Errno 22] Invalid argument` al reintentar
    abrirlos) — Defender le ganó la carrera de lectura. No es una falla: confirma que las dos capas de
    defensa conviven sin pisarse (Jarvis sigue aportando valor real en lo que Defender no reconoce, como las
    reglas YARA propias o contenido por debajo de su umbral heurístico).
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
