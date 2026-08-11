"""Loop del agente: manda la conversación a LM Studio, ejecuta las tool calls que
pida el modelo, le devuelve los resultados, y repite hasta que responda en texto
plano o se llegue al tope de iteraciones.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from . import audit_log
from .config import settings
from .llm_client import client
from .phone_link import is_phone_connected
from .selfrepair import gate as selfrepair_gate
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
    "ANTES de tu primer fs_write_file, llamá obsidian_search_notes con el framework/lenguaje/"
    "tecnología de la tarea (ej. 'Flask', 'Fabric Minecraft modding', lo que corresponda) — puede "
    "haber guías o errores conocidos ya cargados que te eviten repetir un problema real ya visto "
    "(nombres de configuración inventados, pasos de setup en el orden equivocado, eventos sin "
    "conectar, etc.). Hacé la query lo más ESPECÍFICA posible a lo que estás por implementar en ese "
    "momento (ej. 'AttackEntityCallback Fabric evento golpear enemigo' cuando vas a programar la "
    "lógica de un golpe, no 'Fabric mod development' a secas) — una query genérica te trae notas "
    "generales y puede hacer que tu propia nota nueva de research_topic (con un título parecido) "
    "tape en el ranking una nota más específica y útil que ya estaba guardada; una query puntual "
    "sobre la clase/API/mecánica exacta evita eso. Esto no es opcional: fs_write_file va a RECHAZAR "
    "la escritura con un error si todavía no consultaste Obsidian ni una vez en este turno — no lo "
    "tomes como un bug, es a propósito, y la solución es simplemente llamar obsidian_search_notes y "
    "reintentar. También va a RECHAZAR la escritura de un archivo NUEVO si dejaste un fs_write_file "
    "anterior bloqueado sin reintentarlo con éxito todavía — no te distraigas escribiendo otra cosa, "
    "volvé a intentar ESE archivo (con el contenido corregido si hacía falta) antes de seguir. El "
    "mismo guardrail de conocimiento se vuelve a activar más adelante en la tarea si un "
    "pc_run_command de compilar/correr "
    "el proyecto te devuelve exit_code distinto de 0: antes de reintentar fs_write_file para arreglar "
    "ESE error puntual, tenés que consultar obsidian_search_notes (o research_topic si Obsidian no "
    "tiene nada relevante sobre ese error específico) — no inventes una solución alternativa a "
    "ciegas sin informarte primero sobre la causa real. "
    "Si diagnosticaste un error real y sabés qué comando lo arregla (ej. generar un archivo que "
    "falta, instalar una dependencia, correr un wrapper), EJECUTALO vos mismo en el mismo turno con "
    "la tool que corresponda — no te quedes en anunciar 'voy a intentar X' como texto y cortar ahí: "
    "eso deja la tarea a medio terminar con el usuario esperando que vos actúes, no describiendo. "
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
    "Cuando el usuario te pida auditar Y REPARAR un hallazgo de seguridad puntual (no solo reportarlo -- "
    "ej. 'buscá y arreglá la inyección SQL en tal archivo'), tenés autorización para completar el ciclo "
    "entero SIN pedir confirmación en el medio: security_scan_project (si hace falta) para encontrarlo, "
    "security_get_finding con file+rule_id+line (NO un finding_id de memoria -- es un hash interno, fácil "
    "de citar mal) para ver el código real y las notas de Obsidian relacionadas que trae automáticamente, "
    "y security_audit_find_fix_verify -- NO code_apply_fix -- para aplicar el fix, commitearlo, y "
    "confirmar que el hallazgo puntual quedó resuelto, todo en un solo paso. No le devuelvas el diff al "
    "usuario pidiendo que lo confirme él mismo -- eso es exactamente lo que security_audit_find_fix_verify "
    "evita. Contale el resultado REAL al final (leé 'finding_resolved' de la respuesta, no asumas que el "
    "fix funcionó solo porque el commit se hizo). code_apply_fix (con su dry-run) sigue siendo la opción "
    "correcta para ediciones de código que el usuario quiere revisar antes de aplicar, o cuando no pidió "
    "explícitamente que repares algo vos solo.\n\n"
    "Si el usuario nombró un hallazgo ESPECÍFICO a reparar (por su regla, CWE, o descripción concreta -- "
    "ej. 'el B608', 'la inyección SQL de tal archivo'), NO lo sustituyas por otro hallazgo más fácil de "
    "encontrar sin decirlo -- pasale ese rule_id (y file si lo dijo) como 'requested_rule_id'/'requested_file' "
    "a CADA llamada de security_audit_find_fix_verify de este pedido: si intentás aplicar el fix sobre un "
    "hallazgo distinto sin marcarlo, la tool te lo va a rechazar a propósito (bug real 2026-08-09: pasó tres "
    "veces seguidas, terminó arreglando un hallazgo random en vez del pedido). Si de verdad no podés ubicar el "
    "hallazgo pedido (no existe, es ambiguo y no lográs desambiguarlo), decíselo al usuario en tu respuesta "
    "ANTES de aplicar un fix sobre otra cosa -- nunca calladamente. Si al pedir un hallazgo por file+rule_id+"
    "line el line no matchea, el error te devuelve las líneas reales disponibles para esa regla en ese "
    "archivo -- usá esas, no seas adivinando líneas al azar en el siguiente intento.\n\n"
    "'Auditado' y 'verificado' no son lo mismo: que security_scan_project/quality_scan_project no encuentren "
    "un patrón ya no significa que el proyecto siga funcionando. security_audit_find_fix_verify corre la "
    "suite de tests real del proyecto automáticamente después de cada fix (leé 'tests' en su respuesta -- "
    "'detected' dice si había una suite real para correr, 'passed' si quedó en verde); si vos aplicaste el "
    "fix con code_apply_fix en cambio, llamá code_run_tests después de confirm=true y antes de dar la tarea "
    "por terminada. Si audit_generate_report muestra que la última corrida de tests falló (o que nunca se "
    "corrió), decíselo al usuario explícitamente en tu respuesta -- no digas 'quedó todo resuelto' basándote "
    "solo en que ya no aparecen hallazgos.\n\n"
    "Si el usuario pide arreglar un bug de tu propio código (backend/, el que está corriendo ahora), usá "
    "selfrepair_propose_fix -- SOLO propone (dry-run, genera un diff real y un proposal_id), nunca aplica nada. "
    "fs_write_file sobre tu propio código está bloqueado siempre, sin excepción. Para aplicar la propuesta de "
    "verdad hace falta que Damian escriba el proposal_id exacto (formato 'sf-xxxxxxxx') en un mensaje suyo -- "
    "no alcanza con que vos digas que ya confirmó, ni con pedirle un 'dale' genérico: mostrale el diff y "
    "pedile específicamente que confirme ESE id. Recién con eso en su mensaje podés llamar a code_apply_fix con "
    "confirm=true, el mismo file y el mismo old_snippet/new_snippet de la propuesta. Después de aplicar, el "
    "backend sigue corriendo con el código viejo hasta que alguien lo reinicia a mano -- decíselo al usuario, "
    "no asumas que el fix ya está en efecto.\n\n"
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
    [0]) supera `max_messages`. Corte simple por cantidad de mensajes, no por
    tokens reales -- ver `_trim_history_by_budget` para la poda que sí mira
    tamaño real.

    Bug real 2026-08-10 (test de creación de un mod de Minecraft/Fabric, 19
    tool calls seguidas en un solo turno): esta función tenía la MISMA falla
    que `_trim_history_by_budget` tuvo y se corrigió el 2026-08-09 (ver el
    docstring de esa función) -- pero acá nunca se aplicó el mismo fix. La
    versión vieja buscaba "el próximo mensaje 'user'" arrancando siempre
    después de `excess`, sin importar si ese punto ya estaba DENTRO del
    turno en curso. En un turno de un solo mensaje 'user' seguido de muchas
    tool calls (sin ninguna segunda pregunta del usuario después), esa
    búsqueda nunca encuentra un 'user' más adelante y termina podando TODO
    el cuerpo -- incluido el pedido original -- en cuanto la cantidad de
    mensajes supera `max_messages`. El modelo se queda sin contexto de qué
    tenía que hacer y responde con el saludo genérico ("¡Hola! Soy
    Jarvis...") en vez de seguir la tarea -- reproducido en vivo: se trabó
    justo así al crear el mod, sin escribir un solo archivo de código.

    Mismo criterio que `_trim_history_by_budget`: el turno en curso -- desde
    el último mensaje 'user' en adelante -- nunca se poda entero, sin
    importar cuántos mensajes tenga. Solo se poda lo que quedó ANTES de ese
    turno (turnos viejos ya resueltos, si los hay)."""
    body = history[1:]
    if len(body) <= max_messages:
        return

    last_user_idx = max((i for i, m in enumerate(body) if m.get("role") == "user"), default=0)
    current_turn = body[last_user_idx:]

    if len(current_turn) >= max_messages:
        # Ni siquiera el turno activo solo entra -- no hay nada más que podar
        # sin romperlo (mismo criterio que `_trim_history_by_budget`): mejor
        # pasarse del límite que mandar un historial vacío o corrupto.
        history[1:] = current_turn
        return

    older = body[:last_user_idx]
    cut = 0
    while cut < len(older) and (len(older) - cut) + len(current_turn) > max_messages:
        cut += 1
        while cut < len(older) and older[cut].get("role") != "user":
            cut += 1
    history[1:] = older[cut:] + current_turn


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
    contexto del bug que motivó esta protección.

    El TURNO EN CURSO -- desde el mensaje 'user' más reciente en adelante --
    nunca se poda entero, sin importar qué tan grande sea. Bug real
    2026-08-09 (round 2): un turno de auditar+reparar+verificar con muchas
    tool calls seguidas tiene UN SOLO mensaje 'user' en todo `body` (el
    pedido original, nada más -- no hay una segunda pregunta del usuario
    después). La versión anterior de esta función buscaba "el próximo
    'user' después de un punto de corte" arrancando SIEMPRE después del
    índice 0 -- en este caso degenerado no hay ningún otro 'user' más
    adelante, así que la búsqueda nunca encontraba nada y terminaba podando
    TODO el historial, incluido el pedido original. El modelo se quedó sin
    ningún contexto de qué tenía que hacer y respondió con un saludo
    genérico ("¡Hola! Soy Jarvis...") en vez de terminar de aplicar el fix
    que ya tenía casi resuelto (encontrado corriendo el caso real: B608 en
    pygoat, 12 tool calls, cortado justo antes de confirmar el commit).

    Solo se poda lo que quedó ANTES del turno en curso (turnos viejos ya
    resueltos, si los hay) -- mismo criterio de "cortar en el próximo
    'user'" que antes, pero acotado a esa ventana."""
    body = history[1:]
    if not body:
        return

    def _fits(msgs: list[dict]) -> bool:
        return len(json.dumps(msgs, default=str, ensure_ascii=False)) <= budget_chars

    if _fits(body):
        return

    last_user_idx = max((i for i, m in enumerate(body) if m.get("role") == "user"), default=0)
    current_turn = body[last_user_idx:]

    if not _fits(current_turn):
        # Ni siquiera el turno activo solo entra -- no hay nada más que podar
        # sin romperlo (partir un tool_call de su respuesta, o peor, perder el
        # pedido original). Se manda igual, mejor pasarse del presupuesto
        # estimado que mandar un historial vacío o corrupto -- en la práctica
        # MAX_TOOL_RESULT_CHARS y MAX_HISTORY_MESSAGES ya deberían evitar
        # llegar hasta acá.
        history[1:] = current_turn
        return

    older = body[:last_user_idx]
    cut = 0
    while cut < len(older) and not _fits(older[cut:] + current_turn):
        cut += 1
        while cut < len(older) and older[cut].get("role") != "user":
            cut += 1
    history[1:] = older[cut:] + current_turn


