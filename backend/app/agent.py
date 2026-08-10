"""Loop del agente: manda la conversación a LM Studio, ejecuta las tool calls que
pida el modelo, le devuelve los resultados, y repite hasta que responda en texto
plano o se llegue al tope de iteraciones.
"""

import json
import logging
from typing import Any

from .config import settings
from .llm_client import client
from .phone_link import is_phone_connected
from .tools import call_tool, openai_tool_schemas
from .video_frames import extract_frames_from_video_base64

logger = logging.getLogger("jarvis.agent")

SYSTEM_PROMPT = (
    "Sos Jarvis, un asistente que corre localmente en la PC del usuario y que puede "
    "ejecutar acciones reales a través de herramientas: sistema de archivos, ejecución de "
    "comandos de shell reales en la PC (pc_run_command) y control del navegador en la PC, "
    "control general del escritorio de la PC (lanzar programas, "
    "mouse, teclado, ventanas de cualquier programa abierto: screenshot, listar/enfocar "
    "ventanas, click por coordenadas o por control, escribir texto, combinaciones de teclas, "
    "mover mouse, scroll), y —si hay un celular conectado— abrir apps, leer/escribir archivos, "
    "controlar la pantalla (tocar, deslizar, escribir, leer contenido), tomar fotos con la cámara "
    "(phone_take_photo) o grabar un clip corto (phone_record_video) para 'ver' el entorno, y "
    "ejecutar comandos de shell reales (vía Termux) en el celular. Usá phone_take_photo para una "
    "imagen fija y phone_record_video solo cuando haga falta capturar movimiento o una secuencia "
    "que una sola foto no explique — el video nunca se manda crudo al modelo: el backend extrae "
    "varios frames del clip y te los manda como una secuencia de imágenes, así que vas a ver "
    "'varios momentos', no un video fluido. Ambas tools solo sirven para describir/identificar lo "
    "que ven si el modelo cargado ahora mismo en LM Studio es un modelo de visión (VL) — con un "
    "modelo de solo texto la foto/video se captura igual pero vas a recibir un aviso de que no "
    "podés verla; en ese caso decíselo al usuario tal cual (que cambie a un modelo VL en LM "
    "Studio), no inventes una descripción de la imagen. phone_run_command es para lo que necesite un intérprete o "
    "herramientas de línea de comandos de verdad (scripts, python, git, etc.) — no la uses para "
    "interactuar con la UI de apps, para eso están phone_tap/phone_swipe/phone_type_text/"
    "phone_global_action. phone_run_command depende de que el usuario tenga Termux instalado y "
    "configurado (no es automático): si falla, el mensaje va a decir qué falta (Termux no instalado, "
    "allow-external-apps no seteado, o el permiso Android no otorgado) — contáselo tal cual al "
    "usuario, no asumas que el comando corrió. nmap_scan corre un escaneo de red REAL (puertos, "
    "servicios, versiones, y con scan_type='vuln' scripts NSE de vulnerabilidades conocidas) -- a "
    "diferencia de security_scan_project/quality_scan_project (que solo leen código/manifiestos en "
    "disco, nunca tocan una red real), esta tool sí interactúa con sistemas de red de verdad, así que "
    "tiene el límite más estricto de todas: por default SOLO puede escanear rangos privados/reservados "
    "(10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), loopback (127.0.0.0/8) o el rango fijo de Tailscale "
    "(100.64.0.0/10) -- un guardrail técnico real (app/network/guardrail.py), no una convención que vos "
    "puedas decidir relajar. Si el usuario pide escanear una IP pública, un dominio de terceros, o "
    "cualquier cosa que no sea claramente su propia red/infraestructura (ej. 'la wifi del vecino', 'la "
    "web de tal empresa', una IP que no reconocés como privada), RECHAZALO vos mismo de entrada -- no "
    "lo intentes, no pidas confirmación blanda ('¿estás seguro?'): explicale que escanear sistemas que "
    "no son suyos y sin autorización explícita del dueño puede ser ilegal (leyes de acceso no "
    "autorizado / computer fraud en la mayoría de países), y que si de verdad tiene autorización para "
    "escanear esa IP/dominio, tiene que agregarla él mismo a mano a NMAP_AUTHORIZED_TARGETS en "
    "backend/.env -- ni vos ni la tool pueden ampliar ese scope. Si la tool falla porque nmap no está "
    "instalado, decíselo tal cual (instalación manual, requiere un click de UAC que no se puede "
    "automatizar) en vez de asumir que corrió. Tenés DOS formas de hacer este reconocimiento de red, y "
    "elegís según DONDE está el objetivo, no según qué tan comoda sea cada una: nmap_scan corre desde "
    "la PC (util para la LAN de casa/infraestructura propia de la PC), y phone_nmap_scan corre desde el "
    "CELULAR conectado (util para cualquier red a la que el celular esté conectado en ese momento, ej. "
    "la wifi de un local/restaurante/oficina de un cliente que le dio la contraseña al usuario) -- la "
    "PC y el celular pueden estar en redes físicas completamente distintas aunque el celular hable con "
    "vos por Tailscale, así que nmap_scan NUNCA puede ver la red del celular ni viceversa: si el "
    "usuario pide escanear 'la wifi del restaurante donde estoy' o cualquier red que claramente no es "
    "la de su casa, usá phone_nmap_scan, no nmap_scan (fallaría o escanearía la red equivocada). Las "
    "dos comparten el mismo guardrail de scope no negociable de arriba -- correr desde el celular no lo "
    "relaja ni un poco, el mismo criterio de autorización aplica sin importar el dispositivo. "
    "phone_nmap_scan además necesita que el celular tenga el paquete nmap de Termux instalado ('pkg "
    "install nmap', sin root); si falta, decíselo al usuario tal cual en vez de asumir que corrió. Para "
    "abrir un programa en la PC usá SIEMPRE desktop_launch_app — nunca simules Win+buscar+"
    "escribir+enter con desktop_press_key/desktop_type_text para lanzar una app: esa secuencia "
    "es frágil (la tecla Windows simulada no siempre abre el menú Inicio de verdad) y no está "
    "garantizada. desktop_launch_app ya deja la ventana nueva al frente con foco real antes de "
    "devolver el resultado, pero revisá igual el campo 'focused': si es false, Windows puede haber "
    "bloqueado el cambio de foco (su propia política de seguridad) aunque la ventana se haya lanzado "
    "bien — en ese caso el resultado igual trae el 'pid' de esa ventana, y el paso correcto es "
    "reintentar con desktop_focus_window(pid=<ese pid>), NO con 'title': si hay varias ventanas de la "
    "misma app abiertas (ej. varios Bloc de notas de intentos anteriores), buscar por título puede "
    "enfocar la ventana equivocada en vez de la que se acaba de lanzar. Las tools de escritorio no "
    "pueden interactuar con ventanas elevadas (UAC / 'Ejecutar como administrador') por una "
    "restricción de Windows, no un bug, y el matching por 'title' de desktop_focus_window/"
    "desktop_click_element es por substring: revisá siempre el campo 'process' del resultado para "
    "confirmar que encontró la app correcta antes de asumir éxito solo porque no tiró error. "
    "Cuando el usuario te pida crear un proyecto de código nuevo (no solo auditar uno existente): "
    "escribí los archivos reales con fs_write_file, incluyendo un manifiesto de dependencias "
    "(requirements.txt para Python, package.json para Node, etc. según corresponda) para que el "
    "proyecto sea reproducible sin que el usuario tenga que adivinar qué instalar — y después NO "
    "te quedes en 'debería funcionar': usá pc_run_command para instalar esas dependencias de "
    "verdad y para correr los tests que hayas escrito antes de decirle al usuario que está listo. "
    "Si el proyecto es de PYTHON: NUNCA instales dependencias con el pip global de la PC — creá "
    "primero un entorno virtual DENTRO de la carpeta del proyecto con 'python -m venv .venv' (cwd "
    "apuntando a esa carpeta), y a partir de ahí usá SIEMPRE el intérprete de ESE venv para todo lo "
    "demás: '.venv\\Scripts\\python.exe -m pip install -r requirements.txt' para instalar (con -m "
    "pip, no el pip.exe del venv directo) y '.venv\\Scripts\\python.exe -m pytest' para correr los "
    "tests (con -m pytest, no el pytest.exe del venv directo — invocar con -m además evita un problema "
    "real ya visto de imports rotos: agrega el cwd a sys.path, algo que el binario pytest.exe a secas "
    "no hace). Nunca uses 'pip install'/'pytest' a secas (eso pega en el Python global de la PC del "
    "usuario, contaminándolo con paquetes de un proyecto de prueba) ni asumas que el venv ya existe: "
    "si no lo creaste vos en este mismo proyecto, creálo antes de instalar nada. Si el proyecto es de "
    "NODE/JS no hace falta nada de esto — npm ya aísla las dependencias por carpeta con node_modules, "
    "así que 'npm install'/'npm test' directo están bien. Contale el resultado REAL de esa corrida "
    "(qué tests pasaron, cuáles fallaron, el stderr si algo rompió) en vez de asumir que el código "
    "compila o los tests pasan solo porque lo escribiste — leé 'exit_code' y 'timed_out' del resultado "
    "de pc_run_command, no solo el stdout. pc_run_command es shell real y arbitrario, el nivel más "
    "invasivo de las tools de PC: "
    "usalo para lo que pidió el usuario (instalar deps, correr tests/builds, git, etc.), no para "
    "acciones que no te pidió. Si falla porque está deshabilitada (PC_SHELL_ENABLED=false) o el "
    "comando matcheó el blocklist de seguridad, decíselo al usuario tal cual en vez de asumir que "
    "corrió. Usá las "
    "herramientas cuando haga falta para cumplir el pedido en vez de "
    "inventar la respuesta. Si una tool de celular falla porque no hay ningún celular "
    "conectado, decíselo al usuario en vez de asumir que la acción se hizo. Si una tool "
    "falla, contale al usuario qué pasó en vez de asumir que funcionó. Respondé siempre "
    "en el mismo idioma en el que te escribe el usuario. Tenés una memoria de reflexión propia "
    "(jarvis_reflect) separada del historial de esta conversación: usá jarvis_reflect(action='query', "
    "topic=...) antes de actuar en una tarea ambigua o compleja, para ver si ya encontraste una "
    "decisión o criterio relevante en el pasado, y jarvis_reflect(action='save', insight=...) después "
    "de resolver algo no trivial, para dejar registro de la decisión y el porqué (no la uses para "
    "datos triviales o el estado de una tarea puntual, es para criterio que valga la pena recordar "
    "en conversaciones futuras).\n\n"
    "Antes de cada mensaje del usuario vas a ver una nota de sistema con el estado ACTUAL "
    "y recién verificado de la conexión del celular. Ese estado puede cambiar de un mensaje "
    "a otro (el usuario puede conectar o desconectar el celular en cualquier momento), así "
    "que confiá siempre en esa nota más reciente por sobre cualquier cosa que hayas dicho "
    "vos antes en esta misma conversación sobre si hay un celular conectado o no."
)


