# Informe completo — JarvisRemote

> **Estado de este documento:** completo. Secciones 1–8 son el estado
> técnico que Claude conoce de primera mano —código leído, tests corridos,
> bugs diagnosticados y arreglados en esta sesión, todo verificado contra
> el repo real, no de memoria. Sección 9 es el resumen narrativo del
> usuario (arquitectura, decisiones de seguridad, pasos manuales
> pendientes, lecciones operativas).

**Fecha:** 2026-07-20
**Estado del backend en este momento:** corriendo, estable, `phone_connected: true`, working tree de git limpio (todo lo de esta sesión está commiteado).

---

## 1. Qué es JarvisRemote (resumen técnico)

Un asistente LLM local (corre en LM Studio, modelo de 30B, API OpenAI-compatible en `localhost:1234`) al que se le puede pedir que ejecute acciones reales tanto en la PC (Windows) como en un celular Android conectado, desde una app Android o desde una ventana de chat en la PC (tray-app). Tres componentes:

- **`backend/`** — FastAPI + Python. Habla con LM Studio, corre el loop del agente (tool calling), expone `POST /api/chat`, `GET /api/health`, y `WS /ws/phone`.
- **`tray-app/`** — Python + pystray. Administra el backend como subproceso (arrancar/parar/logs) y ahora también tiene una ventana de chat propia (Tkinter) para hablarle a Jarvis desde la PC.
- **`android-app/`** — Kotlin + Jetpack Compose. Chat contra el backend + control total del celular (Accessibility Service + filesystem SAF) vía una conexión WebSocket saliente mantenida por un foreground service.

---

## 2. Estructura exacta del repo

```
JarvisRemote/
├── README.md
├── INFORME_COMPLETO.md          (este archivo)
│
├── backend/
│   ├── README.md
│   ├── run.py                    # entrypoint: uvicorn.run("app.main:app", ...)
│   ├── requirements.txt / requirements-dev.txt
│   ├── pytest.ini
│   ├── .env / .env.example
│   ├── .venv/                    # venv del backend (Python 3.12 base)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app: /api/health, /api/chat, /ws/phone
│   │   ├── agent.py              # loop del agente (system prompt, tool-calling loop)
│   │   ├── llm_client.py         # cliente OpenAI/AsyncOpenAI apuntando a LM Studio
│   │   ├── config.py             # Settings desde .env
│   │   ├── auth.py               # verify_api_key (Bearer token)
│   │   ├── models.py             # ChatRequest/ChatResponse/ToolCallLog (pydantic)
│   │   ├── network_info.py       # detección/clasificación de IPs (hotspot/lan/tailscale)
│   │   ├── phone_link.py         # estado de la conexión WS del celular + dispatch de tool calls
│   │   ├── logging_config.py     # logging.basicConfig, nivel INFO
│   │   └── tools/
│   │       ├── __init__.py       # registry: register_tool / get_tools / openai_tool_schemas / call_tool
│   │       ├── filesystem.py     # fs_* (PC)
│   │       ├── browser.py        # browser_* (PC, Playwright/Chromium)
│   │       └── phone.py          # phone_* (celular, despachadas por WS)
│   └── tests/
│       ├── conftest.py
│       ├── test_smoke.py
│       ├── test_tools_registry.py
│       ├── test_phone_link.py
│       └── test_phone_ws_endpoint.py
│
├── tray-app/
│   ├── README.md
│   ├── tray.py                   # ícono de bandeja, menú, poll de salud
│   ├── config.py                 # lee backend/.env, arma BASE_URL/HEALTH_URL/CHAT_URL/API_KEY
│   ├── process_manager.py        # start()/stop()/is_running() sobre el backend como subproceso
│   ├── icon.py                   # dibuja el ícono con Pillow
│   ├── chat_window.py            # ventana de chat (Tkinter) contra POST /api/chat
│   ├── requirements.txt
│   └── backend.log               # log del backend SOLO si se arrancó vía tray (ver sección 7)
│
└── android-app/
    ├── README.md
    ├── SETUP_RAPIDO.md            # guía sin Android Studio: setup-android-sdk.ps1 + deploy.ps1
    ├── setup-android-sdk.ps1      # instala JDK 17 (Temurin) + Android SDK cmdline-tools
    ├── deploy.ps1                 # build + install + habilita Accessibility Service por adb
    ├── build.gradle.kts / settings.gradle.kts / gradle.properties
    ├── gradle/libs.versions.toml
    └── app/
        ├── build.gradle.kts       # applicationId com.jarvisremote.app
        └── src/main/
            ├── AndroidManifest.xml
            ├── java/com/jarvisremote/app/
            │   ├── MainActivity.kt
            │   ├── JarvisApp.kt              # NavHost: settings <-> chat
            │   ├── data/
            │   │   ├── NetworkModels.kt       # kotlinx.serialization
            │   │   ├── BackendApi.kt          # Retrofit: GET /api/health, POST /api/chat
            │   │   ├── ApiClientProvider.kt
            │   │   ├── SettingsRepository.kt  # DataStore: backend_url, api_key, conversation_id,
            │   │   │                          # phone_folder_uri, phone_link_enabled
            │   │   ├── ChatRepository.kt
            │   │   └── NetworkError.kt
            │   ├── phone/
            │   │   ├── PhoneLinkService.kt     # foreground service, WS saliente a /ws/phone
            │   │   ├── JarvisAccessibilityService.kt
            │   │   ├── SafFileStore.kt         # filesystem sandboxeado (SAF)
            │   │   ├── PhoneToolHandler.kt     # router de tool calls recibidas
            │   │   ├── ToolCallModels.kt
            │   │   ├── AccessibilityUtils.kt
            │   │   └── BootReceiver.kt         # relanza el service tras reboot si estaba on
            │   └── ui/
            │       ├── theme/
            │       ├── chat/ (ChatScreen.kt, ChatViewModel.kt, ChatMessage.kt)
            │       └── settings/ (SettingsScreen.kt, SettingsViewModel.kt)
            └── res/ (values, xml/accessibility_service_config.xml, drawable, mipmap)
```