def _pending_blocked_write_paths(history: list[dict]) -> set[str]:
    """Devuelve el CONJUNTO de `path` de `fs_write_file` que fueron bloqueados
    (por `_obsidian_gate_error`, o por cualquier otro motivo -- cualquier
    resultado con clave "error") y todavía no se reintentaron con éxito,
    vacío si no hay ninguno pendiente.

    Bug real 2026-08-10 (test v5 del mod de Fabric): el guardrail bloqueó el
    primer intento de escribir build.gradle, el modelo consultó Obsidian y
    research_topic como se le pidió -- pero DESPUÉS de eso nunca volvió a
    intentar escribir build.gradle: se puso a escribir otros archivos
    (clases Java, fabric.mod.json, assets) y el archivo bloqueado quedó
    abandonado para siempre. El proyecto terminó sin build.gradle. Esto
    evita que un archivo bloqueado quede abandonado: mientras haya alguno
    pendiente, cualquier `fs_write_file` a OTRO path se rechaza también, con
    un recordatorio explícito de cuáles son los que faltan terminar.

    Bug real 2026-08-10 (v6, encontrado por meta-observación/Opción B): la
    versión anterior trackeaba un ÚNICO path (`str | None`) -- si un SEGUNDO
    archivo se bloqueaba mientras el primero seguía pendiente, ese segundo
    bloqueo se perdía en cuanto el primero se resolvía (`SpadeMod.java`
    bloqueado mientras `fabric.mod.json` seguía pendiente; al resolverse
    `fabric.mod.json`, el tracking quedaba en None y `SpadeMod.java` nunca
    se volvió a reintentar). Ahora es un `set[str]`: cada bloqueo se agrega,
    cada reintento exitoso se descarta, sin pisar el tracking de los demás.

    Nota interna (corregido 2026-08-11, tras encontrar empíricamente que la
    primera versión de este fix seguía teniendo el bug real): ANTES, el
    rechazo que este mismo guardrail genera para un archivo DISTINTO
    mientras hay uno pendiente (marcado `blocked_reason: "pending_retry"`)
    se excluía a propósito de contar como "nuevo pendiente" -- tenía sentido
    cuando `pending` era un único valor (agregarlo pisaría el tracking del
    original). Con un `set[str]` esa exclusión ya NO hace falta y de hecho
    reproduce el bug de v6 de nuevo: el archivo distinto rechazado nunca
    queda registrado, así que se pierde apenas se resuelve el original --
    exactamente el mismo síntoma que esto debía arreglar. Confirmado con un
    test real reproduciendo la secuencia exacta de v6 antes y después de
    este cambio."""
    call_id_to_path: dict[str, str] = {}
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if tc.get("function", {}).get("name") != "fs_write_file":
                continue
            call_id = tc.get("id")
            if not call_id:
                continue
            try:
                call_args = json.loads(tc.get("function", {}).get("arguments") or "{}")
            except json.JSONDecodeError:
                continue
            path = call_args.get("path")
            if path:
                call_id_to_path[call_id] = path

    pending: set[str] = set()
    for msg in history:
        if msg.get("role") != "tool":
            continue
        path = call_id_to_path.get(msg.get("tool_call_id"))
        if not path:
            continue
        try:
            result = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and "error" in result:
            pending.add(path)
        elif path in pending:
            pending.discard(path)
    return pending


