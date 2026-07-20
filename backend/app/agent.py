"""Loop del agente: manda la conversación a LM Studio, ejecuta las tool calls que
pida el modelo, le devuelve los resultados, y repite hasta que responda en texto
plano o se llegue al tope de iteraciones.
"""

import json
import logging

from .config import settings
from .llm_client import client
from .tools import call_tool, openai_tool_schemas

logger = logging.getLogger("jarvis.agent")

SYSTEM_PROMPT = (
    "Sos Jarvis, un asistente que corre localmente en la PC del usuario y que puede "
    "ejecutar acciones reales a través de herramientas: sistema de archivos y control "
    "del navegador en la PC, y —si hay un celular conectado— abrir apps, leer/escribir "
    "archivos y controlar la pantalla (tocar, deslizar, escribir, leer contenido) del "
    "celular. Usá las herramientas cuando haga falta para cumplir el pedido en vez de "
    "inventar la respuesta. Si una tool de celular falla porque no hay ningún celular "
    "conectado, decíselo al usuario en vez de asumir que la acción se hizo. Si una tool "
    "falla, contale al usuario qué pasó en vez de asumir que funcionó. Respondé siempre "
    "en el mismo idioma en el que te escribe el usuario."
)

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
        response = client.chat.completions.create(
            model=settings.lmstudio_model,
            messages=history,
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
