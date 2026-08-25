# CAPACIDADES-REALES-DE-JARVIS.md — Auditoría honesta

> Documento de **auditoría de capacidades** (no ejecutable, no es código). Mapea
> lo que Jarvis **hace hoy de forma confiable** contra lo que **existe pero no
> está probado** y lo que **todavía es solo un plan**. Objetivo: que Damian sepa
> exactamente qué puede delegarle a Jarvis antes de "dar vuelta la relación" y
> usarlo como motor principal.
>
> Creado: 2026-08-19 (análisis de solo lectura del código real, no se modificó
> nada). Alinea con: `CLAUDE.md`, `ESTADO.md`, `vision/HACIA-RAPHAEL.md` y los
> diseños de `lab/`. Cruza contra el registro real de tools
> (`app/tools/`), el loop del agente (`app/agent.py`) y la suite de tests
> (`backend/tests/`, 101 archivos `test_*.py`).
>
> **Regla del documento:** cada estado se justifica con archivo y/o test. Donde
> algo no está probado, se dice sin maquillarlo. La honestidad es el punto.

---

## 1. Resumen ejecutivo honesto (una línea)

**Jarvis es hoy un asistente de auditoría de código y análisis forense/de
seguridad de un solo usuario, sólido y bien testeado en su núcleo (escaneo,
investigación, gates de seguridad, memoria en vault), pero envuelto en una capa
ancha de capacidades de control (PC, celular, pentesting activo, antimalware con
respuesta) que en buena parte están escritas y unit-testeadas pero NO validadas
end-to-end contra el mundo real — y todo corre sobre un modelo local/cloud de
gama media (30B / 120B) que alcanza para ejecutar herramientas paso a paso pero
NO para razonar con autonomía sobre tareas ambiguas o de varios pasos sin
supervisión.**

En una frase más corta: **motor de ejecución confiable con supervisión; piloto
automático todavía no.**

---

## 2. Tabla maestra por dominio

Categorías de estado:
- ✅ **VALIDADO** — existe, con tests que pasan y/o probado end-to-end de verdad.
- ⚠️ **SIN PROBAR** — código escrito, quizás con unit tests mockeados, pero nunca
  validado contra el mundo real. La trampa: parece que anda.
- 🧪 **EXPERIMENTAL / PARCIAL** — a medias, detrás de un flag, o con limitaciones
  conocidas.
- ❌ **SOLO DISEÑO** — existe como documento, no como código.

