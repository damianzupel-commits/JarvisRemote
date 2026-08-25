# Raphael — Documentación técnica del sistema real

> **Convención de nombre.** A lo largo de toda esta documentación el sistema se llama
> **Raphael** (antes "Jarvis"). Sin embargo, **todos los identificadores reales del código
> se mantienen exactamente como están**: módulos (`agent.py`, `phone_link.py`), clases
> (`VaultNote`, `OperationMode`), funciones (`run_agent`, `resolve_and_authorize`), tools
> (`jarvis_reflect`, `security_audit_find_fix_verify`), loggers (`jarvis.agent`), variables
> de entorno (`LMSTUDIO_MODEL`) y prompts (que dicen literalmente "Sos Jarvis…"). Esto
> documenta el código tal como existe hoy; "Raphael" es el nombre de producto, "jarvis" es
> el nombre interno todavía presente en el código. Cuando esta documentación diga "Raphael"
> se refiere al sistema; cuando cite un identificador, ese es el nombre real a buscar en el repo.

> **Alcance.** Esta documentación describe **únicamente lo que existe en el código a la fecha
> (2026-08-23)**. No incluye visión, roadmap ni features planeadas. Donde un componente está
> incompleto, experimental o desactivado, se lo indica explícitamente.

---

## Resumen ejecutivo

Raphael es una **herramienta de auditoría de código y pentesting operada por un LLM**, construida
como un agente de *tool-calling* que fue creciendo hasta convertirse también en un asistente
personal con control real de PC y celular, defensa antimalware, investigación forense y generación
de contenido. El núcleo es un backend **Python/FastAPI** que corre un loop *LLM → tool → LLM* con
~58 herramientas registradas (desde `fs_write_file` hasta `sqlmap_scan`), servido por un modelo
LLM local o cloud a través de un endpoint compatible con OpenAI. Alrededor de ese backend hay una
**tray-app de escritorio** (Windows, PySide6/pystray) que administra el proceso y ofrece las vistas
de chat/codebase/obsidian/investigación, y una **app Android** (Kotlin/Compose) que se conecta por
WebSocket para prestarle al agente los sensores y la ejecución del teléfono. Toda la filosofía de
diseño es **acciones reales, no simuladas**, con *flags* para apagar cada capacidad invasiva y
*gates* de seguridad (dry-run→confirm, `authorized_targets.yaml`, DPAPI, modos supervisado/autónomo)
donde el daño sería irreversible.

---

## Diagrama de arquitectura (texto)

```
                                   ┌──────────────────────────────────────────────┐
   USUARIO (Damian)                │                  MODELOS LLM                  │
   ├─ Ventana escritorio (tray)    │  chat/agente: gpt-oss:120b-cloud (Ollama       │
   ├─ Voz PC (voice_listener)      │      cloud) │ jarvis-text-v2 (Qwen3-30B local) │
   └─ App Android (chat / voz)     │  embeddings: nomic-embed (LM Studio :1234)     │
            │                      │  tools puntuales: gemini-2.5-flash (cloud)     │
            │ HTTP /api/chat        └───────────────▲──────────────────────────────┘
            │ WS /ws/phone                          │ OpenAI-compatible
            ▼                                        │
   ┌────────────────────────────────────────────────┴───────────────────────────────┐
   │                         BACKEND  (FastAPI · uvicorn · :8000)                     │
   │                                                                                  │
   │   main.py ──► auth.py (Bearer)                                                    │
   │     │                                                                            │
   │     ├─ POST /api/chat ─► operation_mode (SUPERVISADO) ─► agent.run_agent          │
   │     │        │                                                                    │
   │     │        ▼                                                                    │
   │     │   ┌──────────── agent.py : loop LLM→tool→LLM ────────────┐                  │
   │     │   │  · perfiles default/research  · skills.py (subsets)   │                  │
   │     │   │  · trim de historial (msgs + tokens)                  │                  │
   │     │   │  · gates: obsidian, self-target, pending writes,      │                  │
   │     │   │           loop de reescritura, preview_token          │                  │
   │     │   │  · llm_client.py (AsyncOpenAI)                        │                  │
   │     │   └───────────────────────┬──────────────────────────────┘                  │
   │     │                           │ call_tool(name,args)                            │
   │     │             ┌─────────────┴──────────── tools/  (registro plano) ─────────┐ │
   │     │             │ target="pc" → handler local   target="phone" → phone_link   │ │
   │     │             └──────────────────────────────────────────────────────────────┘ │
   │     │   SUBSISTEMAS (librería, en app/*, envueltos por tools/*.py):                │
   │     │   codebase · security · quality · findings · testing · codeedit · selfrepair │
   │     │   · malware · network · pentest · investigation · obsidian · forms           │
   │     │   · ingestion · introspection · recording · shell_exec · audit_log           │
   │     │                                                                              │
   │     ├─ GET /api/health · /api/health/deep                                          │
   │     ├─ routers: /api/codebase · /api/obsidian · /api/investigation                 │
   │     ├─ WS /ws/phone ─► phone_link (dispatch a celular, correlación por id)          │
   │     └─ startup: malware.behavioral_watcher + malware.fullscan (background)          │
   │                                                                                    │
   │   FS SANDBOX (filesystem._resolve) ◄── operation_mode.effective_fs_roots()          │
   │   GATE DE RED (network/guardrail.resolve_and_authorize) ◄── authorized_targets.yaml │
   └────────────────────────────────────────────────────────────────────────────────────┘
            ▲                                              │
            │ HTTP (health/candidates, chat, voz)          │ WS bidireccional (tool calls)
            │                                              ▼
   ┌────────┴─────────────┐                    ┌──────────────────────────────┐
   │   TRAY-APP (Windows) │                    │      APP ANDROID (Kotlin)    │
   │  pystray + PySide6   │                    │  PhoneLinkService (WS) ·      │
   │  process_manager     │                    │  PhoneToolHandler ·           │
   │  voice_listener      │                    │  Accessibility · Termux ·     │
   │  ui/ (chat,codebase, │                    │  CameraX · SAF · VoiceListener│
   │  obsidian,invest.)   │                    │  (wake word on-device)        │
   └──────────────────────┘                    └──────────────────────────────┘
```