def _phone_status_note() -> dict:
    connected = is_phone_connected()
    return {
        "role": "system",
        "content": (
            "[Estado actual, verificado ahora mismo] Celular conectado: "
            + ("SÍ" if connected else "NO")
            + (
                ". Las tools phone_* deberían funcionar."
                if connected
                else ". Las tools phone_* van a fallar hasta que el usuario conecte el celular."
            )
        ),
    }


# Historial de conversación en memoria, por conversation_id. Se pierde al reiniciar
# el proceso (suficiente para v1; si hace falta persistencia se cambia por un store).
_conversations: dict[str, list[dict]] = {}

# Tools cuyo resultado trae una imagen que hay que mandarle al modelo como contenido
# multimodal (ver `_build_image_message`), no como el texto plano de un mensaje 'tool'
# normal.
_IMAGE_TOOL_NAMES = {"phone_take_photo"}

# Tools cuyo resultado trae un video: en vez de mandarlo crudo (no confiable en el
# server local de LM Studio), se extraen frames (ver `video_frames.py`) y se mandan
# como una secuencia de imágenes en un solo mensaje (ver `_build_multi_image_message`).
_VIDEO_TOOL_NAMES = {"phone_record_video"}

_VISION_FALLBACK_MSG = (
    "La foto/video se capturó bien, pero el modelo que está cargado ahora mismo en LM Studio no "
    "puede ver imágenes (no es un modelo de visión). Para que Jarvis pueda describir lo que ve la "
    "cámara, cambiá a un modelo VL en LM Studio (ej. Qwen3-VL-30B-A3B-Instruct) y probá de nuevo."
)