| Dominio / capacidad | Qué hace realmente | Estado | Evidencia (archivo / test) | Límite conocido |
|---|---|---|---|---|
| **Loop del agente (tool-calling)** | Ciclo LLM→tool→LLM con ~110 tools, `tool_choice=auto`, poda de historial por cantidad y por presupuesto de tokens, tope de salida, auditoría JSON de cada call | ✅ | `app/agent.py` (loop 958-1177); `tests/test_agent.py`, `test_tools_registry.py`, `test_agent_skills.py` | Sin reintentos automáticos: un error de tool vuelve como `{"error":...}` y el modelo decide qué hacer. Máx. 10 iteraciones (50 si hay `fs_write_file`) |
| **Ruteo por skills** | Clasifica el mensaje por keywords y le da al modelo solo el subconjunto de tools + prompt del dominio | ✅ | `app/skills.py` (SKILLS dict, `classify`); `tests/test_skills.py` (disjunción, completitud) | Clasificación por substring de keywords, no semántica: un pedido sin las palabras esperadas cae al set completo |
| **Indexado de código (grafo)** | Indexa cualquier proyecto (tree-sitter + fallback), archivos/funciones/clases/imports como nodos y aristas | ✅ | `app/codebase/`; `test_codebase_graph/_indexer/_store/_tools.py` | — |
| **Escaneo de seguridad** | Semgrep, Bandit, cppcheck, clang-tidy, Trivy con modelo de hallazgos unificado + triage + cache + benchmark OWASP | ✅ | `app/security/`, `app/tools/security_scan.py`; `test_security_scanners/_tools/_triage/_rescan.py` | Depende de que los binarios estén instalados en la PC (degrada con gracia si faltan) |
| **Escaneo de calidad** | Ruff + mypy con mismo modelo de hallazgos | ✅ | `app/quality/`, `app/tools/quality_scan.py`; `test_quality_scanners/_tools/_rescan.py` | Idem binarios |
| **Ciclo fix→commit→verify** | Aplica fixes reversibles (un commit git por fix), corre tests, cierra el ciclo con informe | ✅ | `app/codeedit/`, `app/tools/code_edit.py`, `test_run.py`; `test_codeedit_fixer.py`, `test_testing_pipeline.py`, `test_test_run_tool.py` | La calidad del fix depende del modelo (ver §6) |
| **Auto-reparación del propio backend** | Propone fixes al código de Jarvis; dry-run sin gate, aplicar exige `proposal_id` confirmado a mano | ✅ (gate) | `app/selfrepair/`, `app/tools/selfrepair.py`; `test_selfrepair_gate/_propose/_tool.py` | Aplicar de verdad es siempre manual (por diseño) |
| **Vault Obsidian + memoria semántica** | Notas .md reales (frontmatter, wikilinks), búsqueda por embeddings + coseno, autoría jarvis/humano, perfiles separados | ✅ | `app/obsidian/`; `test_obsidian_vault/_embeddings/_profile/_router/_tools.py` | Embeddings servidos por LM Studio local (1234): si no está levantado, cae a búsqueda por keyword |
| **Reflexión / memoria abstracta** | JSONL append-only de decisiones/lecciones con tipo y contexto, consulta por palabras | ✅ | `app/tools/reflect.py`; `test_reflect_tool.py` | Búsqueda por superposición de palabras, sin embeddings ni LLM |
| **Investigación forense / grafo de entidades** | Casos (repo git c/u), parsers CSV/WhatsApp/Telegram/log/EXIF/PDF/NER, fusión de identidades, métricas de grafo, informe MD+PDF, log firmado Ed25519 | ✅ | `app/investigation/`; **`test_investigation_end_to_end.py`** (encadena todos los parsers en un caso real) + ~20 tests unitarios | Ingesta de imagen/descripción depende del modelo VL |
| **Claves Ed25519 + log firmado (DPAPI)** | Firma append-only del log de investigación/malware, claves protegidas con DPAPI, `rebuild_from_log` | ✅ | `app/investigation/keys.py`; `test_investigation_keys.py`, `test_investigation_log.py` | DPAPI = solo Windows / solo la cuenta del usuario |
| **Credential store cifrado (DPAPI)** | Guarda credenciales de formularios cifradas con DPAPI | ✅ | `app/forms/`; `test_credential_store.py` (10 tests) | Idem Windows/cuenta |
| **Gate de submit de formularios (`preview_token`)** | Dry-run obligatorio emite token de un solo uso atado a selector+URL+timestamp; `confirm=true` sin token válido rechaza sin clickear | ✅ | `app/tools/web_forms.py`; **`test_web_forms.py` (17/17)** cubre expiración, reuso, binding a selector y página | El gate está probado; el **submit real en un navegador** no tiene test end-to-end (usa Playwright, ver browser) |
| **Pentesting — sqlmap** | Escaneo real de inyección SQL vía REST API de sqlmap, detrás del gate `authorized_targets.yaml` | ✅ | `app/pentest/sqlmap_client.py`, `app/tools/pentest_sqlmap.py`; **`test_pentest_sqlmap_integration.py`** (target vulnerable real, validado en vivo 2026-08-13; skip si sqlmap no instalado) | Requiere sqlmap instalado; corre solo contra targets autorizados a mano |
| **Guardrail de scope de pentesting** | Valida todo target contra `authorized_targets.yaml` (rangos privados/loopback/Tailscale); ni tools ni LLM pueden escribir ese archivo | ✅ | `app/network/`; `test_network_guardrail.py` | Solo Damian edita el YAML a mano (por diseño) |
| **Pentesting — nmap** | Reconocimiento de red | 🧪 | `app/tools/network_scan.py`; `test_network_scanner.py`, `test_tool_network_scan.py` (mockeados) | Sin test de integración contra nmap real como el de sqlmap; requiere nmap instalado |
| **Pentesting — OWASP ZAP** | Escaneo web activo | ⚠️/🧪 | `app/pentest/`, `app/tools/pentest_zap.py`; `test_pentest_zap_integration.py` (skip si ZAP no está) | Test de integración existe pero solo corre si ZAP está instalado; sin evidencia de corrida validada |
| **Pentesting — captura de paquetes (scapy)** | Captura y análisis de tráfico | ⚠️/🧪 | `app/tools/pentest_wireshark.py`; `test_pentest_packet_capture.py` | Requiere permisos/privilegios de captura reales; sin evidencia de validación en vivo |
| **Antimalware — detección estática** | YARA + ClamAV (clamd) + VirusTotal, escaneo de path/disco, cuarentena reversible | 🧪 | `app/malware/`; `test_malware_yara_scanner/_virustotal_client/_quarantine/_store/_tools.py` (skip/mock según binario) | Depende de YARA/ClamAV instalados; VT necesita API key |
| **Antimalware — FIM (integridad)** | Baseline de integridad de archivos + verificación | ✅ | `app/malware/`; `test_malware_*` + reuso del store firmado | — |
| **Antimalware — heurística conductual** | Detecta patrón de ransomware (archivos cambiando + entropía alta) | 🧪 PARCIAL | `app/malware/behavioral_watcher.py` (línea 20: *"no identifica ni puede matar el PROCESO"*) | **Detecta pero NO contiene**: no tiene el PID/imagen para matar el proceso. La respuesta real requiere el diseño kernel-grade (❌) |
| **Antimalware — Sysmon** | Consumo de telemetría Event ID 8/10 | 🧪 EXPERIMENTAL | `app/malware/sysmon_monitor.py`; `test_malware_sysmon_monitor.py`; flag `SYSMON_ENABLED=false` | Apagado por default |
| **Control de escritorio (mouse/teclado/ventanas)** | Screenshot, click, foco de ventana, tipear, teclas, scroll, lanzar apps (pyautogui/pywinauto) | 🧪 | `app/tools/desktop.py`; `test_desktop_tools.py` (33 tests, con mocks de pyautogui/pywinauto) | Tests mockean la GUI: la lógica está cubierta, la interacción real con Windows no se testea automáticamente. Flag `DESKTOP_CONTROL_ENABLED` |
| **Shell real de la PC** | `pc_run_command` / `shell_exec` ejecutan comandos reales | 🧪 | `app/tools/pc_command.py`, `app/shell_exec.py`; `test_pc_command.py` | **NO es sandbox**: es una blocklist de patrones destructivos. Un comando fuera de la lista corre igual. `FS_ALLOWED_ROOT` por default es el HOME entero |
| **Navegador (Playwright vía Edge)** | Abrir/click/type/leer/screenshot en web | 🧪 | `app/tools/browser.py`; `test_browser_tool.py` (mockeado) | Chromium bundleado no arranca en esta PC (firma SxS/AV); usa `channel="msedge"` como workaround. Sin test end-to-end contra web real |
| **Control del celular (backend)** | Router de tool calls `target="phone"` por WebSocket, blocklist de comandos destructivos | 🧪 | `app/phone_link.py`, `app/tools/phone.py` (12 tools); `test_phone_link.py` (FakeWebSocket), `test_phone_ws_endpoint.py` | El lado backend se testea con un WebSocket falso, nunca contra un teléfono real conectado |
| **App Android (control del teléfono)** | APK Kotlin/Compose: chat + foreground service + Accessibility + Termux (shell real) + cámara | ⚠️ | `android-app/`; `SETUP_RAPIDO.md` (*"probado y funciona por LAN/USB", 2026-07-20*) | **Compila y corrió una vez por LAN/USB** (fecha vieja), pero **el caso de uso real (Tailscale, datos móviles) NO está probado y Tailscale no está instalado**. Sin tests automáticos contra dispositivo real |
| **Ingesta de playlist de YouTube → vault** | Enumera playlist (yt-dlp), detecta nuevos por video-ID, transcribe, resume con el LLM, escribe nota con formato exacto, idempotente | ✅ (validado por Damian 2026-08-19) | `app/ingestion/youtube_playlist.py`, `app/tools/ingestion.py`; `test_youtube_ingestion.py` (lógica de vault/formato/idempotencia) | **Ojo:** el docstring del módulo todavía dice "NO PROBADO CONTRA YOUTUBE REAL" y **todos los tests mockean la red** (yt-dlp, transcript-api, LLM). La validación real es la corrida manual de Damian, no la suite. Conviene actualizar el docstring |
| **Delegación a modelos cloud** | `cloud_expert_code/marketing` (Gemini Flash), `opencode_run_task` (OpenCode → Ollama local) | 🧪 | `app/tools/cloud_expert.py`, `opencode.py`; `test_cloud_expert.py`, `test_opencode_tool.py` | Gemini necesita `GOOGLE_AI_API_KEY` (vacío = falla clara). Free tier |
| **Generación de imagen/video (ComfyUI)** | `generate_image`, `generate_video` | 🧪 APAGADO | `app/tools/image_gen.py`, `video_gen.py`; `test_image_gen_tool.py`, `test_video_gen_tool.py` | Apagadas por consumo de energía real de la PC (apagados observados) |
| **Grabación de pantalla (ffmpeg)** | Graba automáticamente alrededor del pipeline auditoría→fix→test | ✅ | `app/recording.py`, `app/tools/recording.py`; `test_recording.py` (skip si no hay ffmpeg) | Flag `SCREEN_RECORDING_ENABLED`; requiere ffmpeg |
| **Investigación web / research** | `research_topic` | 🧪 | `app/tools/research.py`; `test_research_tool.py` | Sin evidencia de validación end-to-end |
| **Introspección (leer su propio código)** | Jarvis razona sobre su propio backend | ✅ | `app/introspection/`; `test_introspection.py` | Solo lectura/análisis |
| **Orquestación remota (celular fuera de casa)** | `vm_control`, `ssh_guest`, cola de misiones, confirmaciones remotas | ❌ | `lab/ORQUESTACION-REMOTA-DESIGN.md` (2026-08-17, "spec, no código") | No existe código |
| **Detección/estrés nocturno** | Bucle de detección desatendido en el cyber range | ❌ | `lab/DETECCION-ESTRES-NOCTURNO.md` | Solo diseño |
| **Defensa kernel-grade (EDR sin driver)** | ETW/AMSI/ASR/WDAC/AppLocker/WFP orquestando kernel de Windows | ❌ | `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`, `DEFENSA-PRIORIDADES.md` | Solo diseño; nada instalado |
| **Cyber range (lab aislado)** | VMs de ataque/víctima para probar los módulos ofensivos | 🧪 EN ARMADO | `ESTADO.md` §Cyber range | VirtualBox + Kali + Metasploitable montados, pero a mitad (falta bootear/snapshotear/conectar); falta Docker |
| **Sandboxing de `pc_run_command` en contenedor** | Acotar el radio de daño del shell | ❌ | `backend/obsidian_vault/jarvis/propuesta-sandboxing-*.md` | Docker no instalado; hay una mitigación barata pendiente (achicar `FS_ALLOWED_ROOT`) |

