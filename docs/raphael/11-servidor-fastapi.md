# 11 · Servidor FastAPI: rutas, autenticación, arranque

## `app/main.py` — la aplicación

`app = FastAPI(title="Jarvis Remote Backend", version="0.1.0")`. Configura logging
(`configure_logging()`) y monta tres routers: codebase, obsidian, investigation.

### Startup — servicios de malware en background
`@app.on_event("startup") _start_malware_protection()`:
- `behavioral_watcher.start_watching()` — escaneo on-access (thread propio del Observer de watchdog).
- `asyncio.create_task(fullscan.full_scan_loop())` — escaneo completo diario (tarea asyncio que espera
  su delay inicial y se repite sola).

Ninguno bloquea el arranque del server. Ver [05](05-malware-defensa.md).

### Endpoints

| Método | Ruta | Auth | Qué hace |
|--------|------|------|----------|
| GET | `/api/health` | no | `{status, phone_connected, network_candidates}` — el celular usa `network_candidates` (de `network_info.py`) para preferir conexión directa sobre Tailscale |
| GET | `/api/health/deep` | no | Ejercita el **loop del LLM de verdad** (round-trip mínimo, sin tools, timeout corto 30 s) para confirmar que el modelo responde, no solo que el puerto está abierto. Prerequisito de un futuro watchdog de self-restart |
| POST | `/api/chat` | **Bearer** | Punto de entrada interactivo único. Declara `operating_as(SUPERVISED, source="http_chat")` y llama `run_agent(message, conversation_id)`. Devuelve `ChatResponse` |
| WS | `/ws/phone` | Bearer (header) | Conexión saliente del celular; autentica con `_check_bearer`, registra la conexión y despacha tool calls (ver `phone_link`) |

`/api/chat` es el único camino que declara **SUPERVISADO**: hay un humano del otro lado (ventana, voz de
la tray, o chat del celular). Cualquier otro camino (tareas programadas, CLIs, loops de fondo) queda
**AUTÓNOMO** por el default fail-safe del `ContextVar`. Ver [02](02-cliente-llm-config-modos.md).

## `app/auth.py`

`verify_api_key(authorization)` — dependencia de FastAPI. Exige header `Authorization: Bearer <token>` y
compara contra `settings.api_key`; si falta o no matchea, `HTTPException 401`. El WebSocket usa la misma
validación vía `_check_bearer`.

## `app/models.py`

Modelos Pydantic del endpoint de chat: `ChatRequest` (`message`, `conversation_id?`), `ToolCallLog`
(`tool`, `arguments`, `result`), `ChatResponse` (`conversation_id`, `reply`, `tool_calls`).

## `app/logging_config.py`

`configure_logging()` — logging general a **consola + archivo rotativo** (`general.log`, 5 MB × 5). Con
`force=True` (basicConfig es no-op si el root logger ya tiene handlers). Complementa el `audit_log.py`
(JSON estructurado por evento, con `propagate=False`) — este es texto libre para diagnóstico en vivo.

## Routers (`app/routers/`)

Todos con `dependencies=[Depends(verify_api_key)]` (Bearer). Son de solo lectura para las vistas de la
tray-app.

### `/api/codebase` (`codebase.py`)
- `GET /recent` — proyectos indexados recientemente.
- `GET /index?path=&refresh=` — índice de un proyecto (`get_or_build`).
- `GET /graph?path=` — grafo de archivos/imports.
- `GET /file?path=&file=` — outline + contenido de un archivo.

### `/api/obsidian` (`obsidian.py`)
- `GET /notes?author=&tag=` — lista notas.
- `GET /graph` — grafo de notas/wikilinks (coloreado por autor).
- `GET /notes/{author}/{slug}` — una nota.
- `POST /notes` — crea/actualiza una nota (modelo `NoteIn`; solo notas **humanas** desde la UI).
- `DELETE /notes/{author}/{slug}` — borra una nota humana.

### `/api/investigation` (`investigation.py`)
- `GET /cases` — lista de casos.
- `GET /{case_id}/graph` — grafo de entidades/aristas (coloreado por tipo, con halo de centralidad+
  confianza; `_load_active_case` reconstruye desde el log).
- `GET /{case_id}/timeline?entity_id=` — timeline forense del caso o de una entidad.

## `app/audit_log.py`

Logger de auditoría estructurado, **separado** del logging general: JSON por línea, rotación por tamaño,
`propagate=False`. `log_tool_call(target, tool, arguments, result, error, conversation_id)` y
`read_entries(target=, tool=, conversation_id=)`. Responde "qué hizo Raphael mientras no miraba": cada
tool call del agente, del escritorio y del celular queda acá, fácil de grepear con `jq`. Es la fuente de
datos del guardrail en vivo de reescrituras y del análisis post-hoc de `introspection/`.

## `app/network_info.py`

`network_candidates(port)` — detecta las IPv4 locales (`_local_ipv4_addresses`) y las clasifica
(`_classify`): `hotspot` (192.168.137/24) < `lan` (privadas) < `tailscale` (100.64/10), ignorando
loopback/link-local y **nunca ofreciendo una IP pública**. Devuelve la lista ordenada (directo primero)
que consume `/api/health`. `TAILSCALE_RANGE` se reusa desde `network/guardrail.py`.

## Entrypoint: `backend/run.py`
Levanta uvicorn con `HOST`/`PORT` (defaults `0.0.0.0:8000`) y, si `TLS_ENABLED`, con el cert/key
(`TLS_CERT_PATH`/`TLS_KEY_PATH`). TLS está **apagado por default** (ver [14](14-seguridad-transversal.md)).