Relación entre capas: **`tools/*.py` son wrappers finos** que exponen la lógica real (que vive en
los paquetes de librería `app/security/`, `app/malware/`, `app/investigation/`, etc.) al LLM. La
dirección de dependencia es estricta: `app/tools/*` importa de `app/<librería>/`, nunca al revés.

---

## Stack tecnológico real

| Capa | Tecnología |
|------|-----------|
| **Backend** | Python 3.12, FastAPI ≥0.115, uvicorn, Pydantic 2, SDK `openai` (cliente async), httpx |
| **LLM chat/agente** | `gpt-oss:120b-cloud` (Ollama cloud, activo) o `jarvis-text-v2` (Qwen3-30B-A3B local); endpoint OpenAI-compatible en `http://127.0.0.1:11434/v1` (var `LMSTUDIO_MODEL`, nombre heredado) |
| **Embeddings** | `text-embedding-nomic-embed-text-v1.5` servido por LM Studio real en `:1234` |
| **Tools cloud puntuales** | `gemini-2.5-flash` (Google AI Studio, free tier) para `cloud_expert_*` |
| **Indexado de código** | tree-sitter + tree-sitter-language-pack (fallback regex), pathspec (gitignore) |
| **SAST/SCA** | Semgrep, Bandit, cppcheck (wheel), clang-tidy (wheel), Trivy (externo) |
| **Calidad** | Ruff, mypy (Python), ESLint + tsc (JS/TS, externos), detekt (Kotlin, externo) |
| **Pentesting** | nmap (externo), SQLMap (REST API), OWASP ZAP (daemon REST), scapy (captura de paquetes) |
| **Malware** | yara-python, clamd (cliente de ClamAV), psutil, watchdog, VirusTotal (opcional), Sysmon (experimental) |
| **Investigación forense** | networkx, matplotlib, fpdf2, pypdf, python-docx, Pillow (EXIF), cryptography (Ed25519), python-dateutil |
| **Navegador / desktop** | Playwright (Edge/Chromium del sistema), pyautogui, pywinauto, pywin32/comtypes |
| **Grabación** | ffmpeg (binario del sistema), OpenCV (frames de video) |
| **Ingesta** | yt-dlp, youtube-transcript-api |
| **Tray-app** | Python, pystray, PySide6, Pillow; voz: openWakeWord + Silero VAD + faster-whisper |
| **App Android** | Kotlin, Jetpack Compose, Retrofit + OkHttp, kotlinx.serialization, DataStore, CameraX, ONNX Runtime; minSdk 26 / targetSdk 34 |
| **Seguridad** | DPAPI (Windows) para secretos, Ed25519 para logs firmados, Android Keystore (AES-256-GCM) en el teléfono |