---

## 3. Lo que Jarvis YA hace confiable (delegable hoy sin miedo)

Solo lo ✅. Esto es el núcleo real y probado — lo que podés dejarle correr con
supervisión mínima:

**Auditoría de código de punta a punta.** Indexar un proyecto, escanear
seguridad (Semgrep/Bandit/Trivy/cppcheck) y calidad (Ruff/mypy), triar
hallazgos, aplicar fixes reversibles (un commit por fix), correr los tests y
generar el informe. Es lo más maduro del repo: modelo de hallazgos unificado,
cache, benchmark OWASP y tests en verde en toda la cadena. La *ejecución* del
pipeline es confiable; la *calidad de cada fix* depende del modelo (ver §6), así
que revisás los diffs, no el proceso.

**Investigación forense / grafo de entidades.** Ingesta de CSV, exports de
WhatsApp/Telegram, logs de servidor, imágenes con EXIF y PDFs; NER, fusión de
identidades, métricas de grafo e informe MD+PDF, todo con log firmado Ed25519 y
reconstruible desde el log. Tiene un test end-to-end real que encadena todos los
parsers — es el segundo subsistema más sólido.

**Memoria en el vault (Obsidian).** Guardar y buscar notas con embeddings,
journaling, continuidad de criterio entre conversaciones vía `jarvis_reflect`.
Confiable como memoria de largo plazo del asistente.