def _audit_safe_args(tool_name: str, args: dict) -> dict:
    """Versión de `args` segura para persistir en `audit_log` (ver hook en el
    loop de tool calls, más abajo): para `fs_write_file` reemplaza el `content`
    real -- puede ser código entero, potencialmente grande -- por un hash
    sha256 y su longitud, nunca el contenido crudo.

    El hash (no el contenido) es justamente lo que necesita
    `app/introspection/analyzer.py` para detectar el bug real de v6 (reescribir
    contenido IDÉNTICO al mismo path varias veces seguidas): comparar hashes es
    suficiente para eso, y guardar el contenido completo de cada escritura
    inflaría `audit.log` sin necesidad."""
    if tool_name == "fs_write_file" and "content" in args:
        content = args.get("content") or ""
        safe = {k: v for k, v in args.items() if k != "content"}
        safe["content_sha256"] = hashlib.sha256(str(content).encode("utf-8", errors="replace")).hexdigest()
        safe["content_length"] = len(str(content))
        return safe
    return args


def _audit_safe_result(result: Any) -> Any:
    """Igual que `_audit_safe_args` pero para el resultado de la tool call --
    omite blobs base64 (imagen/video) que no aportan nada al análisis de
    patrones y solo inflarían el log."""
    if not isinstance(result, dict):
        return result
    safe = dict(result)
    for blob_key in ("image_base64", "video_base64"):
        if blob_key in safe:
            safe[blob_key] = f"<omitido, {len(str(safe[blob_key]))} chars>"
    return safe


