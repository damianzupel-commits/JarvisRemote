# CLAUDE.md — Contexto del proyecto JarvisRemote

> Documento de orientación para cualquier sesión de IA (o para el propio Damian)
> que retome este repo sin contexto previo. Se creó el 2026-08-17 porque se
> perdieron sesiones remotas y el repo no estaba auto-documentado. Mantenelo al
> día. El estado operativo (en qué se está trabajando ahora) va en `ESTADO.md`.

---

## ⚠️ Advertencias antes de tocar nada

- **ESTE repo es `C:\Users\dam\Documents\JarvisRemote`.** Es el proyecto real y
  activo.
- **`C:\Users\dam\cerebro-fenix\_Jarvis-Local` NO es este proyecto.** Es un
  **prototipo VIEJO de asistente de voz, congelado el 2026-07-20**. No lo uses
  como referencia, no copies código de ahí, no lo confundas con esto. Está
  muerto a propósito.
- **`C:\Users\dam\Vault-Fenix` es un vault de Obsidian aparte**, independiente
  del vault que vive dentro de este repo (`backend/obsidian_vault/`). No los
  mezcles.
- **El repositorio remoto es PÚBLICO** (github.com/damianzupel-commits/JarvisRemote).
  Todo lo que se commitea y pushea queda visible para cualquiera. Nunca
  commitees secretos, claves, `.env`, targets de pentesting, credenciales ni
  rutas privadas sensibles. El `.gitignore` ya cubre lo obvio (ver abajo), pero
  revisá antes de pushear.

---

## Qué es JarvisRemote

Herramienta de **auditoría de código / pentesting** manejada por un LLM, con un
agente de tool-calling que además fue creciendo en capacidades de asistente
personal (control de PC y celular, investigación forense, protección antimalware,
generación de contenido). Le apuntás a un proyecto, lo indexa en un grafo
(código + notas estilo Obsidian) y corre escáneres reales de seguridad/calidad
para encontrar vulnerabilidades antes de shippear.

Filosofía de diseño recurrente en todo el código: **acciones reales sobre la PC,
no simuladas**; **flags para apagar cada capacidad invasiva sin tocar código**;
**"sin fricción" por default a pedido explícito de Damian**, pero con gates
donde el daño sería irreversible.

## Arquitectura real (basada en el código)

```
JarvisRemote/
├── backend/           Python + FastAPI. El cerebro: loop del agente + todas las tools.
├── tray-app/          Python + pystray. Ventana de escritorio (pestañas Codebase/Obsidian),
│                      administra el backend como subproceso, selector de modelo, voice listener.
├── android-app/       App Android (Kotlin/Gradle) — componente aparte, en desarrollo.
│                      NO hace falta para la auditoría de código. Se conecta por WebSocket.
├── installer/ollama/  Modelfiles de Ollama (jarvis-text-v2, jarvis-text-lite).
├── install.ps1        Instalador idempotente (detecta hardware, arma modelo, venvs, .env).
├── docs/              Diagrama de arquitectura, etc.
├── content/           Contenido humano/de publicación (grabaciones, capturas) — gitignoreado.
├── README.md          Presentación pública (enfoca solo auditoría de código).
├── INFORME_COMPLETO.md Informe largo con el resto de las capacidades.
└── Fundamentos_de_Jarvis.docx
```

### Backend (`backend/app/`) — módulos

FastAPI (`main.py`, entrypoint `run.py`). El agente (`agent.py`) corre el loop
LLM → tool → LLM con ~50 tools registradas (`tools/`). Routers HTTP: `codebase`,
`obsidian`, `investigation`. El celular se conecta por WebSocket (`phone_link.py`).

Módulos principales:

- **`codebase/`** — indexa cualquier proyecto en un grafo (tree-sitter, con
  fallback genérico). Archivos, funciones, clases, imports como edges.
- **`obsidian/`** — vault de notas .md reales (frontmatter YAML, wikilinks),
  búsqueda semántica por embeddings + coseno (keyword como fallback). Autoría
  separada jarvis/humano. Hay un vault de seguridad y otro de investigación
  científica (`obsidian_vault_investigacion/`), con perfiles distintos.
- **`security/` + `quality/` + `findings/`** — escaneo real (Semgrep, Bandit,
  cppcheck, clang-tidy, Trivy = seguridad; Ruff/mypy = calidad) con modelo de
  hallazgos unificado, triage, cache por proyecto, benchmark OWASP.