**Los gates de seguridad.** El `preview_token` de formularios (17/17 tests), el
`proposal_id` de auto-reparación, el guardrail de `authorized_targets.yaml`.
Estos están *diseñados para no confiar en el prompt del modelo* y tienen
enforcement en código — son justamente lo que te deja delegar con red de
seguridad.

**sqlmap contra targets autorizados.** Único módulo ofensivo con validación en
vivo real (2026-08-13) además de test de integración.

**Ingesta de YouTube al vault** (validada por vos el 2026-08-19). Con la salvedad
de actualizar el docstring y de que la suite sigue mockeada.

---

## 4. Lo que parece que hace pero NO está probado (la trampa)

Esto compila, tiene código serio, muchas veces tiene unit tests — y por eso es
peligroso: **da la sensación de estar listo**. Delegarle autonomía acá sería
riesgoso hasta validarlo contra el mundo real.

**Control del celular / app Android.** Es el caso más claro. El APK compila, el
lado backend está testeado con un WebSocket *falso*, y hay una corrida por
LAN/USB registrada… pero **de julio, con fecha vieja, y el caso de uso real
(Tailscale desde datos móviles) nunca se probó porque Tailscale ni está
instalado**. Entre "compiló y anduvo una vez en la misma red" y "puedo confiarle
control total de mi teléfono a distancia" hay un abismo de validación. Riesgo
extra: la app expone Accessibility + Termux (shell arbitrario) en el teléfono.

