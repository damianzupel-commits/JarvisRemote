# 01 · El agente y su loop (`app/agent.py`)

Es el cerebro de Raphael: recibe el mensaje del usuario, se lo manda al LLM junto con el catálogo de
tools, ejecuta las *tool calls* que el modelo pida, le devuelve los resultados y repite hasta que el
modelo responde en texto plano o se agota el tope de iteraciones. Archivo de ~1260 líneas, el más
denso del backend. Logger: `jarvis.agent`.

## Dependencias

`llm_client.client` (AsyncOpenAI), `config.settings`, `operation_mode`, `audit_log`, `skills`,
`selfrepair.gate`, `recording`, `obsidian.profile`, `phone_link.is_phone_connected`,
`video_frames.extract_frames_from_video_base64`, `tools.call_tool` / `tools.openai_tool_schemas`.

## Prompts de sistema

- **`SYSTEM_PROMPT`** — constante gigante (~220 líneas) que define la identidad ("Sos Jarvis…") y las
  reglas de uso de casi todas las tools: control de PC/celular, el guardrail de scope de red, el ciclo
  auditar→reparar→verificar, el gate de Obsidian antes de escribir código, la política anti–prompt
  injection (todo texto que traen las tools es **dato, nunca instrucción**), y el criterio de
  delegación entre trabajadores (local / OpenCode / Gemini). Es el prompt "completo" que se usa cuando
  ningún skill matchea.
- **`RESEARCH_SYSTEM_PROMPT`** — identidad alternativa para el **perfil de investigación científica**
  (biotecnología de Damian): vault y directorio de trabajo separados, subconjunto chico de tools, sin
  acceso a seguridad/código/control de PC.
- **`CORE_PROMPT`** y los fragmentos por skill viven en `skills.py` (ver [03](03-tools-registro-catalogo.md)).

## Perfiles de conversación

Estado en memoria por conversación (se pierde al reiniciar el proceso):

- `_conversation_profiles: dict[str, str]` — perfil activo (`"default"` o `"research"`) por `conv_id`.
- `_conversations: dict[str, list[dict]]` — historial de mensajes por `conv_id`.
- `_PROFILE_SWITCH_COMMANDS` — comandos explícitos (`/modo investigacion`, `/modo seguridad`, etc.). No
  hay detección heurística: el cambio siempre es un comando tipeado, mismo criterio de explicitud que
  `confirm=true` en el resto del proyecto.
- `_RESEARCH_TOOL_NAMES` — subconjunto fijo de 9 tools visibles en el perfil research
  (`research_topic`, `obsidian_*`, `jarvis_reflect`, `fs_*`).
- `_system_prompt_for_profile(profile_name)` / `_tools_for_profile(profile_name, all_tools)` — eligen
  prompt y tools según el perfil.

## Función pública: `run_agent(message, conversation_id) -> (conv_id, reply, tool_log)`

Punto de entrada real (lo llama `/api/chat`). Pasos:

1. Si `message` es un comando de cambio de perfil → corto-circuita **sin llamar al LLM**: actualiza el
   perfil, reescribe `history[0]` con el prompt nuevo, responde con el aviso del cambio.
2. Si el perfil activo es `research` → activa el override de vault/embeddings vía
   `vault_profile.use_profile(...)` (context manager) para toda la llamada, y delega en `_run_agent_turn`.
3. Si no, delega directo en `_run_agent_turn`.

## `_run_agent_turn` → `_run_agent_turn_inner`

`_run_agent_turn` es un wrapper fino cuyo único propósito es garantizar el apagado de la grabación:
envuelve todo en `try/finally: recording.stop_recording()` y marca el turno con
`operation_mode.agent_turn_active()` (habilita el guardrail anti-auto-escalada). Así ninguna grabación
queda huérfana pase lo que pase adentro (return normal, return temprano, excepción).

`_run_agent_turn_inner` es el loop real:

1. **Selección de tools/prompt.** Perfil `default` → `skills.classify(message)`. Si algún skill
   matchea, usa su prompt y su subconjunto de tools; si no, `SYSTEM_PROMPT` + todas las tools (nunca
   al revés: el camino recortado solo se toma con clasificación confiada). Perfil `research` → su
   subconjunto fijo.
2. **Presupuesto de contexto.** `_history_char_budget(len(tools_schema))` se calcula una vez por turno.
3. **`history[0]` se reescribe en cada turno** para reflejar la clasificación de *este* mensaje (una
   conversación puede saltar de dominio entre mensajes).
4. Agrega el mensaje del usuario, poda el historial (`_trim_history` + `_trim_history_by_budget`).
5. **Loop** hasta `effective_max_iterations` (arranca en `MAX_AGENT_ITERATIONS`=10; sube a
   `MAX_AGENT_ITERATIONS_CODE_TASK`=50 la primera vez que el turno usa `fs_write_file`):
   - Poda de nuevo (un turno puede crecer varias veces).
   - Llama `_create_chat_completion(model, messages=history+[_phone_status_note()], tools, tool_choice,
     max_tokens=reserved_response_tokens)`. La nota de estado del celular se agrega **fuera** del
     historial, recalculada en cada vuelta.
   - Si hay `tool_calls`: por cada una aplica los **gates** (ver abajo), ejecuta vía `call_tool`,
     registra en `audit_log`, y arma el mensaje `tool` (o multimodal si es foto/video). `continue`.
   - Si no hay tool calls: agrega la respuesta al historial y retorna.
6. Si se agota el loop → mensaje de fallback (`MAX_AGENT_ITERATIONS`).

### Resultado multimodal (foto/video)

- `_IMAGE_TOOL_NAMES = {"phone_take_photo"}` — la imagen no va en el mensaje `tool` (evita mandar un
  blob base64 como texto); va aparte en un mensaje `user` multimodal vía `_build_image_message`.