---

## 3. Tools registradas (las 21, con parámetros exactos)

Confirmado corriendo `openai_tool_schemas()` directamente contra el código — esta es la lista real que se le manda a LM Studio en cada request, siempre completa, sin condicionar por si hay celular conectado o no (ver bug #1 más abajo).

### PC — filesystem (`backend/app/tools/filesystem.py`), sandboxeadas a `FS_ALLOWED_ROOT`

| Tool | Parámetros | Notas |
|---|---|---|
| `fs_list_dir` | `path?` (default `.`) | Lista archivos/subcarpetas en la PC |
| `fs_read_file` | `path`, `max_chars?` (default 20000) | Lee texto |
| `fs_write_file` | `path`, `content`, `append?` (default false) | Crea carpetas intermedias si hace falta |
| `fs_create_dir` | `path` | — |
| `fs_move_path` | `source`, `destination` | Mueve/renombra |
| `fs_delete_path` | `path` | **Deshabilitada por default**, requiere `FS_ALLOW_DELETE=true` en `.env` |

Todas las descripciones dicen explícitamente "en la PC del usuario" (agregado en esta sesión, ver sección 5).

### PC — browser (`backend/app/tools/browser.py`), Playwright/Chromium, una página persistente entre llamadas

| Tool | Parámetros | Notas |
|---|---|---|
| `browser_open` | `url` | Lanza Chromium si no está corriendo. Descripción aclara: "navegador... en la PC... no para abrir apps del celular" |
| `browser_click` | `selector` (CSS) | timeout 5000ms |
| `browser_type` | `selector`, `text`, `submit?` (default false) | `submit=true` presiona Enter |
| `browser_get_text` | `selector?` (default `body`) | Trunca a 8000 chars |
| `browser_screenshot` | `path?` (default `last_screenshot.png`) | — |
| `browser_close` | — | Libera el browser/page |

### Celular (`backend/app/tools/phone.py`), `target="phone"`, despachadas por WS a `/ws/phone`

Los handlers de estas 9 tools nunca se ejecutan de verdad en el backend — `call_tool()` intercepta por `target` y llama a `phone_link.dispatch_to_phone()`, que manda el tool call por WebSocket al celular y espera la respuesta correlacionada por `id` (timeout default `PHONE_TOOL_TIMEOUT=30s`, configurable en `.env`).

| Tool | Parámetros | Notas |
|---|---|---|
| `phone_open_app` | `package_name` | Descripción (ajustada en esta sesión): "en el CELULAR del usuario (Android)... no usar para abrir programas o sitios web en la PC" |
| `phone_list_dir` | `path?` (default `.`) | Sandboxeado a la carpeta SAF elegida por el usuario |
| `phone_read_file` | `path`, `max_chars?` (default 20000) | — |
| `phone_write_file` | `path`, `content`, `append?` (default false) | — |
| `phone_tap` | `x`, `y` (int, píxeles) | Vía Accessibility Service |
| `phone_swipe` | `x1`, `y1`, `x2`, `y2`, `duration_ms?` (default 300) | — |
| `phone_type_text` | `text` | Requiere un campo con foco (usar `phone_tap` antes si hace falta) |
| `phone_read_screen` | — | Devuelve texto/descripciones/posiciones/clickeable de todos los nodos en pantalla |
| `phone_global_action` | `action` (enum: `back`, `home`, `recents`, `notifications`) | — |

**Nota de seguridad ya conocida:** el Accessibility Service puede leer y accionar sobre *cualquier app visible en pantalla*, incluidas apps de banca, 2FA, mensajería. No hay forma de acotar ese alcance a nivel Android.

---

## 4. Bug #1 — Historial de conversación contaminado (SYSTEM_PROMPT estático)

**Síntoma reportado:** pidiendo "abre la calculadora en mi celular" (sin ambigüedad), el modelo respondió *"No tengo acceso al celular del usuario en este momento..."* y ni siquiera intentó llamar a ninguna tool `phone_*`, a pesar de que el celular estaba realmente conectado (`phone_connected: true`).

**Investigación (antes de tocar código, con evidencia):**
1. Se confirmó que `openai_tool_schemas()` manda las 21 tools **siempre**, sin ningún chequeo de `is_phone_connected()` — descartado que fuera un bug de qué tools se envían.
2. Se probó el mismo pedido con un `conversation_id` **nuevo**: el modelo llamó correctamente a `phone_open_app`. Esto probó que el problema no era estructural sino específico de esa conversación puntual.
3. Se le pidió al modelo, usando el `conversation_id` real de la app, que resumiera qué había dicho antes sobre el acceso al celular. Su propio resumen reveló la causa: en un turno anterior de esa misma conversación había dicho *"No tengo acceso al celular"* (probablemente cuando el celular aún no estaba conectado o el modelo dudó), y en turnos siguientes repetía esa misma afirmación citándose a sí mismo, sin importar el estado real ni las tools disponibles.

**Causa raíz:** `backend/app/agent.py` guarda el historial completo por `conversation_id` en un diccionario en memoria (`_conversations`), **para siempre, sin expirar ni corregirse**. El `SYSTEM_PROMPT` es una constante fija con lenguaje condicional ("—si hay un celular conectado—") que nunca se actualiza con el estado real en el momento de cada request. Una vez que el modelo genera una afirmación falsa, esa afirmación queda fija en el historial y el modelo la trata como hecho consumado en turnos futuros (autoconsistencia).

**Fix aplicado** (commit `91163d3`): cada llamada a LM Studio ahora suma una nota de sistema fresca —calculada de nuevo en cada vuelta del loop del agente, con `is_phone_connected()` real— **sin persistirla en `history`** (así nunca se vuelve stale ni se acumula turno a turno). El `SYSTEM_PROMPT` le dice explícitamente al modelo que confíe en esa nota por sobre cualquier cosa que haya dicho antes en la conversación sobre el estado del celular.

```python
def _phone_status_note() -> dict:
    connected = is_phone_connected()
    return {
        "role": "system",
        "content": (
            "[Estado actual, verificado ahora mismo] Celular conectado: "
            + ("SÍ" if connected else "NO")
            + (". Las tools phone_* deberían funcionar."
               if connected else
               ". Las tools phone_* van a fallar hasta que el usuario conecte el celular.")
        ),
    }
```

**Verificación:** con el backend reiniciado (limpia `_conversations`) y usando el mismo `conversation_id` de la app que antes daba la respuesta mala, "abre la calculadora en mi celular" ahora hace que el modelo llame a `phone_open_app` (falla por package incorrecto — problema aparte, ver sección 6) y a `phone_read_screen` para investigar, en vez de negar tener acceso.

---

## 5. Ajuste de descripciones de tools (ambigüedad PC vs. celular)

**Síntoma previo y más leve:** pidiendo "abre la calculadora Jarvis" (sin decir "en mi celular"), el modelo eligió `browser_open` (PC) para buscar "calculadora" en Google, en vez de `phone_open_app`.

**Fix aplicado** (commit `578e25d`, sin tocar el system prompt): se ajustaron las *descripciones individuales* de las tools para que cada una diga explícitamente si actúa en la PC o en el celular:
- `phone_open_app`: "en el CELULAR del usuario (Android)... no usar para abrir programas o sitios web en la PC".
- `browser_open`: "navegador Chromium... en la PC del usuario... no para abrir apps del celular ni programas de escritorio".
- Las 6 tools `fs_*` suman "en la PC del usuario" a su descripción, por simetría con las `phone_*` equivalentes (que ya decían "en el celular").

No se tocó `agent.py`/`SYSTEM_PROMPT` en este cambio — la hipótesis (confirmada después, indirectamente, por el comportamiento correcto en pruebas posteriores) era que el modelo atiende más a la descripción puntual de cada tool que al prompt general.

Efecto colateral encontrado y arreglado en la misma sesión: ese mismo intento fallido de `browser_open` reveló que **Playwright no tenía Chromium instalado** en esta PC (`BrowserType.launch: Executable doesn't exist...`). Se corrió `playwright install chromium` en el venv del backend (no requiere reiniciar el backend — Chromium se lanza lazy, recién en el primer uso por proceso).

---

## 6. Bug #2 — Cliente OpenAI sincrónico bloqueando el event loop (el más serio)

**Síntoma reportado:** la app mostraba "Estado: desconectado, reintentando..." con WiFi activo. `GET /api/health` no respondía (timeout, sin error — colgado, no caído). El log del backend mostraba una request de `/api/chat` en loop durante ~6 minutos, reintentando `phone_global_action` una y otra vez, fallando siempre con "Se reemplazó la conexión del celular por una nueva" o "El celular se desconectó".

**Causa raíz, encontrada leyendo código, no solo infiriendo:**

```python
# backend/app/llm_client.py (ANTES)
from openai import OpenAI
client = OpenAI(base_url=settings.lmstudio_base_url, api_key="lm-studio")
```

```python
# backend/app/agent.py (ANTES)
response = client.chat.completions.create(...)   # sin await, sin executor,
                                                    # dentro de una función async
```

`uvicorn` corre un solo event loop. Una llamada **sincrónica** ejecutada directamente adentro de una corutina `async` bloquea ese loop entero mientras dura — y una inferencia local de un modelo de 30B puede tardar entre 20 y 100+ segundos. Durante ese bloqueo, el proceso no podía atender ningún otro tráfico: ni `GET /api/health`, ni los frames del WebSocket del celular. Cada vez que el agente hacía una tool call al celular, el WS se quedaba sin atender durante la siguiente inferencia, el celular (por su lado) decidía que la conexión estaba muerta y reconectaba, y esa reconexión mataba el tool call pendiente — el mismo patrón de inestabilidad de conexión que se venía arrastrando durante gran parte de la sesión, no solo este incidente puntual.

Además, durante esta misma investigación el proceso viejo terminó en un estado roto aparte: un error de red (`OSError: [WinError 64] El nombre de red especificado ya no está disponible`) tumbó su loop de `accept()` en asyncio — el proceso seguía vivo pero ya no escuchaba en el puerto. Confirma que había que reiniciar de todas formas, más allá del fix.

**Fix aplicado** (commit `4d312f4`):

```python
# llm_client.py (AHORA)
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url=settings.lmstudio_base_url, api_key="lm-studio")
```

```python
# agent.py (AHORA)
response = await client.chat.completions.create(...)
```

**Verificación real, en vivo:** se reinició el backend, se lanzó una request de chat sin tools (pregunta de texto general, para aislar la variable) en background, y **mientras estaba en curso** se hicieron 6+ pedidos concurrentes a `/api/health`, todos respondidos en ~7–9ms cada uno. La request de chat tardó **117.5 segundos** en total y devolvió `200 OK` — el event loop nunca se bloqueó durante ese tiempo. Este fue el último cambio de la sesión antes de la pausa.

---

## 7. Detalle operativo importante: cómo está corriendo el backend ahora mismo

El proceso actual del backend **no fue arrancado por la tray-app** — se inició directamente (`python run.py` desde una terminal, o en este caso, arrancado por Claude vía `nohup .venv/Scripts/python.exe run.py` redirigido a un log en el scratchpad de la sesión, para poder diagnosticar). Esto es relevante porque:

- `tray-app/backend.log` está **desactualizado** — corresponde a un proceso viejo (PID 20524) que ya no existe. No usarlo como fuente de verdad sobre el estado actual.
- El log real de la sesión actual del backend vive en un archivo temporal del scratchpad de Claude (`.../scratchpad/backend_restart2.log`), **no persistente** — si se cierra esta sesión de Claude o se reinicia la PC, ese archivo puede desaparecer. Si se quiere logging persistente del backend hacia adelante, conviene arrancarlo desde la tray-app (que sí escribe a `tray-app/backend.log` de forma estable) o redirigir manualmente a un archivo dentro del repo.
- PID actual del backend: **38496** (verificar con `netstat -ano | findstr :8000` si hace falta confirmar que sigue vivo).

---

## 8. Estado de tests y de git

**Tests backend:** 18/18 pasan (`cd backend && .venv/Scripts/python.exe -m pytest -q`). Se arreglaron 2 tests que habían quedado rotos por un cambio anterior (agregado de `network_candidates` a `/api/health` sin actualizar `test_smoke.py`/`test_phone_ws_endpoint.py`) — ahora validan la forma de la respuesta en vez de comparar por igualdad exacta con un dict fijo, porque `network_candidates` depende de las interfaces de red de la máquina.

**No hay tests para:** `agent.py` (el loop del agente en sí, incluida la nota de estado nueva), `network_info.py`, ni nada del lado Android/tray-app (no hay infraestructura de test en esos dos).

**Working tree:** limpio, todo commiteado. Commits de esta sesión, en orden:

```
1208bf3  Add PC-side chat window to tray-app; fix health-endpoint test drift
2734ea4  Document LAN/USB testing success and manual Tailscale install steps
c078f62  Log WS connect/close/failure reasons in PhoneLinkService
578e25d  Clarify PC vs. celular scope in tool descriptions for the LLM
91163d3  Inject live phone-connection status into every agent turn
4d312f4  Switch to AsyncOpenAI to stop the event loop from blocking on inference
```

**No commiteado / no aplica:** nada pendiente en el working tree a esta fecha.

**Config actual** (`backend/app/config.py`, valores desde `backend/.env`):
`HOST=0.0.0.0`, `PORT=8000`, `API_KEY` fijo (confirmado que coincide con el de la app Android tras el fix del bug de tipeo `l`/`I` de una sesión anterior), `LMSTUDIO_BASE_URL=http://localhost:1234/v1`, `FS_ALLOWED_ROOT` = home del usuario, `FS_ALLOW_DELETE=false`, `BROWSER_HEADLESS=false`, `MAX_AGENT_ITERATIONS=10`, `PHONE_TOOL_TIMEOUT=30s`.

---

## 9. Contexto, decisiones y lecciones operativas

*(Resumen narrativo aportado por el usuario.)*

### Qué es y por qué

Damian quiere comandar su LLM local ("Jarvis", modelo de 30B servido por LM Studio en su PC) desde el celular, con capacidad real de EJECUTAR ACCIONES — no solo chatear — tanto en la PC como en el celular Android, desde cualquier lugar (no solo en casa).

### Decisiones de arquitectura (todas confirmadas explícitamente por el usuario)

- Modelo: 30B parámetros vía LM Studio (localhost:1234, API compatible OpenAI).
- Backend: Python/FastAPI en la PC, con framework de tools que el LLM invoca. Actúa de router: cada tool tiene un `target` (`pc` o `phone`).
- Control del celular: **Accessibility Service con control TOTAL de pantalla** (no la opción acotada de Intents estándar). El usuario confirmó explícitamente que entiende el riesgo — con este permiso activo, Jarvis puede leer y tocar CUALQUIER app visible en pantalla, incluidas banca, WhatsApp, 2FA. Fue una decisión consciente, preguntada dos veces y confirmada las dos ("full invasiva").
- Transporte celular↔backend: WebSocket saliente desde el celular (no un servidor HTTP en el celu, por las limitaciones de Doze/background de Android), mantenido por un foreground service con notificación persistente.
- Filesystem del celu: Storage Access Framework (SAF), sandboxeado a una carpeta que el usuario elige una vez.
- Acceso remoto ("desde cualquier lugar"): Tailscale (VPN mesh privada) en vez de exponer el backend a internet directamente. Para cuando está en la misma red física, el backend también detecta y prioriza conexión directa por LAN o por el hotspot de la PC (pedido explícito del usuario: "mantengamos que se puedan conectar a internet pero también que uno tenga hotspot, lo tendrá la pc").
- Control bidireccional: el usuario pidió explícitamente poder comandar al celular desde la PC Y a la PC desde el celular. Esto llevó a agregar una ventana de chat en el tray-app (antes solo existía el chat en la app Android).
- Auth: Bearer token simple compartido, suficiente porque el backend nunca queda expuesto a internet directo (vive detrás de Tailscale/LAN).

### Pasos manuales pendientes (ninguno automatizable, por diseño de seguridad de Windows/Android — ya se intentó y se confirmó el límite)

1. **Instalar y loguear Tailscale en la PC** — el instalador pide UAC (aprobación humana obligatoria), y el login requiere credenciales reales en el navegador. Tampoco se pudo automatizar.
2. **Instalar Tailscale en el celular** (Play Store) y loguearse con la misma cuenta.
3. Cargar la IP de Tailscale de la PC en la app Android (reemplazando la IP LAN actual) una vez que Tailscale esté activo.
4. Determinar el package name real de la app Calculadora en este Moto G72 (no es `com.android.calculator2`; puede ser `com.google.android.calculator` u otro de Motorola) — Jarvis ya intenta compensar leyendo pantalla cuando falla, pero sería bueno confirmarlo.

### Bugs encontrados y resueltos durante esta sesión (cronológico)

1. Múltiples sesiones de código corriendo en paralelo sobre la misma carpeta dejaron procesos zombie (gradlew, java, sdkmanager, hasta un `claude.exe` viejo) que corrompían archivos y causaban cuelgues falsos — resuelto matando los procesos y evitando paralelismo sobre el mismo directorio de ahí en más.
2. Instalación del JDK vía MSI se colgaba esperando UAC — resuelto usando JDK portátil (zip) sin necesitar admin.
3. `sdkmanager --licenses` interactivo se colgaba — resuelto escribiendo los archivos de licencia a mano.
4. Playwright no tenía el navegador Chromium descargado (`playwright install` pendiente) — resuelto.
5. **Bug de contaminación de historial**: el modelo dijo una vez "no tengo acceso al celular" (en un momento en que probablemente no lo tenía), y como el historial de conversación persiste para siempre sin corrección, el modelo repetía esa afirmación falsa en cada turno siguiente, ignorando que las tools del celu SÍ estaban disponibles y el celu SÍ estaba conectado. Fix: inyectar el estado real de `is_phone_connected()` como nota de sistema fresca en cada turno, no depender del `SYSTEM_PROMPT` fijo ni del historial.
6. **Bug de arquitectura más serio**: el cliente de OpenAI hacia LM Studio era síncrono (`OpenAI`, no `AsyncOpenAI`) y se llamaba sin `await`/executor dentro de una función async — cada respuesta del modelo (20-70s con este modelo de 30B) congelaba TODO el servidor (incluida la conexión WebSocket del celu), causando reconexiones en cadena y la apariencia de inestabilidad de red que en realidad era el backend bloqueado. Fix: cambiar a `AsyncOpenAI`. Confirmado con prueba real de concurrencia que ya no se congela.

### Lecciones operativas (para quien retome esto)

- Las herramientas de pregunta interactiva (AskUserQuestion) en sesiones de código quedan bloqueadas para siempre si se usan — las respuestas por texto plano no llegan a ese widget. Nunca usarlas en esta sesión.
- No correr múltiples sesiones de código en paralelo sobre el mismo directorio de proyecto — causa corrupción real por procesos zombie.
- Los pasos que requieren UAC de Windows, login de cuentas, o toggles de seguridad de Android (Accessibility Service, Depuración USB) son inherentemente manuales — no vale la pena reintentar automatizarlos, hay que documentarlos como tal y seguir.