**Control de escritorio y navegador reales.** 33 tests de desktop, pero todos
mockean pyautogui/pywinauto: se prueba la lógica, no que el click caiga donde
tiene que caer en tu Windows real. El navegador tiene un bug conocido (Chromium
no arranca, workaround con Edge) y ningún test contra web real. Para "Jarvis hace
el trabajo pesado en la PC", esto es exactamente lo que hay que endurecer.

**Shell de la PC.** `pc_run_command` corre comandos reales y **no es un
sandbox** — es una blocklist de texto. Fuera de esa lista, cualquier comando se
ejecuta, y `FS_ALLOWED_ROOT` es tu HOME entero. Funciona; el problema no es que
falle, es que su radio de daño no está acotado. La mitigación barata (achicar
`FS_ALLOWED_ROOT`) sigue pendiente.

**ZAP, captura de paquetes, nmap.** A diferencia de sqlmap, no tienen una corrida
validada en vivo; sus tests o son mocks o se saltan si la herramienta no está.
El gate de scope los protege de tocar targets no autorizados, pero que
*funcionen* como esperás no está demostrado.

**Antimalware conductual.** Detecta patrón de ransomware pero **no puede
contenerlo** — no tiene el PID para matar el proceso. O sea: te avisa mientras te
cifran, no lo frena. La contención real es diseño (§5).

---

## 5. Lo que todavía es solo un plan (❌ solo diseño)

Documentos en `lab/`, sin una línea de código:

- **Orquestación remota** (`ORQUESTACION-REMOTA-DESIGN.md`): controlar Jarvis
  desde el celular fuera de casa, `vm_control`/`ssh_guest`, cola de misiones con
  confirmaciones remotas. Explícitamente "spec, no código".
- **Detección/estrés nocturno** (`DETECCION-ESTRES-NOCTURNO.md`): el bucle
  desatendido que "trabaja mientras Damian no mira". Diseño.
- **Defensa kernel-grade** (`DEFENSA-KERNEL-GRATIS-DESIGN.md` +
  `DEFENSA-PRIORIDADES.md`): acercar el antimalware a un EDR orquestando
  ETW/AMSI/ASR/WDAC/AppLocker/WFP. Diseño; nada instalado. Es lo que le daría al
  watcher conductual la capacidad de *contener*, no solo detectar.
- **Sandboxing en contenedor** de `pc_run_command`/`browser`: propuesta en el
  vault; Docker no instalado.
- **Cyber range**: a mitad de armado (VMs creadas, falta bootear/conectar/
  snapshotear). Es el prerrequisito para *validar* los módulos ofensivos y de
  detección que hoy están ⚠️.

---

## 6. El salto a "Jarvis hace el trabajo pesado": qué le falta concretamente

Que Jarvis pase de "herramienta que uso" a "motor que hace y yo corrijo" exige
cuatro cosas que hoy no están, en este orden.

### 6.1 La limitación real del modelo (lo más importante, y no es opcional)

El chat corre sobre **`gpt-oss:120b-cloud`** (Ollama cloud) o, en local,
**`jarvis-text-v2` (Qwen3-30B-A3B, MoE, Q4_K_M)**. Hay que ser honesto sobre qué
implica:

- Un 30B/120B de esta clase **ejecuta bien flujos guiados**: "escaneá esto",
  "aplicá este fix", "ingestá este CSV", "corré la playlist". El andamiaje de
  skills + prompts por dominio + gates está justamente construido para
  compensar al modelo, acotándole el problema y las tools disponibles.
- **NO razona como un modelo frontera** sobre tareas ambiguas, de muchos pasos,
  con decisiones encadenadas o que requieren planificar y replanificar. El
  propio código lo evidencia: guardrails contra *loops de reescritura idéntica*,
  contra *archivos bloqueados que abandona*, contra *adivinar otra solución en
  vez de consultar Obsidian* — todos son parches para modos de falla reales
  observados del modelo (v4, v5, v6 en los comentarios de `agent.py`). Eso te
  dice qué tipo de tarea NO le podés soltar: la que pide criterio, no ejecución.