# Mismo umbral que app/introspection/analyzer.py::_DEFAULT_MIN_REPEATS -- 3
# reescrituras idénticas seguidas cuentan como loop. Repetido acá (no
# importado) a propósito: introspection/analyzer.py opera sobre entradas ya
# cerradas de una sesión terminada, este guardrail corre EN VIVO adentro del
# loop del agente -- son dos consumidores del mismo criterio, no el mismo
# código ejecutándose en dos momentos distintos.
_LIVE_LOOP_MIN_REPEATS = 3


def _live_identical_rewrite_loop_error(conv_id: str, path: str | None, content: str) -> str | None:
    """Guardrail duro EN VIVO (2026-08-11, prerequisito #7 para Opción A --
    ver informe de arquitectura 2026-08-10). Bug real de v6: el modelo
    reescribió el mismo archivo con contenido idéntico 14 veces seguidas sin
    ningún freno -- Opción B (meta-observación) detecta este patrón, pero
    solo DESPUÉS de que la sesión termina, cuando ya no sirve para nada.
    Esto corre el MISMO criterio (ver `_LIVE_LOOP_MIN_REPEATS`) antes de
    permitir la escritura, leyendo del audit_log real (target="agent", ya
    persistido por el hook de Opción B) en vez de reimplementar el tracking
    desde cero -- misma fuente de verdad que usa el análisis post-hoc."""
    if not path:
        return None
    content_hash = hashlib.sha256(str(content).encode("utf-8", errors="replace")).hexdigest()
    entries = audit_log.read_entries(target="agent", tool="fs_write_file", conversation_id=conv_id)
    recent = entries[-(_LIVE_LOOP_MIN_REPEATS - 1):]
    if len(recent) < _LIVE_LOOP_MIN_REPEATS - 1:
        return None
    for e in recent:
        if not e.get("ok"):
            return None
        prior_args = e.get("arguments") or {}
        if prior_args.get("path") != path or prior_args.get("content_sha256") != content_hash:
            return None
    return (
        f"Ya escribiste '{path}' con este MISMO contenido exacto {_LIVE_LOOP_MIN_REPEATS - 1} vez/veces "
        f"seguidas -- esto es un loop de reescritura idéntica (bug real de v6, ver "
        f"app/introspection/analyzer.py). Si ya terminaste con este archivo, seguí con el resto de la "
        f"tarea; si necesitás cambiar algo, escribí contenido REALMENTE distinto."
    )