---

## Cómo se levanta el sistema

Requiere **Windows** (varias tools son Windows-específicas: DPAPI, `taskkill`, pywinauto, link a Termux).
Ollama (o LM Studio) corre aparte.

**Rápido (idempotente):**

```powershell
.\install.ps1   # detecta hardware, instala/verifica Ollama, arma el modelo del tier,
                # deja backend/.env + venvs listos.
```

**Manual:**

```powershell
# Backend
cd backend
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # completar API_KEY, LMSTUDIO_MODEL, etc.
python run.py                   # FastAPI en :8000

# Tray-app
cd ..\tray-app
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
python tray.py
```

**Probar el backend:**

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer TU_API_KEY" -H "Content-Type: application/json" \
  -d '{"message": "Listame los archivos de mi escritorio"}'
```

**Tests:** `cd backend && pytest` (≈100 archivos `test_*.py`) · `cd tray-app && pytest`.

---

## Índice de la documentación

| # | Archivo | Contenido |
|---|---------|-----------|
| 01 | [01-agente-y-loop.md](01-agente-y-loop.md) | `agent.py`: loop LLM→tool, perfiles, trimming de contexto, todos los guardrails en vivo |
| 02 | [02-cliente-llm-config-modos.md](02-cliente-llm-config-modos.md) | `llm_client.py`, `cloud_client.py`, `operation_mode.py` (SUPERVISADO/AUTÓNOMO) |
| 03 | [03-tools-registro-catalogo.md](03-tools-registro-catalogo.md) | Registro de tools (`tools/__init__.py`) + catálogo completo de las ~58 tools |
| 04 | [04-auditoria-codigo.md](04-auditoria-codigo.md) | codebase, security, quality, findings, testing, codeedit, selfrepair, audit_report, introspection |
| 05 | [05-malware-defensa.md](05-malware-defensa.md) | `app/malware/*`: YARA, ClamAV, conductual, FIM, proceso propio, Sysmon, cuarentena |
| 06 | [06-pentesting-red.md](06-pentesting-red.md) | `app/network/*`, `app/pentest/*`: nmap, sqlmap, ZAP, captura de paquetes, el guardrail de scope |
| 07 | [07-investigacion-forense.md](07-investigacion-forense.md) | `app/investigation/*`: casos, grafo, NER, fusión, timeline, log firmado Ed25519, export |
| 08 | [08-conocimiento-obsidian.md](08-conocimiento-obsidian.md) | `app/obsidian/*`, `reflect.py`, `research.py`, `app/ingestion/*` |
| 09 | [09-web-forms-credenciales.md](09-web-forms-credenciales.md) | `app/forms/*`, `tools/web_forms.py`: credential store DPAPI, preview_token |
| 10 | [10-control-pc-celular.md](10-control-pc-celular.md) | desktop, browser, pc_command, shell_exec, phone, phone_link, recording, video_frames |
| 11 | [11-servidor-fastapi.md](11-servidor-fastapi.md) | `main.py`, routers, auth, models, health |
| 12 | [12-tray-app.md](12-tray-app.md) | Arquitectura y módulos de la tray-app de escritorio |
| 13 | [13-android-app.md](13-android-app.md) | Arquitectura y módulos de la app Android |
| 14 | [14-seguridad-transversal.md](14-seguridad-transversal.md) | Todos los gates y controles de seguridad en un solo lugar |
| 15 | [15-configuracion.md](15-configuracion.md) | Todas las variables de entorno reales (`config.py` / `.env.example`) |

Al final de [14](14-seguridad-transversal.md) y en la sección "Pendiente" de este índice se listan
los componentes que quedaron para una segunda pasada de documentación.

---

## Qué quedó documentado vs. pendiente

**Documentado con detalle a nivel función:** todos los subsistemas del backend listados arriba
(01–11), la tray-app y la app Android a nivel arquitectura+módulos (12–13), y las capas transversales
de seguridad y configuración (14–15).

**Pendiente para una segunda pasada** (ver nota al pie de cada archivo correspondiente):
`app/tools/video_gen.py` e `image_gen.py` (ComfyUI, **desactivadas** — no importadas en el registro,
por precaución de hardware); detalle función-por-función de la tray-app y la app Android (acá se
cubre arquitectura + módulos); `install.ps1` (instalador); y los ~100 archivos de tests como corpus.