- Cloud (120B) razona mejor que el local (30B) pero depende de estar logueado a
  Ollama cloud y de la red; el local es más autónomo pero más limitado. No hay
  ruteo automático: es uno u otro por config.

**Traducción práctica:** delegale *tareas acotadas y verificables*, no *objetivos
abiertos*. "Auditá este repo y proponé fixes" ✅. "Encargate de la seguridad de mi
PC" ❌ — eso último requiere criterio sostenido que el modelo no tiene.

### 6.2 Manejo de errores y reintentos

El loop **no reintenta**: un error de tool vuelve como `{"error":...}` y el
modelo decide. Para autonomía real falta una capa de reintentos/backoff con
criterio (distinguir error transitorio de error de lógica), y política de
escalamiento cuando el modelo entra en loop (hoy hay detección de algunos loops,
pero la salida es cortar el turno, no recuperarse). El tope de 10 iteraciones (50
en tareas de código) es razonable pero es un tope duro, no una estrategia.

### 6.3 Confiabilidad de las capas que hoy están ⚠️

Antes de delegarle acciones sobre PC/celular/red, hay que **validarlas contra el
mundo real**, no contra mocks. En orden de lo que más desbloquea:

1. **Achicar `FS_ALLOWED_ROOT`** (una línea, cero riesgo, ya identificado). Sin
   esto, cualquier delegación de shell tiene radio de daño = HOME entero.
2. **Validar desktop/browser reales** con un set chico de tareas verificables en
   tu Windows (no mocks), y arreglar el bug de Chromium o formalizar Edge.
3. **Cerrar el cyber range** para poder validar en vivo nmap/ZAP/captura como ya
   se hizo con sqlmap.
4. **Probar el control del celular sobre Tailscale** (instalar Tailscale primero),
   no solo por LAN.
5. **Actualizar el docstring de YouTube** y, si querés, agregar un test de humo
   real (no mock) para que la suite refleje que ya se validó.

### 6.4 Autonomía acotada con contención real

El watcher conductual detecta pero no contiene; el shell no está sandboxeado. Si
Jarvis va a actuar "mientras no mirás", necesita poder *frenar daño*, no solo
avisar — eso es el diseño kernel-grade (❌) + el sandbox en contenedor (❌). Hasta
que existan, la autonomía desatendida es prematura.

---

## 7. Veredicto honesto: ¿está Jarvis para "dar vuelta la relación" hoy?

**Parcialmente sí, en un dominio; todavía no como motor general.**

**SÍ podés dar vuelta la relación hoy en el núcleo de auditoría de código y en
investigación forense.** Ahí Jarvis ya es un motor confiable: le apuntás a un
proyecto o a un caso, hace el trabajo pesado (indexar, escanear, triar, fixear,
testear, informar / ingerir evidencia, fusionar, graficar, exportar) y vos
corregís sobre el resultado. Los gates (`preview_token`, `proposal_id`,
`authorized_targets.yaml`) te dan la red de seguridad para soltarle la mano sin
que rompa nada irreversible. Sumale la ingesta de YouTube al vault, ya validada.
En este perímetro, "Jarvis hace y yo corrijo" **ya es real**.

**NO todavía como asistente general que controla tu PC, tu celular y tu red de
forma autónoma.** Esas capas existen y son impresionantes en superficie, pero
están en ⚠️ (control de PC/celular/navegador probados solo con mocks, Tailscale
sin instalar) o ❌ (contención de malware, orquestación remota, sandbox). Y por
encima de todo está el techo del modelo: un 30B/120B ejecuta, no delibera.
Delegarle objetivos abiertos hoy es pedirle criterio que no tiene, sobre acciones
cuyo radio de daño todavía no está acotado.

**El camino corto para ensanchar el "sí"** (en orden de mejor relación
riesgo/beneficio): (1) achicar `FS_ALLOWED_ROOT`; (2) validar desktop/browser
reales; (3) cerrar el cyber range y validar en vivo el resto de las tools
ofensivas; (4) Tailscale + celular real; (5) recién después, la contención
(kernel-grade / sandbox) que habilita la autonomía desatendida.

En una frase: **hoy Jarvis es un excelente segundo par de manos para auditar
código e investigar; para ser el "Gran Sabio" que actúa solo sobre tu vida
digital le falta validar el mundo real y acotar el daño — y aceptar que el modelo
manda ejecución, no juicio.**