def _last_index_of_tool_call(history: list[dict], tool_name: str) -> int | None:
    """Índice (en `history`) del ÚLTIMO mensaje 'assistant' que llamó `tool_name`,
    o None si nunca se llamó. Usado por `_obsidian_gate_error` para comparar
    "¿esto pasó antes o después de la última consulta de conocimiento?"."""
    last: int | None = None
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if tc.get("function", {}).get("name") == tool_name:
                last = i
    return last


def _last_failed_command_result(history: list[dict]) -> tuple[int, dict] | None:
    """Busca el ÚLTIMO mensaje 'tool' que sea la respuesta de un `pc_run_command`
    con `exit_code` distinto de 0 (una compilación/build/test real que falló).
    Devuelve `(índice en history, dict del resultado parseado)`, o None si no
    hay ninguno. El mensaje 'tool' en sí no lleva el nombre de la tool que lo
    generó -- hay que mapear `tool_call_id` -> nombre buscando en los mensajes
    'assistant' anteriores."""
    call_id_to_name: dict[str, str] = {}
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            call_id = tc.get("id")
            name = tc.get("function", {}).get("name")
            if call_id and name:
                call_id_to_name[call_id] = name

    last: tuple[int, dict] | None = None
    for i, msg in enumerate(history):
        if msg.get("role") != "tool":
            continue
        if call_id_to_name.get(msg.get("tool_call_id")) != "pc_run_command":
            continue
        try:
            result = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and result.get("exit_code") not in (None, 0):
            last = (i, result)
    return last


