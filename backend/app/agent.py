"""Loop del agente: manda la conversación a LM Studio, ejecuta las tool calls que
pida el modelo, le devuelve los resultados, y repite hasta que responda en texto
plano o se llegue al tope de iteraciones.
"""

import json
import logging

from .config import settings
from .llm_client import client
from .phone_link import is_phone_connected
from .tools import call_tool, openai_tool_schemas

logger = logging.getLogger("jarvis.agent")

SYSTEM_PROMPT = (
    "Sos Jarvis, un asistente que corre localmente en la PC del usuario y que puede "
    "ejecutar acciones reales a través de herramientas: sistema de archivos y control "
    "del navegador en la PC, control general del escritorio de la PC (lanzar programas, "
    "mouse, teclado, ventanas de cualquier programa abierto: screenshot, listar/enfocar "
    "ventanas, click por coordenadas o por control, escribir texto, combinaciones de teclas, "
    "mover mouse, scroll), y —si hay un celular conectado— abrir apps, leer/escribir archivos "
    "y controlar la pantalla (tocar, deslizar, escribir, leer contenido) del celular. Para "
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
    "confirmar que encontró la app correcta antes de asumir éxito solo porque no tiró error. Usá las "
    "herramientas cuando haga falta para cumplir el pedido en vez de "
    "inventar la respuesta. Si una tool de celular falla porque no hay ningún celular "
    "conectado, decíselo al usuario en vez de asumir que la acción se hizo. Si una tool "
    "falla, contale al usuario qué pasó en vez de asumir que funcionó. Respondé siempre "
    "en el mismo idioma en el que te escribe el usuario.\n\n"
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


async def run_agent(message: str, conversation_id: str | None) -> tuple[str, str, list[dict]]:
    conv_id = conversation_id or "default"
    history = _conversations.setdefault(conv_id, [{"role": "system", "content": SYSTEM_PROMPT}])
    history.append({"role": "user", "content": message})

    tool_log: list[dict] = []
    tools = openai_tool_schemas()

    for _ in range(settings.max_agent_iterations):
        # La nota de estado se arma de nuevo en cada vuelta del loop (por si el celular
        # se conecta/desconecta durante una tarea larga) y no se guarda en `history`:
        # así siempre es el estado real al momento de la llamada, no una foto vieja que
        # se vuelve stale (o contradice lo que el modelo dijo antes) a medida que la
        # conversación crece.
        response = await client.chat.completions.create(
            model=settings.lmstudio_model,
            messages=history + [_phone_status_note()],
            tools=tools or None,
            tool_choice="auto" if tools else None,
        )
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
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str, ensure_ascii=False),
                    }
                )
            continue

        history.append({"role": "assistant", "content": msg.content})
        return conv_id, msg.content or "", tool_log

    fallback = "No pude terminar la tarea dentro del límite de pasos permitidos (MAX_AGENT_ITERATIONS)."
    history.append({"role": "assistant", "content": fallback})
    return conv_id, fallback, tool_log
