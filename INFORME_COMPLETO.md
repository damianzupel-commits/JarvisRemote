# JarvisRemote — Manual completo del proyecto

> **Qué es este documento:** un manual del estado real del proyecto al
> 2026-07-27, no una bitácora de sesión. Reemplaza una versión anterior de
> este mismo archivo que era un informe de debugging de una sesión puntual
> (2026-07-20) y que ya no reflejaba el código actual (mencionaba LM Studio,
> la ventana de chat vieja en Tkinter, y no existían todavía
> generate_image/generate_video/jarvis_reflect ni la voz). Todo lo de acá
> está verificado contra el repo real, tests corridos, y pruebas en vivo
> hechas en las últimas sesiones — donde algo no está confirmado en vivo, se
> dice explícitamente. Nada de esto es optimista a propósito: si algo está
> roto o a medio probar, se dice.

---

## 1. Qué es JarvisRemote

Un asistente de IA local — corre enteramente en la PC del usuario, sin
depender de ningún servicio en la nube — al que se le puede dar órdenes desde
el celular o desde la PC, y que puede **ejecutar acciones reales** en ambos
dispositivos, no solo responder texto. El modelo de lenguaje corre en
[Ollama](https://ollama.com), local.

Tres componentes:

- **`backend/`** — Python + FastAPI. Habla con Ollama (API compatible OpenAI),
  corre el loop del agente (tool calling), expone `GET /api/health`,
  `POST /api/chat` y `WS /ws/phone` (todos autenticados con un Bearer token).
- **`tray-app/`** — Python + pystray + PySide6. Administra el backend como
  subproceso (arrancar/parar/reiniciar) y tiene su propia ventana de chat de
  escritorio con tema oscuro, selector de modelo, sidebar de accesos directos,
  y escucha de voz continua.
- **`android-app/`** — Kotlin + Jetpack Compose. Chat contra el backend, más
  un foreground service que mantiene una conexión WebSocket saliente hacia
  `/ws/phone` para recibir y ejecutar tool calls en el celular (control total
  de pantalla vía Accessibility Service, shell real vía Termux, cámara).

No hay ningún puerto expuesto a internet: el backend escucha en la IP privada
de Tailscale del usuario (o en la LAN local), y todas las requests requieren
el Bearer token.

---

## 2. Instalación

### 2.1. Con un comando (`install.ps1`, nuevo)

```powershell
.\install.ps1
```

Cubre la parte que es igual para cualquier instalación: detecta hardware
(CPU/RAM/GPU, con la limitación conocida de que WMI no siempre reporta bien
la VRAM en GPUs >4GB), recomienda un tier, instala/verifica Ollama, baja el
modelo del tier elegido y lo arma con el template de tool-calling corregido
(ver `installer/ollama/*.Modelfile`, sección 4), y deja `backend/.env` +
los venvs de `backend/` y `tray-app/` listos. Es idempotente.

**Explícitamente fuera de alcance de este script** (documentado en su propio
header, no es un olvido):
- ComfyUI (`generate_image`/`generate_video`): instalación portable propia,
  con un intérprete Python distinto según la GPU. Ver sección 4.6 sobre
  estabilidad conocida antes de meterse con esto.
- La app Android: ver `android-app/README.md` +
  `android-app/setup-android-sdk.ps1` + `deploy.ps1`.
- Termux, TLS, Tailscale: pasos manuales, documentados en
  `backend/README.md` — son decisiones de seguridad conscientes, no algo
  para automatizar a ciegas.

**Nota de honestidad sobre este script**: es nuevo (agregado en esta sesión),
tiene el syntax verificado y la lógica revisada, pero **no se corrió de
punta a punta en una máquina limpia** (correrlo completo pide input
interactivo y reinstalaría Ollama en una máquina que ya lo tiene). Los tags
base de Ollama que usa (`qwen3:30b-a3b`, `qwen3:8b`) se confirmaron contra
el registry real (el manifest existe), pero no se verificó el contenido
exacto del blob contra lo que corre hoy en la máquina de Damian.

### 2.2. Manual, paso a paso

Ver `backend/README.md`, `tray-app/README.md` y `android-app/README.md` para
el detalle completo. Resumen:

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env    # completar API_KEY, HOST, LMSTUDIO_MODEL, etc.
python run.py

# Ollama: bajar un modelo con soporte de tool calling y apuntar LMSTUDIO_MODEL
# a su nombre en `ollama list`. Ver installer/ollama/*.Modelfile si el modelo
# tiene problemas de tool-calling con el template default de Ollama.

# Tray app (recomendado, supervisa el backend en vez de correrlo suelto)
cd tray-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tray.py
```

### 2.3. Los 3 tiers de modelo

Seleccionables desde el selector de la ventana de PC (ver sección 5) o
seteando `LMSTUDIO_MODEL` en `backend/.env` a mano. Cambiar de tier **reinicia
el backend** (lee el `.env` una sola vez al arrancar, no hay hot-reload).

| Tier | Nombre en Ollama | Modelo base | Parámetros | Notas |
|---|---|---|---|---|
| **Lite** | `jarvis-text-lite` | Qwen3-8B (Q4_K_M) | 8.2B | Para hardware con menos VRAM/RAM. |
| **Medio** | `jarvis-text-v2` | Qwen3-30B-A3B, MoE (Q4_K_M) | 30.5B | El "principal", usado en la mayoría de las pruebas de esta sesión. |
| **Hard** | `jarvis-text-hard` | — | — | **Es un alias del mismo modelo que "Medio"** (`ollama cp jarvis-text-v2 jarvis-text-hard`) — no hay un modelo de texto distinto para este tier. Lo que lo distingue no es el modelo de texto sino que está pensado para tareas más pesadas (generación de imagen/video, disponibles como tool independientemente del tier activo). El selector necesita un nombre de Ollama propio para poder recordar cuál de los dos eligió el usuario, aunque el modelo real sea idéntico. |

Los tres tienen el mismo template de chat corregido (ver `installer/ollama/`)
— el modelo "jarvis-text" (v1, sin el fix) tiene un bug real de tool-calling
confirmado, no usarlo.

---

## 3. Arquitectura en detalle

### `backend/`

- `app/main.py` — `GET /api/health` (estado + candidatos de red LAN/hotspot/
  Tailscale), `POST /api/chat` (autenticado), `WS /ws/phone`.
- `app/agent.py` — loop del agente: manda mensajes + los 37 tool schemas a
  Ollama, ejecuta las tool calls que pida el modelo, devuelve resultados,
  repite hasta texto final o `MAX_AGENT_ITERATIONS` (default 10). Historial en
  memoria por `conversation_id`, podado a `MAX_HISTORY_MESSAGES` (default 40)
  para no reventar la ventana de contexto en conversaciones largas. Cada turno
  inyecta una nota de sistema fresca con el estado real de la conexión del
  celular (no depende de lo que el modelo haya dicho antes en la misma
  conversación sobre si el celular estaba conectado).
- `app/llm_client.py` — `AsyncOpenAI` apuntando a Ollama (`localhost:11434/v1`).
  Es async de punta a punta — un cliente síncrono acá bloquearía todo el
  event loop de uvicorn durante cada inferencia (bug real de una sesión
  anterior, ya arreglado).
- `app/tools/` — registry de tools (`register_tool`/`get_tools`/
  `openai_tool_schemas`/`call_tool`), ver catálogo completo en la sección 4.
- `app/phone_link.py` — estado de la conexión WS del celular + despacho de
  tool calls `target="phone"` (el backend nunca ejecuta esas tools
  localmente, solo las reenvía y espera la respuesta correlacionada por id).
- `app/audit_log.py` — log de auditoría estructurado (JSON por línea,
  `backend/audit.log`, rotado, gitignored) de cada tool call de celular y de
  escritorio.
- `app/network_info.py` — clasifica IPs (LAN/hotspot/Tailscale) para que el
  celular pueda elegir la ruta más directa disponible.

**Tests: 146 pasan** (`cd backend && pytest`).

### `tray-app/`

- `tray.py` — ícono de bandeja (pystray), autoarranca el backend, poll de
  salud cada 3s, auto-abre la ventana principal al iniciar.
- `process_manager.py` — `start()`/`stop()`/`is_running()` sobre el backend
  como subproceso, más `set_active_model()` (reescribe `LMSTUDIO_MODEL` en
  el `.env` y reinicia — usado por el selector de tier).
- `ui/main_window.py` — la ventana principal, ver sección 5.
- `ui/settings_window.py` — diálogo de permisos/conectores, ver sección 5.
- `voice_listener.py` — voz de la PC, ver sección 6.1.

**Tests: pasan** (`pytest`, usa `pytest-qt` para no abrir ventanas reales).

### `android-app/`

- Kotlin + Jetpack Compose + Material3. Compila y se instala 100% por línea
  de comandos (JDK 17 + Android SDK cmdline-tools, sin Android Studio) — ver
  `setup-android-sdk.ps1` + `deploy.ps1`.
- `phone/PhoneLinkService.kt` — foreground service, WebSocket saliente con
  reconexión con backoff exponencial.
- `phone/JarvisAccessibilityService.kt` — control de pantalla (tap/swipe/
  type/read_screen/global_action), con un blocklist configurable de apps
  sensibles (2FA, bancos) — mitigación por nombre de paquete, no un sandbox
  real.
- `phone/SafFileStore.kt` — filesystem del celular sandboxeado a una carpeta
  elegida por el usuario vía Storage Access Framework.
- `phone/TermuxCommandRunner.kt` + `TermuxResultService.kt` — ejecución de
  comandos reales vía Termux (`phone_run_command`).
- `voice/` — wake word "hey Jarvis" on-device + `SpeechRecognizer`, ver
  sección 6.2 (**con un bug real sin resolver**).
- `ApiKeyCrypto.kt` — cifra el API key guardado con AES-256-GCM en Android
  Keystore, en vez de guardarlo en texto plano en DataStore.

---

## 4. Catálogo completo de tools (37, confirmado corriendo `get_tools()` contra el código real)

### 4.1. Filesystem de la PC (`fs_*`, 6) — sandboxeadas a `FS_ALLOWED_ROOT`

`fs_list_dir`, `fs_read_file`, `fs_write_file`, `fs_create_dir`,
`fs_move_path`, `fs_delete_path` (esta última apagada por default,
`FS_ALLOW_DELETE=false`).

**Estado:** funcional, sandboxing verificado por tests.

### 4.2. Navegador de la PC (`browser_*`, 6) — Playwright + Edge del sistema

`browser_open`, `browser_click`, `browser_type`, `browser_get_text`,
`browser_screenshot`, `browser_close`. Usa el Microsoft Edge ya instalado en
Windows (`channel="msedge"`), no un Chromium propio de Playwright — evita el
fallo `BrowserType.launch: spawn UNKNOWN` que causaba cierto software de
seguridad con el Chromium sin firmar de Playwright.

**Estado:** funcional, probado.

### 4.3. Control de escritorio de la PC (`desktop_*`, 10) — pywinauto + pyautogui

`desktop_screenshot`, `desktop_list_windows`, `desktop_focus_window`,
`desktop_click`, `desktop_click_element`, `desktop_type_text`,
`desktop_press_key`, `desktop_move_mouse`, `desktop_scroll`,
`desktop_launch_app`. Control total e invasivo de cualquier ventana/programa
abierto — mismo nivel de riesgo que el Accessibility Service del celular, sin
sandboxing posible. No puede controlar ventanas elevadas (UAC, admin) por
restricción de Windows (UIPI). Blocklist de lanzamientos obviamente
destructivos (`format`, `diskpart`, `cipher /w`, `vssadmin delete`) — matching
de texto, no una garantía.

**Estado:** implementado, con tests unitarios, pero **no validado en vivo
contra una GUI real de otra app en esta sesión** — no confundir "tests
pasan" con "se probó clickeando algo de verdad".

### 4.4. Control del celular (`phone_*`, 12) — despachadas por WS, Accessibility Service + Termux + cámara

`phone_open_app`, `phone_list_dir`, `phone_read_file`, `phone_write_file`,
`phone_tap`, `phone_swipe`, `phone_type_text`, `phone_read_screen`,
`phone_global_action`, `phone_run_command`, `phone_take_photo`,
`phone_record_video`.

**Estado real, por sub-grupo:**
- **Tap/swipe/type/read_screen/global_action/filesystem SAF**: confirmado
  funcional en dispositivo real (Moto G72), incluida la reconexión del
  Accessibility Service por adb en la sesión de hoy.
- **`phone_run_command` (Termux)**: **con un error activo reportado por el
  usuario, sin investigar todavía** — "app is in background uid null" al
  intentar correr un comando, posiblemente una restricción nueva de Android
  bloqueando el intent `RUN_COMMAND` cuando la app no está en foreground.
  Pendiente de diagnóstico.
- **`phone_take_photo`/`phone_record_video` (cámara)**: agregadas
  recientemente (commits `0f264a0`, `8eebc32`). El video se convierte a una
  secuencia de frames (no se manda el video crudo) para que lo puedan
  consumir modelos de visión. **Con errores reportados por el usuario sin
  investigar todavía**: "El celular no respondió a tiempo" y "Camera is
  closed".

### 4.5. Generación de contenido (2) — ComfyUI local en GPU — **DESACTIVADAS por precaución de hardware**

> ⚠️ **`generate_image` y `generate_video` están deshabilitadas a propósito
> (comentadas en `backend/app/tools/__init__.py`, no borradas — reactivables
> con solo descomentar dos líneas una vez resuelto el problema de hardware).
> Esto no es una limitación de software ni una elección de producto: es una
> precaución de seguridad física.**

- **`generate_image`** — Flux.1 Schnell (GGUF Q4_K_S), una sola pasada de
  KSampler (4 pasos), rápido.
- **`generate_video`** — Wan 2.2 (workflow de dos expertos high/low noise),
  lento (medido entre ~4.3 y ~14 min para 1s de clip).
- Ambas comparten infraestructura (`_comfyui_shared.py`): coordinan VRAM con
  Ollama (descargan el modelo de texto antes de generar, lo recargan al
  terminar), y arrancan/paran el proceso de ComfyUI si hace falta.

**Por qué se desactivaron — evidencia dura, no una sospecha:**

El 2026-07-27, la PC de Damian **se apagó por completo** (no un crash de
proceso ni de ComfyUI — un apagado físico de hardware) al menos dos veces,
ambas coincidiendo *al segundo* con el arranque de una de estas dos tools:

| Hora | Evidencia del backend | Evidencia del Event Log de Windows |
|---|---|---|
| 16:23:06 | `tool_call name=generate_image` a las 16:23:06,391 | Event 6008: "el cierre anterior del sistema a las 16:23:06 resultó inesperado" |
| ~16:57 | Polling de `generate_video` (prompt del globo) corriendo normal hasta 16:56:58, silencio total después | `LastBootUpTime` = 16:57:26 (reinicio) |

Sumado a un patrón previo de apagados similares (Event ID 41, "crítico", "se
reinició el sistema sin apagarlo limpiamente") en los días 22 y 23 de julio,
y un tercer apagado esa misma mañana del 27/07 (que en su momento se
diagnosticó, erróneamente, como "se cayó el proceso del backend" — en
realidad fue la PC entera).

**Diagnóstico anterior a este hallazgo (sigue siendo válido como parte del
problema, pero no explica un apagado físico de PC):** ComfyUI puede
crashear a nivel nativo (sin traceback de Python) si se le piden dos
generaciones seguidas o en paralelo — reproducido tres veces en una sesión
previa, con la hipótesis de que la GPU (RX 6700 XT, `gfx1031`) no está
oficialmente soportada por ROCm. Se habían aplicado dos mitigaciones de
software (fail-fast en el polling en vez de colgar 10 minutos, y limpieza de
procesos zombie de ComfyUI) — **esas mitigaciones siguen en el código y
siguen siendo válidas**, pero un apagado físico de la PC es un problema de
otra categoría que ningún fail-fast de software puede prevenir.

**Hipótesis sin confirmar, a investigar antes de reactivar:** protección
térmica de la GPU/CPU, la fuente de poder sin margen para el pico de consumo
de la carga GPU, o un crash de driver lo bastante severo como para forzar un
reset de hardware en vez de solo matar el proceso. Ninguna de las tres se
investigó todavía — hace falta monitorear temperaturas/voltajes durante una
generación controlada (con la PC vigilada, no desatendida) antes de siquiera
considerar reactivar estas dos tools.

**Cómo quedaron desactivadas:** no se borró código. `backend/app/tools/__init__.py`
simplemente no importa `video_gen`/`image_gen` (comentado con la explicación
de por qué), así que `register_tool` nunca corre para ellas — el LLM ya no
las ve en la lista de 35 tools disponibles (confirmado con `get_tools()`
corriendo contra el backend real, y con los 146 tests del backend pasando
igual). Reactivarlas es descomentar esas dos líneas, pero **no hacerlo hasta
entender la causa del apagado**.

### 4.6. Memoria de reflexión del agente (1)

- **`jarvis_reflect`** (`action="save"`/`"query"`) — JSONL append-only
  (`backend/reflections.jsonl`, gitignored, puede tener notas personales),
  búsqueda simple por superposición de palabras. Para que el modelo recuerde
  decisiones no triviales entre conversaciones que no comparten historial.

**Estado:** implementado, con tests unitarios. No se validó en una
conversación real de punta a punta esta sesión (guardar una reflexión y que
un turno *futuro* la recupere y la use).

---

## 5. Interfaz nueva de PC (PySide6)

Reemplaza la vieja ventana de Tkinter (borrada, `tray-app/chat_window.py` ya
no existe). Tema oscuro fijo (pedido explícito del usuario, sin opción de
volver a claro).

- **Chat central**: mandar/recibir mensajes contra `POST /api/chat`, mismas
  tools que la app Android (incluidas las `phone_*` si el celular está
  conectado). Cada burbuja del asistente se puede seleccionar con el mouse.
- **Indicador de "pensando..."** (agregado en esta sesión): burbuja gris
  itálica mientras se espera la respuesta del backend, para que una request
  larga (Ollama cargando en frío, generación de imagen/video) no parezca
  colgada. Confirmado funcionando en vivo.
- **Selector de tier (Lite/Medio/Hard)**: arriba de la ventana. Cambiar de
  tier reinicia el backend — confirmado funcionando en vivo (dos reinicios
  reales observados en el log durante la sesión).
- **Sidebar**:
  - Los botones 🖼 "Generar imagen" y 🎬 "Generar video" **ya no existen en
    la UI** (`Sidebar.TOOLS` vacía a propósito) — no es solo que la tool de
    atrás esté deshabilitada, Damian pidió explícitamente que no aparezcan
    ni como opción visible, dado el riesgo de hardware (ver sección 4.5).
    Antes de sacarlos se había confirmado en vivo que el click de 🎬 sí
    disparaba `generate_video` correctamente (tool_call real con un prompt
    propio de Damian, no de una prueba automatizada) — la UI en sí
    funcionaba bien, el problema nunca fue el wiring. Confirmado con test
    (`test_sidebar_has_no_utility_buttons_only_voice`) y reinicio en vivo de
    la ventana: el sidebar ahora solo tiene el botón de voz.
  - 🎙 activa/desactiva la escucha de voz continua (ver sección 6.1).
- **Ícono de configuración (⚙)**: diálogo aparte (`ui/settings_window.py`) a
  propósito — la ventana de chat tiene que quedar "limpia, nada técnica".
  Prende/apaga `DESKTOP_CONTROL_ENABLED`, `PHONE_SHELL_ENABLED`,
  `PHONE_CAMERA_ENABLED`, `FS_ALLOW_DELETE`, `BROWSER_HEADLESS` escribiendo
  directo a `backend/.env`, y reinicia el backend al guardar. **Código
  revisado y de bajo riesgo (lectura/escritura de `.env` + reinicio, mismo
  mecanismo ya probado del selector de tier), pero el click real de abrir el
  diálogo y guardar todavía no se confirmó visualmente en esta sesión.**

---

## 6. Voz

### 6.1. PC (`tray-app/voice_listener.py`)

Pipeline: mic (16kHz mono) → `openWakeWord` (modelo custom entrenado con TTS
en 22 voces/acentos de español, `models/hey_jarvis.onnx`, **no committeado
en git — necesario para que esto funcione, ver `tray-app/README.md`**) →
Silero VAD decide cuándo terminó el comando → `faster-whisper` (`medium`,
`language="es"` fijo) transcribe → `POST /api/chat`.

**Estado:** según indicación del usuario, esta parte está considerada
cerrada/funcional. **No se validó de forma independiente en esta sesión** —
no se tocó `voice_listener.py` ni se hizo una prueba de voz en la PC hoy.

### 6.2. Android (`android-app/.../voice/`) — bug real, sin resolver, diagnóstico pausado

Mismo modelo (`hey_jarvis.onnx`, MD5 idéntico al de la PC — confirmado, no es
un problema de modelo distinto) portado a Kotlin puro sobre ONNX Runtime
(`OnnxWakeWordDetector.kt` + `WakeWordFeatureBuffers.kt`), sin TFLite.

**Síntoma reportado:** el mismo audio real grabado por el propio micrófono
del celular (archivos `training_samples/positive_*.wav`, capturados con
`SampleRecorder.kt`) da **score 1.0 en Python** (pipeline de referencia,
mismo modelo) pero scoreaba ~0.001–0.15 en vivo en el celular.

**Lo que se descartó, con evidencia dura:**
- **No es un problema del modelo** — mismo archivo, mismo hash MD5 en PC y
  Android.
- **No es un bug de la matemática del port Kotlin** — se corrió el archivo
  real grabado por el celular a través del código de producción real
  (`OnnxWakeWordDetector`/`WakeWordFeatureBuffers`, el mismo que usa
  `VoiceListenerService` en vivo) desde un hook de diagnóstico temporal, y
  dio **score=1.0000 en el mismo frame exacto** que Python, en dos archivos
  distintos. Además cada frame se procesó en ~20ms, muy por debajo de los
  80ms de presupuesto — tampoco es un problema de latencia de inferencia.

**Lo que sigue sin explicación:** en una prueba en vivo posterior, el
detector SÍ funcionó (score 0.99265, detección y ejecución correctas) sin que
se supiera qué había cambiado respecto a los intentos fallidos anteriores con
audio similar. **El diagnóstico quedó pausado en este punto, no resuelto** —
no se identificó qué distingue un intento en vivo exitoso de uno fallido. El
hook de diagnóstico temporal (`WakeWordSelfTestReceiver.kt` + el gancho en
`MainActivity.kt`) se sacó del código antes de publicar el repo, ya cumplió
su propósito.

**Próximo paso de diagnóstico sugerido** (no hecho todavía): instrumentar
`VoiceListenerService.kt` con timestamps por frame durante una sesión de
escucha en vivo real, para ver si hay drops/desincronización del stream de
`AudioRecord` específicamente en los intentos que fallan.

---

## 7. Seguridad

Ver el detalle completo en `backend/README.md` (sección "Notas de
seguridad"). Resumen:

- El backend no valida quién está del otro lado más allá del Bearer token —
  la barrera principal es que solo es alcanzable por la tailnet/LAN del
  usuario.
- Log de auditoría persistente (`backend/audit.log`, JSON por línea) de cada
  tool call de celular y de escritorio.
- `desktop_*` y el Accessibility Service del celular son **control total e
  invasivo**, sin sandboxing posible — decisión consciente del usuario,
  ambos apagables por variable de entorno sin tocar código.
- `phone_run_command` es ejecución de shell real (código arbitrario) vía
  Termux — el nivel más invasivo del proyecto.
- Blocklists de comandos/lanzamientos obviamente destructivos en ambos lados
  — mitigación de "evitar el desastre obvio" por matching de texto, **no un
  sandbox real ni una garantía de seguridad completa**.
- TLS (`wss://`/`https://`) preparado en el backend pero apagado por
  default — la conexión viaja en texto plano salvo que ya esté sobre
  Tailscale (cifrado por WireGuard a nivel de transporte).
- API key del celular cifrado con AES-256-GCM en Android Keystore (no texto
  plano).

---

## 8. Resumen ejecutivo honesto — qué funciona confirmado vs. qué no

| Área | Estado |
|---|---|
| Chat PC↔backend (texto) | ✅ Confirmado en vivo, incluido roundtrip completo con Ollama |
| Selector de tier (Lite/Medio/Hard) | ✅ Confirmado en vivo (reinicios reales observados) |
| Indicador de "pensando..." | ✅ Confirmado en vivo |
| `generate_image`/`generate_video` | 🔴 **DESHABILITADAS por precaución de hardware** — la PC se apagó físicamente (no un crash de software) al menos dos veces coincidiendo al segundo con estas tools. Ver sección 4.5. |
| Botones 🖼/🎬 del sidebar | 🔴 **Removidos de la UI a pedido de Damian** (no solo deshabilitados) — el wiring había sido confirmado en vivo (🎬 disparaba `generate_video` bien) antes de sacarlos. Confirmado con test + reinicio en vivo de la ventana. |
| Ícono de configuración ⚙ (click en la UI) | ⚠️ Pendiente de confirmación visual |
| Control de celular: tap/swipe/type/read_screen/SAF | ✅ Confirmado en dispositivo real |
| `phone_run_command` (Termux) | ❌ Error activo ("app is in background uid null"), sin diagnosticar |
| `phone_take_photo`/`phone_record_video` | ❌ Errores activos (timeout, "Camera is closed"), sin diagnosticar |
| `desktop_*` (control de PC) | ⚠️ Tests unitarios pasan, sin validar contra una GUI real |
| `jarvis_reflect` | ⚠️ Tests unitarios pasan, sin validar en una conversación real de punta a punta |
| Voz PC (`voice_listener.py`) | ⚠️ Según el usuario, funcional — no validado por Claude esta sesión |
| Voz Android (wake word) | ❌ Bug real confirmado, diagnóstico pausado sin causa raíz identificada |
| Instalador de un click | ⚠️ Recién escrito, syntax verificado, no corrido de punta a punta |

---

## 9. Licencia

MIT — ver `LICENSE`.