def _obsidian_gate_error(history: list[dict]) -> str | None:
    """Devuelve un mensaje de error si el próximo `fs_write_file` debería
    bloquearse por falta de conocimiento consultado, o None si puede pasar.

    Dos casos reales, ambos encontrados corriendo tareas de creación de código
    de verdad (mods de Fabric para Minecraft, v2/v3/v4):

    1. Nunca se consultó Obsidian en este turno (bug real 2026-08-10, v2/v3):
       pedirlo solo en el prompt no alcanzó, el modelo lo ignoró dos corridas
       seguidas -- acá se bloquea hasta que llame obsidian_search_notes al
       menos una vez.

    2. Ya se consultó Obsidian, pero DESPUÉS de esa consulta hubo un intento
       real de compilar/correr el proyecto (`pc_run_command`) que falló
       (`exit_code != 0`), y todavía no se volvió a consultar conocimiento
       sobre ESE error puntual antes de reintentar escribir código (bug real
       2026-08-10, v4: consultó Obsidian una vez al principio sobre StatusEffect,
       nunca chequeó nada sobre cómo detectar un golpe -- AttackEntityCallback --,
       y terminó inventando una mecánica equivocada en vez de darse cuenta de
       que le faltaba información puntual). Esto es agnóstico de lenguaje o
       framework: aplica igual a un fallo de `npm run build`, `pytest`,
       `cargo build`, etc. -- cualquier `pc_run_command` que falle cuenta.

    En ambos casos, tanto `obsidian_search_notes` como `research_topic` cuentan
    como "consulté conocimiento" -- `research_topic` es la vía de escape
    cuando Obsidian no tiene nada relevante todavía."""
    search_idx = _last_index_of_tool_call(history, "obsidian_search_notes")
    research_idx = _last_index_of_tool_call(history, "research_topic")
    last_knowledge_idx = max((i for i in (search_idx, research_idx) if i is not None), default=None)

    if last_knowledge_idx is None:
        return (
            "Antes de escribir código nuevo tenés que consultar tu conocimiento "
            "en Obsidian primero -- llamá obsidian_search_notes con el tema/"
            "tecnología de esta tarea (ej. el framework o lenguaje que vas a usar). "
            "Puede haber guías o errores conocidos ya documentados que evitan "
            "problemas reales (nombres de configuración inventados, eventos sin "
            "conectar, etc.). Después de consultar Obsidian, reintentá fs_write_file."
        )

    failed = _last_failed_command_result(history)
    if failed is not None:
        fail_idx, result = failed
        if fail_idx > last_knowledge_idx:
            error_detail = str(result.get("stderr") or result.get("stdout") or "")[:400]
            return (
                f"El último intento de compilar/correr el proyecto falló (exit_code="
                f"{result.get('exit_code')}) y todavía no consultaste tu conocimiento "
                f"sobre ESE error puntual antes de seguir escribiendo código. Error real: "
                f"{error_detail!r}. Llamá obsidian_search_notes (o research_topic si "
                f"Obsidian no tiene nada relevante) sobre la causa concreta de este error "
                f"antes de reintentar fs_write_file -- no sigas adivinando otra solución "
                f"a ciegas sin informarte primero."
            )

    return None


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

    # Tope de iteraciones dinámico: arranca en el default (settings.max_agent_iterations,
    # pensado para chat/auditorías normales) y sube una sola vez a
    # settings.max_agent_iterations_code_task en cuanto este turno usa fs_write_file
    # por primera vez -- ahí es cuando se confirma que es una tarea de creación de
    # código, no antes (ver docstring de max_agent_iterations_code_task).
    effective_max_iterations = settings.max_agent_iterations
    iteration = 0
    while iteration < effective_max_iterations:
        iteration += 1
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
                # Bug real 2026-08-10: no había NINGÚN tope de tokens de salida --
                # `_history_char_budget` ya restaba `reserved_response_tokens` del
                # presupuesto de PROMPT asumiendo que la respuesta iba a quedar
                # acotada a eso, pero nunca se lo pasamos a la llamada real: el
                # trim protege lo que ENTRA, nada protegía lo que el modelo podía
                # generar DESPUÉS. En una corrida real (reparación masiva en
                # pygoat) la respuesta final entró en lo que parece haber sido un
                # loop de repetición justo después de que Ollama disparó su propio
                # context-shift (`n_discard=16381` -- el prompt-processing había
                # llenado el contexto casi hasta el límite antes de esta llamada),
                # y sin tope de salida siguió generando sin parar (pasó 2800+
                # tokens, contra ~100-450 de una respuesta normal, y seguía
                # subiendo cuando se cortó a mano) -- potencialmente hasta agotar
                # TODO el contexto restante. Con este tope, `finish_reason` pasa a
                # "length" en el peor caso -- una respuesta truncada pero ACOTADA,
                # nunca una que se coma el resto del turno.
                max_tokens=settings.reserved_response_tokens,
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
                gate_error = None
                blocked_reason = None
                # Guardrail duro (2026-08-11, Opción C del diseño de auto-reparación):
                # cualquier escritura -- fs_write_file o code_apply_fix(confirm=true) --
                # que apunte adentro del propio backend/ de Jarvis se bloquea sin
                # excepción salvo que el mensaje de ESTE turno traiga un proposal_id
                # confirmado (ver app/selfrepair/gate.py para las reglas completas).
                # Va ANTES de los gates de fs_write_file de abajo -- es más específico
                # y más severo, no reemplaza al resto (un self-fix igual necesita haber
                # consultado Obsidian, etc.).
                gate_error = selfrepair_gate.self_target_gate_error(tc.function.name, args, message)
                if gate_error is None and tc.function.name == "fs_write_file":
                    pending_paths = _pending_blocked_write_paths(history)
                    write_path = args.get("path")
                    if pending_paths and write_path not in pending_paths:
                        # Guardrail duro (2026-08-10, extendido después de v5 y v6): ver el
                        # docstring de `_pending_blocked_write_paths` -- no alcanza con
                        # desbloquear el guardrail de conocimiento, hay que asegurarse
                        # de que TODOS los archivos bloqueados se retomen, no se abandonen.
                        gate_error = (
                            f"Todavía tenés pendiente(s) reintentar: {', '.join(sorted(pending_paths))} -- que "
                            f"se habían bloqueado antes y nunca se volvieron a escribir con éxito -- terminá "
                            f"ESOS archivos primero (con el contenido corregido si hacía falta) antes de "
                            f"escribir '{write_path}' u otro archivo nuevo. No los dejes abandonados."
                        )
                        blocked_reason = "pending_retry"
                    else:
                        gate_error = _obsidian_gate_error(history)
                if gate_error:
                    # Guardrail duro (2026-08-10, extendido después de v4): ver el
                    # docstring de `_obsidian_gate_error` para los dos casos reales
                    # que motivaron esto -- pedirlo solo en el prompt no alcanzó.
                    result = {"error": gate_error}
                    if blocked_reason:
                        # Ver docstring de `_pending_blocked_write_paths`: este marcador
                        # evita que el propio rechazo se registre como un nuevo archivo
                        # pendiente (pisaría el tracking del que hace falta reintentar).
                        result["blocked_reason"] = blocked_reason
                    logger.info("fs_write_file bloqueado: %s", gate_error[:80])
                else:
                    if (
                        tc.function.name == "fs_write_file"
                        and effective_max_iterations < settings.max_agent_iterations_code_task
                    ):
                        effective_max_iterations = settings.max_agent_iterations_code_task
                    try:
                        result = await call_tool(tc.function.name, args)
                    except Exception as exc:  # las tools pueden fallar por muchas razones distintas
                        logger.warning("tool_call failed name=%s error=%s", tc.function.name, exc)
                        result = {"error": str(exc)}
                    else:
                        # Si esto era un self-fix (code_apply_fix confirm=true sobre
                        # backend/) que acaba de pasar el gate de arriba, marca la
                        # propuesta usada como aplicada -- así el mismo proposal_id
                        # no se puede reusar para otro cambio después.
                        selfrepair_gate.consume_proposal_if_applied(
                            tc.function.name, args, message, result, datetime.now(timezone.utc).isoformat()
                        )
                tool_log.append({"tool": tc.function.name, "arguments": args, "result": result})

                # Traza estructurada de CADA tool call del agente (bloqueada o
                # no) para `app/introspection/analyzer.py` -- a diferencia del
                # `logger.info` de más arriba (texto libre, no necesariamente
                # persiste salvo que alguien redirija stdout a un archivo a
                # mano, ver docstring de `audit_log.py`), esto siempre queda en
                # `audit.log` como JSON parseable. Es la fuente de datos real
                # para detectar patrones de falla como los de v6 (loop de
                # reescritura idéntica, archivo bloqueado nunca reintentado).
                _tool_error = result.get("error") if isinstance(result, dict) and "error" in result else None
                audit_log.log_tool_call(
                    target="agent",
                    tool=tc.function.name,
                    arguments=_audit_safe_args(tc.function.name, args),
                    result=None if _tool_error else _audit_safe_result(result),
                    error=_tool_error,
                    conversation_id=conv_id,
                )

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