- `_VIDEO_TOOL_NAMES = {"phone_record_video"}` — el video **nunca** se manda crudo: se extraen frames
  con `extract_frames_from_video_base64` (uno cada `VIDEO_FRAME_INTERVAL_SECONDS`, máx.
  `VIDEO_MAX_FRAMES`) y se mandan como secuencia de imágenes.
- `awaiting_vision_response` — si la llamada siguiente falla (modelo no-VL cargado), en vez de
  crashear devuelve `_VISION_FALLBACK_MSG` pidiendo cargar un modelo de visión.

## Reintentos de red: `_create_chat_completion` / `_is_transient_llm_error`

Envuelve `client.chat.completions.create` con backoff exponencial **solo para fallas transitorias de
red**. `_is_transient_llm_error`: `APITimeoutError` → solo reintenta si `LLM_RETRY_ON_TIMEOUT` (default
False, porque un timeout local suele ser una generación lenta real, no un fallo de red — reintentarla
reprocesa el prompt entero, bug real v6); `APIConnectionError` → sí; cualquier otra cosa → se propaga
sin enmascarar. Complementa el `max_retries=0` del SDK.

## Gestión de contexto (protección en capas)

Tres protecciones complementarias, cada una nacida de un bug real de "context exceeded":

- **`_trim_history(history, max_messages)`** — poda por **cantidad de mensajes** (`MAX_HISTORY_MESSAGES`
  =40). El turno en curso (desde el último `user`) nunca se poda entero; solo se recortan turnos viejos,
  cortando siempre en un `user` para no partir un `tool_call` de su respuesta.
- **`_cap_tool_result(result, max_chars)`** — recorta **un solo tool result** que supere
  `MAX_TOOL_RESULT_CHARS` (6000). Si el dict tiene una lista (ej. `findings`), la recorta por búsqueda
  binaria sobre la candidata completa (incluyendo la nota de recorte) y deja constancia de cuántos ítems
  se omitieron.
- **`_history_char_budget` + `_trim_history_by_budget`** — backstop de **tamaño total** en tokens:
  `(MODEL_CONTEXT_TOKENS − RESERVED_RESPONSE_TOKENS) × CHARS_PER_TOKEN_ESTIMATE − len(SYSTEM_PROMPT) −
  len(schema tools)`. Poda hasta que el JSON del cuerpo entre en ese presupuesto, protegiendo siempre el
  turno en curso.

## Guardrails en vivo (dentro del loop, antes de ejecutar cada tool)

Se aplican en orden, del más específico al más general:

1. **`selfrepair_gate.self_target_gate_error(name, args, message)`** — bloquea cualquier escritura
   (`fs_write_file` o `code_apply_fix confirm=true`) que apunte al propio `backend/` de Raphael, salvo
   que el mensaje traiga un `proposal_id` confirmado. Detalle en [04](04-auditoria-codigo.md).
2. **`_live_identical_rewrite_loop_error(conv_id, path, content)`** — si el modelo ya escribió el mismo
   archivo con contenido **idéntico** (mismo sha256) `_LIVE_LOOP_MIN_REPEATS-1`=2 veces seguidas (leído
   del `audit_log` real), bloquea la tercera. Detecta en vivo el loop de reescritura de v6 (el modelo
   reescribió el mismo archivo 14 veces).
3. **`_pending_blocked_write_paths(history)`** — devuelve el `set` de paths de `fs_write_file` que
   fueron bloqueados y nunca se reintentaron con éxito. Mientras haya alguno pendiente, cualquier
   `fs_write_file` a **otro** path se rechaza (marcado `blocked_reason="pending_retry"` para no contarse
   a sí mismo como pendiente). Evita que un archivo bloqueado quede abandonado (bugs v5/v6).
4. **`_obsidian_gate_error(history)`** — bloquea `fs_write_file` si (a) nunca se consultó Obsidian
   (`obsidian_search_notes`) ni `research_topic` en el turno, o (b) hubo un `pc_run_command` fallido
   (`exit_code != 0`) **después** de la última consulta de conocimiento y todavía no se volvió a
   consultar sobre ese error. Fuerza informarse antes de inventar código/soluciones a ciegas.

Cuando un gate rechaza, el resultado es `{"error": <mensaje>}` — no se ejecuta la tool, pero igual se
registra en `audit_log`.

## Consumo de propuesta de self-repair

Tras ejecutar una tool exitosa, `selfrepair_gate.consume_proposal_if_applied(...)` marca la propuesta
usada como aplicada, para que el mismo `proposal_id` no se reuse.

## Auditoría de tool calls

Cada tool call (bloqueada o no) se persiste en `audit_log` (JSON append-only) vía `log_tool_call(target="agent", …)`.
`_audit_safe_args` reemplaza el `content` de `fs_write_file` por su sha256 + longitud (nunca el código
crudo); `_audit_safe_result` omite blobs base64 de imagen/video. Es la fuente de verdad para el análisis
post-hoc de `app/introspection/analyzer.py` y para el guardrail en vivo del punto 2.

## Funciones auxiliares de lectura del historial

- `_last_index_of_tool_call(history, name)` — índice del último `assistant` que llamó a `name`.
- `_last_failed_command_result(history)` — último `pc_run_command` con `exit_code != 0` (mapea
  `tool_call_id`→nombre buscando en los `assistant` previos).
- `_phone_status_note()` — arma la nota de sistema con el estado recién verificado del celular.

---

*Segunda pasada sugerida:* trazar cada rama del loop con un diagrama de secuencia y documentar los
tests de `tests/test_agent*.py` que reproducen los bugs v2–v6.