def _build_multi_image_message(frames_base64: list[str], caption: str, mime_type: str = "image/jpeg") -> dict:
    """Arma un mensaje multimodal (formato de contenido de OpenAI) con una o varias
    imágenes en un solo mensaje 'user' — el mismo mensaje puede llevar N imágenes, que
    es justo lo que se usa para mandar los frames extraídos de un video de una sola
    vez (ver `video_frames.py`)."""
    content: list[dict] = [{"type": "text", "text": caption}]
    for frame_b64 in frames_base64:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{frame_b64}"}}
        )
    return {"role": "user", "content": content}


def _build_image_message(result: dict) -> dict:
    """Arma el mensaje multimodal con la imagen que devolvió una tool de
    `_IMAGE_TOOL_NAMES` (una sola foto — ver `_build_multi_image_message` para el
    caso de varios frames de un video)."""
    return _build_multi_image_message(
        [result["image_base64"]],
        "(Foto recién tomada con la cámara del celular, adjunta arriba.)",
        mime_type=result.get("mime_type", "image/jpeg"),
    )


def _cap_tool_result(result: Any, max_chars: int) -> Any:
    """Recorta un resultado de tool cuyo JSON serializado supera `max_chars` --
    protección aparte de `_trim_history` (que poda por CANTIDAD de mensajes, no por
    tamaño): un solo tool result gigante (ej. security_scan_project sobre un
    proyecto con cientos de hallazgos, ~47KB de JSON real visto en pygoat) puede
    consumir sola casi toda la ventana de contexto real del modelo, desplazando el
    system prompt y el pedido original del usuario fuera de contexto sin que
    `_trim_history` lo detecte (sigue siendo "un solo mensaje").

    Si `result` es un dict con algún campo lista (típicamente 'findings' o similar),
    recorta esa lista al tamaño más grande que entre en el presupuesto y deja
    constancia de cuántos items se omitieron -- mismo patrón que ya usan
    security_scan_project/quality_scan_project con su cap de 100, pero por tamaño
    real en vez de cantidad fija de items. Si no hay campo lista que recortar
    (resultado ya es chico en estructura pero con algún string enorme, u otro tipo),
    cae a un truncado de texto plano como último recurso."""
    serialized = json.dumps(result, default=str, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return result

    if isinstance(result, dict):
        list_keys = [k for k, v in result.items() if isinstance(v, list) and v]
        if list_keys:
            biggest_key = max(
                list_keys,
                key=lambda k: len(json.dumps(result[k], default=str, ensure_ascii=False)),
            )
            items = result[biggest_key]

            def _build(n: int) -> dict:
                candidate = dict(result)
                candidate[biggest_key] = items[:n]
                candidate[f"{biggest_key}_omitted_by_size_limit"] = len(items) - n
                candidate["_note"] = (
                    f"Resultado recortado: '{biggest_key}' tenía {len(items)} items, se mandaron "
                    f"{n} para no exceder el contexto del modelo. Si necesitás el resto, "
                    "pedí un filtro más específico o llamá la tool de nuevo con más detalle puntual."
                )
                return candidate

            # Búsqueda binaria sobre la CANDIDATA COMPLETA (incluyendo la nota, no
            # solo la lista recortada) -- si se bisecta sin la nota y recién se
            # agrega al final, el resultado final puede terminar pasándose del
            # presupuesto por el tamaño de la nota misma.
            lo, hi = 0, len(items)
            best_n = 0
            while lo <= hi:
                mid = (lo + hi) // 2
                if len(json.dumps(_build(mid), default=str, ensure_ascii=False)) <= max_chars:
                    best_n = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            return _build(best_n)

    return {
        "_note": "Resultado recortado: era demasiado grande para mandarlo entero sin exceder el contexto del modelo.",
        "truncated_content": serialized[:max_chars],
    }


def _trim_history(history: list[dict], max_messages: int) -> None:
    """Recorta `history` in-place si el cuerpo (todo menos el system prompt en
    [0]) supera `max_messages`. Corta siempre en el próximo mensaje 'role':'user'
    para no dejar un tool_call sin su respuesta (o viceversa), lo cual rompe el
    pedido al modelo. Corte simple por cantidad de mensajes, no por tokens reales
    -- ver `_trim_history_by_budget` para la poda que sí mira tamaño real."""
    body = history[1:]
    excess = len(body) - max_messages
    if excess <= 0:
        return
    cut = excess
    while cut < len(body) and body[cut].get("role") != "user":
        cut += 1
    history[1:] = body[cut:]


def _history_char_budget(tools_schema_chars: int) -> int:
    """Cuántos caracteres de `history` (todo menos el system prompt en [0]) entran
    sin superar el contexto REAL del modelo cargado, dejando aparte margen para
    que pueda generar una respuesta después de "leer" todo el prompt.

    Bug real 2026-08-09: con 51 tools ya registradas, el system prompt (~9.7KB)
    + el schema de tools (~42KB) SOLOS ya representan ~13-16k tokens estimados
    contra un num_ctx de 16384 -- `_trim_history` (poda por CANTIDAD de
    mensajes) y `_cap_tool_result` (acota UN SOLO mensaje) no alcanzan a
    evitarlo: varios tool results medianos, cada uno ya bajo su propio tope
    individual, sumados igual superan lo poco que queda de contexto. Un pedido
    real (security_scan_project sobre pygoat) llegó a 16372/16384 tokens de
    prompt, tardó varios minutos SOLO en prompt-processing (con `ollama ps`
    reportando carga mixta CPU/GPU, el throughput se degrada con el contexto en
    este hardware) y nunca llegó a generar respuesta -- el contexto real del
    modelo se subió a 32768 (ver MODEL_CONTEXT_TOKENS) para dar aire, pero este
    presupuesto es la protección de fondo: sin importar qué tan grande se ponga
    el schema de tools a futuro (quedan creciendo con cada tool nueva que se
    registra), esto SIEMPRE deja margen real para el system prompt y la
    respuesta, recalculando en cada turno en vez de asumir un tamaño fijo."""
    available_tokens = settings.model_context_tokens - settings.reserved_response_tokens
    available_chars = available_tokens * settings.chars_per_token_estimate
    baseline_chars = len(SYSTEM_PROMPT) + tools_schema_chars
    return max(0, int(available_chars - baseline_chars))


def _trim_history_by_budget(history: list[dict], budget_chars: int) -> None:
    """Poda `history` in-place (todo menos el system prompt en [0]) hasta que el
    JSON serializado del cuerpo entre en `budget_chars` -- backstop de TAMAÑO
    real, complementario a `_trim_history` (cantidad de mensajes) y
    `_cap_tool_result` (un solo mensaje). Ver `_history_char_budget` para el
    bug real que lo motivó. Mismo criterio de corte que `_trim_history`: corta
    siempre en el próximo mensaje 'role':'user', para no separar un tool_call
    de su respuesta."""
    body = history[1:]
    if not body:
        return

    def _fits(msgs: list[dict]) -> bool:
        return len(json.dumps(msgs, default=str, ensure_ascii=False)) <= budget_chars

    if _fits(body):
        return

    cut = 0
    while cut < len(body):
        cut += 1
        while cut < len(body) and body[cut].get("role") != "user":
            cut += 1
        if _fits(body[cut:]):
            break
    history[1:] = body[cut:]


async def run_agent(message: str, conversation_id: str | None) -> tuple[str, str, list[dict]]:
    conv_id = conversation_id or "default"
    tools = openai_tool_schemas()
    # Se mide una sola vez por turno (no cambia mientras corre run_agent) y se
    # reusa en cada pasada del loop de abajo -- ver _history_char_budget.
    history_budget_chars = _history_char_budget(len(json.dumps(tools, default=str, ensure_ascii=False)))

    history = _conversations.setdefault(conv_id, [{"role": "system", "content": SYSTEM_PROMPT}])
    history.append({"role": "user", "content": message})
    _trim_history(history, settings.max_history_messages)
    _trim_history_by_budget(history, history_budget_chars)

    tool_log: list[dict] = []
    # Si el turno anterior le acaba de mandar una imagen al modelo (ver
    # `_build_image_message`), la próxima llamada puede fallar con un modelo que no
    # sea de visión — en ese caso no hay que crashear, hay que avisarle al usuario
    # que cambie de modelo (ver docstring de `_VISION_FALLBACK_MSG`).
    awaiting_vision_response = False

    for _ in range(settings.max_agent_iterations):
        # Poda también acá adentro (no solo al entrar): un turno con muchas
        # tool calls puede hacer crecer `history` varias veces dentro del
        # mismo `run_agent`, antes de volver a pasar por la poda de arriba.
        _trim_history(history, settings.max_history_messages)
        _trim_history_by_budget(history, history_budget_chars)
        # La nota de estado se arma de nuevo en cada vuelta del loop (por si el celular
        # se conecta/desconecta durante una tarea larga) y no se guarda en `history`:
        # así siempre es el estado real al momento de la llamada, no una foto vieja que
        # se vuelve stale (o contradice lo que el modelo dijo antes) a medida que la
        # conversación crece.
        try:
            response = await client.chat.completions.create(
                model=settings.lmstudio_model,
                messages=history + [_phone_status_note()],
                tools=tools or None,
                tool_choice="auto" if tools else None,
            )
        except Exception as exc:
            if awaiting_vision_response:
                logger.warning(
                    "LLM call tras phone_take_photo falló (probablemente el modelo cargado no es VL): %s",
                    exc,
                )
                history.append({"role": "assistant", "content": _VISION_FALLBACK_MSG})
                return conv_id, _VISION_FALLBACK_MSG, tool_log
            raise
        awaiting_vision_response = False
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            history.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                }
            )
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                logger.info("tool_call name=%s args=%s", tc.function.name, args)
                try:
                    result = await call_tool(tc.function.name, args)
                except Exception as exc:  # las tools pueden fallar por muchas razones distintas
                    logger.warning("tool_call failed name=%s error=%s", tc.function.name, exc)
                    result = {"error": str(exc)}
                tool_log.append({"tool": tc.function.name, "arguments": args, "result": result})

                if tc.function.name in _IMAGE_TOOL_NAMES and "image_base64" in result:
                    # El mensaje 'tool' no lleva el base64 crudo: mandarle un blob de
                    # decenas de KB como texto a un modelo que puede ni ser VL infla el
                    # historial (y el contexto) para nada — la imagen de verdad va
                    # aparte, como mensaje multimodal, en el formato que entiende un VL.
                    tool_summary = {k: v for k, v in result.items() if k != "image_base64"}
                    tool_summary["note"] = "imagen adjunta en el siguiente mensaje"
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(tool_summary, default=str, ensure_ascii=False),
                        }
                    )
                    history.append(_build_image_message(result))
                    awaiting_vision_response = True
                elif tc.function.name in _VIDEO_TOOL_NAMES and "video_base64" in result:
                    try:
                        frames = extract_frames_from_video_base64(
                            result["video_base64"],
                            interval_seconds=settings.video_frame_interval_seconds,
                            max_frames=settings.video_max_frames,
                        )
                    except Exception as exc:  # decode puede fallar por muchas razones (VideoDecodeError u otras)
                        logger.warning("no se pudieron extraer frames del video: %s", exc)
                        error_result = {"error": f"No se pudo procesar el video capturado: {exc}"}
                        tool_log[-1]["result"] = error_result
                        history.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(error_result, default=str, ensure_ascii=False),
                            }
                        )
                        continue

                    tool_summary = {k: v for k, v in result.items() if k != "video_base64"}
                    tool_summary["frames_extracted"] = len(frames)
                    tool_summary["note"] = f"{len(frames)} frame(s) del video adjuntos en el siguiente mensaje"
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(tool_summary, default=str, ensure_ascii=False),
                        }
                    )
                    history.append(
                        _build_multi_image_message(
                            frames,
                            f"({len(frames)} frames extraídos del video recién grabado con la cámara "
                            "del celular, uno cada "
                            f"{settings.video_frame_interval_seconds}s aprox., adjuntos arriba.)",
                        )
                    )
                    awaiting_vision_response = True
                else:
                    capped_result = _cap_tool_result(result, settings.max_tool_result_chars)
                    if capped_result is not result:
                        tool_log[-1]["result"] = capped_result
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(capped_result, default=str, ensure_ascii=False),
                        }
                    )
            continue

        history.append({"role": "assistant", "content": msg.content})
        return conv_id, msg.content or "", tool_log

    fallback = "No pude terminar la tarea dentro del límite de pasos permitidos (MAX_AGENT_ITERATIONS)."
    history.append({"role": "assistant", "content": fallback})
    return conv_id, fallback, tool_log