- **`codeedit/` + `selfrepair/`** — aplicación de fixes reversibles (cada fix en
  su propio commit git). `selfrepair/` propone fixes al **propio** código de
  Jarvis (dry-run sin gate, aplicar de verdad requiere confirmación manual).
- **`testing/`** — pipeline de tests reales: detección, runner, store del último
  resultado. Cierra el gap "compiló ≠ funciona" antes de re-auditar.
- **`pentest/` + `network/`** — pentesting ACTIVO: sqlmap (inyección SQL), OWASP
  ZAP, captura de paquetes (scapy). `network/` = nmap (reconocimiento pasivo) +
  el **guardrail de scope compartido** (ver gates de seguridad abajo).
- **`malware/`** — protección antimalware: YARA + ClamAV (clamd) + heurística
  conductual (watchdog/psutil) + FIM (file integrity monitoring) + monitor del
  proceso propio + Sysmon (experimental, apagado). Cuarentena reversible.
  Escaneo diario en background de `FS_ALLOWED_ROOT` + on-access de Descargas/
  Escritorio/Temp. Reusa el artifact store y las claves Ed25519 de `investigation/`.
- **`investigation/`** — análisis de enlaces y evidencia digital: casos (cada uno
  su propio repo git), artifact store por sha256, log append-only firmado con
  Ed25519 (claves protegidas con DPAPI).
- **`forms/`** — completado de formularios web con credential store cifrado (DPAPI).
  Dry-run con captura de preview antes de todo submit (pedido explícito de Damian).
- **`introspection/`** — Jarvis puede leer/razonar sobre su propio código.
- **`tools/`** — todas las tools del agente: `desktop.py` (mouse/teclado/ventanas),
  `pc_command.py` + `shell_exec.py` (shell real), `browser.py` (Playwright vía
  Edge del sistema), `phone.py` (Termux/cámara del celular), `network_scan.py`,
  `cloud_expert.py`, `opencode.py`, `video_gen.py`/`image_gen` (ComfyUI, apagadas
  por consumo), `reflect.py`, `web_forms.py`, etc.
- **`recording.py`** — grabación de pantalla (ffmpeg) automática alrededor de las
  tools de auditoría/fix/test, para documentar el trabajo.

### Tray-app (`tray-app/`)

pystray + ventana con pestañas Codebase/Obsidian. Lanza el backend como
subproceso (`process_manager.py`), tiene `voice_listener.py` (entrada por voz) y
un selector de modelo por tiers (Lite/Medio/Hard). `config.py` lee el mismo
`backend/.env`.

---

## Modelos en uso (nombres exactos)

Hay **un modelo de chat/agente por vez** más un modelo de embeddings aparte más
tools puntuales que delegan a otros modelos. NO hay ruteo automático cloud/local
en runtime: el modelo de chat se elige por config.

### Modelo de chat/agente ACTIVO ahora mismo — CLOUD

- **`gpt-oss:120b-cloud`** — configurado en `backend/.env` como `LMSTUDIO_MODEL`.
  **Este es el "modelo de 120B" que Damian recordaba.** Es gpt-oss 120B servido
  por la **nube de Ollama** (no corre local; requiere estar logueado en Ollama
  cloud). Se accede por el endpoint OpenAI-compatible de Ollama en
  `http://127.0.0.1:11434/v1` — Ollama proxea el modelo cloud transparentemente,
  por eso el cliente (`app/llm_client.py`) no cambia.

> ⚠️ El nombre de variable `LMSTUDIO_*` quedó de una migración vieja desde LM
> Studio. **HOY apunta a Ollama (puerto 11434), no a LM Studio.** No te dejes
> confundir por el nombre.

### Modelos LOCALES de chat/agente (alternativa al cloud)

Armados por `install.ps1` con un Modelfile de template **corregido para
tool-calling** (`installer/ollama/*.Modelfile`). El `.env.example` los usa por
default (`LMSTUDIO_MODEL=jarvis-text-v2`).

- **`jarvis-text-v2`** — base **Qwen3-30B-A3B (MoE)**, servido por Ollama con su
  cuantización default (Q4_K_M). **Este es el "modelo de 30B Q4" que Damian
  recordaba.** Tier "Medio" (y "Hard").
