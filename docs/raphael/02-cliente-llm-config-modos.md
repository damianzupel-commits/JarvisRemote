# 02 · Cliente LLM, clientes cloud y modos de operación

## `app/llm_client.py`

Un único objeto `client = AsyncOpenAI(base_url=settings.lmstudio_base_url, api_key=settings.llm_api_key,
timeout=settings.llm_request_timeout_seconds, max_retries=0)`.

- **Async a propósito:** uvicorn corre en un solo event loop y una inferencia local tarda decenas de
  segundos; el cliente síncrono bloquearía el loop entero (rompía la conexión WebSocket del celular en
  cada tool call). Todo el I/O contra el LLM es no-bloqueante.
- **`max_retries=0`:** desactiva los reintentos automáticos del SDK, que ante un timeout de una
  generación local legítimamente lenta reprocesaban el prompt entero desde cero (bug real v6). Los
  reintentos "buenos" (solo errores de conexión, con backoff, sobre todo para el modelo cloud) los
  agrega `agent._create_chat_completion` (ver [01](01-agente-y-loop.md)).
- **`timeout` = `LLM_REQUEST_TIMEOUT_SECONDS`** (1800 s) — generoso a propósito: mejor esperar de más
  que cortar una generación real en curso.
- El `base_url` (var `LMSTUDIO_BASE_URL`) hoy apunta a **Ollama** (`:11434`), no a LM Studio: el nombre
  quedó de una migración vieja. Ollama proxea transparentemente el modelo cloud `gpt-oss:120b-cloud`.

## `app/cloud_client.py`

`client = AsyncOpenAI(base_url=settings.google_ai_base_url, api_key=settings.google_ai_api_key or
"sin-configurar", max_retries=0)`. Instancia **separada** de `llm_client.client` (dos proveedores
distintos, keys/timeouts/modelos propios). Apunta al endpoint OpenAI-compatible real de Gemini
(`generativelanguage.googleapis.com/v1beta/openai/`). Lo usa exclusivamente `app/tools/cloud_expert.py`
(`cloud_expert_code` / `cloud_expert_marketing`) con `gemini-2.5-flash`. Sin `GOOGLE_AI_API_KEY`, esas
tools fallan con error claro.

## `app/operation_mode.py` — SUPERVISADO vs AUTÓNOMO

Resuelve la tensión potencia-vs-seguridad: permite que Raphael trabaje solo sin que un modo desatendido
tenga el mismo radio de daño que una sesión con Damian mirando en vivo.

### Los dos modos (`class OperationMode(enum.Enum)`)

- **`SUPERVISED`** ("supervised") — hay un humano usando Raphael en vivo (chat/voz). El sandbox de
  filesystem se **abre** a las raíces amplias (`Settings.fs_supervised_roots`, por default el HOME). La
  potencia de siempre: con Damian presente para frenar una macana, no se pierde capacidad.
- **`AUTONOMOUS`** ("autonomous") — Raphael corre solo (tareas programadas, CLIs, self-repair
  desatendido, loops de fondo). El sandbox se **acota** a las raíces chicas
  (`Settings.fs_allowed_roots`: proyecto + `FS_ALLOWED_ROOTS`). Radio de daño limitado.

### Diseño fail-safe

- El **default del proceso es AUTÓNOMO** (el más restrictivo), derivado una vez de la env var
  `JARVIS_OPERATION_MODE` por `_env_default_mode()` — cualquier valor vacío/desconocido cae a AUTÓNOMO,
  nunca a SUPERVISADO por accidente de tipeo.
- El modo vive en un **`ContextVar`** (`_current_mode`), no en una global: se setea por-invocación y no
  se filtra entre tareas asyncio concurrentes.
- Solo los **puntos de entrada interactivos** (código de confianza del server) declaran SUPERVISADO;
  cualquier entrada que no lo declare queda AUTÓNOMA por omisión.

### Guardrail anti-auto-escalada

`_agent_turn_active` (otro `ContextVar`, lo prende `agent.agent_turn_active()`) marca "hay un turno del
agente corriendo acá". Si algo intenta escalar AUTÓNOMO→SUPERVISADO con un turno del agente activo,
`operating_as` lanza `PermissionError`. Raphael no puede ampliarse los permisos de filesystem en runtime:
el modo lo fija el punto de entrada **antes** de arrancar el loop, nunca el modelo ni una tool.

### API del módulo

| Función | Qué hace |
|---------|----------|
| `current_mode() -> OperationMode` | El modo efectivo en este contexto |
| `is_supervised()` / `is_autonomous()` | Atajos booleanos |
| `effective_fs_roots() -> list[str]` | Puente con el sandbox: SUPERVISADO→`fs_supervised_roots`, AUTÓNOMO→`fs_allowed_roots`. Lo consume `filesystem._allowed_roots()` (único choke point) |
| `operating_as(mode, *, source)` (context manager) | Declara el modo para el bloque; `source` es una etiqueta legible que se loguea ("http_chat", "scheduler", "cli"); aplica el guardrail anti-escalada |
| `agent_turn_active()` (context manager) | Prende el flag de turno activo |

`main.chat` usa `with operating_as(OperationMode.SUPERVISED, source="http_chat")` — `/api/chat` es el
único punto de entrada interactivo (ventana, voz de la tray, chat del celular, todos pegan ahí).

Ver [15](15-configuracion.md) para las variables `FS_*` y `JARVIS_OPERATION_MODE`, y
[14](14-seguridad-transversal.md) para el modelo de seguridad completo.