- **`jarvis-text-lite`** — base **qwen3:8b**. Tier "Lite" (hardware con menos VRAM/RAM).
- **`jarvis-text-hard`** — alias (`ollama cp`) de `jarvis-text-v2`. Existe solo
  para que el selector de la tray recuerde qué tier eligió el usuario; es el
  mismo modelo de texto que Medio.
- **`jarvis-text` (v1)** — ⚠️ **NO USAR.** Bug real de template de tool-calling
  (los tool calls no los reconocía el parser de Ollama). Reemplazado por v2.

### Cómo se elige entre cloud y local

- El modelo de chat es **uno solo, definido por `LMSTUDIO_MODEL` en `backend/.env`**.
  Cambiar de cloud a local (o entre tiers locales) = cambiar esa variable (o usar
  el selector Lite/Medio/Hard de la tray-app, que escribe uno de los `jarvis-text-*`).
- Ahora está en `gpt-oss:120b-cloud`, **seteado a mano** — no es uno de los tres
  tiers del selector, así que el selector de la tray no lo va a mostrar como opción.

### Embeddings (memoria semántica del vault) — LOCAL, servidor aparte

- **`text-embedding-nomic-embed-text-v1.5`**, servido por el **LM Studio real
  (la app)** en `http://127.0.0.1:1234/v1`. A propósito NO reusa el endpoint de
  chat: en esta PC Ollama (11434) no tiene modelo de embeddings cargado; LM
  Studio (1234) sí. Config: `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL`.

### Modelos que usan tools puntuales (no son el chat principal)

- **`gemini-2.5-flash`** (Google AI Studio, free tier) — lo usan SOLO las tools
  `cloud_expert_code` / `cloud_expert_marketing` (`app/tools/cloud_expert.py` +
  `app/cloud_client.py`) para un primer borrador de código/marketing. Endpoint
  OpenAI-compatible `https://generativelanguage.googleapis.com/v1beta/openai/`.
  Requiere `GOOGLE_AI_API_KEY` en `.env` (vacío = la tool falla con error claro).
- **`opencode_run_task`** — delega a la CLI OpenCode apuntada a
  `jarvis-ollama/jarvis-text-v2` (Ollama local).

---

## Cómo levantar el entorno y correr los tests

Requiere **Windows** (varias tools son Windows-específicas: DPAPI, taskkill,
pywinauto, Termux link, etc.). Ollama (o LM Studio) corriendo aparte.

**Rápido (idempotente):**

```powershell
.\install.ps1   # detecta hardware, instala/verifica Ollama, arma el modelo del
                # tier que corresponda, deja backend/.env + venvs listos.
```

**Manual:**

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt    # incluye requirements.txt + pytest/httpx
copy .env.example .env                 # completar API_KEY, LMSTUDIO_MODEL, etc.
python run.py                          # levanta FastAPI (default :8000)

# Tray-app (ventana de escritorio)
cd ..\tray-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tray.py
```

**Probar el backend:**

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer TU_API_KEY" -H "Content-Type: application/json" \
  -d "{\"message\": \"Listame los archivos de mi escritorio\"}"
```

**Tests** (100 archivos `test_*.py` en `backend/tests/`; la tray tiene los suyos
en `tray-app/tests/`):

```bash
cd backend && pytest
cd ../tray-app && pytest
```

---

## Convenciones del repo

- **Commits en español**, con prefijo tipo Conventional Commits:
  `feat:` funcionalidad nueva · `fix:` corrección de bug (los mensajes suelen
  aclarar "bug real" cuando fue un problema reproducido, no hipotético) ·
  `chore:` mantenimiento/config · `docs:` documentación. Mensajes descriptivos,
  con contexto del *porqué*, no solo el *qué*.
- **`git config core.autocrlf = input`** — line endings LF en el repo. Respetalo.
- **Comentarios de código extensos y con fecha**: el código (sobre todo
  `config.py`) documenta decisiones y bugs reales con fecha y razonamiento. Es la
  memoria del proyecto — leelo antes de cambiar defaults, no lo borres.
- **`.gitignore`** cubre: venvs/caches (`.venv/`, `__pycache__`, `.mypy_cache`,
  `.ruff_cache`, `.pytest_cache`), `node_modules/`; **secretos** (`.env` y
  `.env.*` salvo `.env.example`, `*credentials*.json`, `*.pem`/`*.key`/`*.p12`,
  `id_rsa*`, `*_token.json`, `*_api_key.json`, `secrets.json`); **datos sensibles
  de pentesting** (`backend/authorized_targets.yaml`, `sqlmap_api_credentials.json`,
  `zap_api_key.json`); **contenido pesado** (`content/recordings/`, `*.mp4/mkv/mov/avi`,
  capturas, `*.docx` de la raíz); y logs. Motivo: el remoto es público y los
  binarios/credenciales no deben versionarse.

---

## Decisiones de diseño y gates de seguridad ya tomados

Estos gates ya están decididos e implementados — **no los debilites sin pedírselo
a Damian explícitamente.**

- **Pentesting activo detrás de una autorización única y no negociable.** Todas
  las tools de pentesting activo (nmap, sqlmap, ZAP, captura de paquetes) validan
  el target contra **`backend/authorized_targets.yaml`** (fuente única compartida,
  decisión del 2026-08-13) antes de correr. **Ni las tools ni el LLM pueden
  escribir ese archivo** — solo Damian lo edita a mano. Por default el scope solo
  permite rangos privados/loopback/Tailscale; escanear una IP pública exige que
  Damian la agregue a mano (escanear sin autorización puede ser ilegal).
- **Auto-reparación con gate de aprobación** (`selfrepair/`, "Opción C"). Jarvis
  puede *proponer* un fix a su propio código en dry-run sin gate, pero *aplicarlo*
  (`confirm=true`) requiere un `proposal_id` concreto que Damian confirma a mano.
  Guardrail de self-target en `agent.py`.
- **Patrón dry-run → confirm=true** para todo lo destructivo/irreversible:
  cuarentena de malware (mover, no borrar; eliminar definitivo solo con confirm),
  fixes de código, submit de formularios (preview obligatorio antes).
- **Flags para apagar cada capacidad invasiva** sin tocar código:
  `DESKTOP_CONTROL_ENABLED`, `PC_SHELL_ENABLED`, `PHONE_SHELL_ENABLED`,
  `PHONE_CAMERA_ENABLED`, `SCREEN_RECORDING_ENABLED`, `NMAP_ENABLED`, etc. Están
  prendidos por default a pedido explícito de Damian ("versión sin fricción").
- **Sandbox de filesystem**: `FS_ALLOWED_ROOT` limita las tools de FS. ⚠️ Por
  default es el **HOME entero** (`Path.home()`), no solo el repo — ver la propuesta
  de sandboxing en `ESTADO.md`, hay una mitigación barata pendiente.
- **`pc_run_command` NO es un sandbox real**, es una blocklist de patrones
  destructivos (format, rm -rf /, shutdown, fork bombs). Un comando fuera de la
  blocklist corre igual. Auditoría persistente de todo lo que ejecuta.
- **Presupuesto de contexto del modelo protegido en varias capas**
  (`_trim_history`, `_cap_tool_result`, `model_context_tokens`) tras bugs reales
  de "context exceeded" con escaneos grandes. Si cambiás el modelo, sincronizá
  `MODEL_CONTEXT_TOKENS` con el `num_ctx` real.
- **TLS preparado pero apagado** (`TLS_ENABLED=false`). Activarlo rompe la app
  Android hasta que confíe en el cert self-signed — coordinar con Damian, no
  activar solo (ver `backend/certs/README.md`).
- **Timeouts LLM generosos a propósito** (1800s) — cortar una generación real en
  curso fuerza un reprocesamiento carísimo del prompt entero (bug real v6).

---

## Dónde buscar más contexto

- **`ESTADO.md`** (raíz) — qué se está trabajando ahora, qué quedó a medias,
  próximos pasos. **Leelo apenas retomes.**
- **`backend/README.md`** — setup detallado, "cómo está armado", limitaciones
  conocidas, notas de seguridad, instalación de nmap/ClamAV/etc.
- **`INFORME_COMPLETO.md`** (raíz) — informe largo del proyecto entero.
- **`backend/obsidian_vault/jarvis/`** — el propio vault de notas de Jarvis:
  índices por tema, decisiones de arquitectura (ej.
  `indice-arquitectura-jarvis.md`, `propuesta-sandboxing-en-contenedor-*.md`).
- **`backend/app/config.py`** — la fuente más rica de decisiones y bugs reales
  con fecha, comentada línea por línea.
