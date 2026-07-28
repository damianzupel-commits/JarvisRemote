"""Registro de tools que el LLM puede invocar.

Cada módulo de tools (filesystem.py, browser.py, phone.py, ...) se registra a si
mismo con el decorator `register_tool` al ser importado. El agente pide
`openai_tool_schemas()` para mandarle a LM Studio el listado en formato "function
calling" de OpenAI (una única lista, sin distinción de origen), y usa
`call_tool(name, args)` para ejecutar la que el modelo haya elegido.

Cada tool tiene un campo `target`: "pc" (se ejecuta localmente, acá en el backend)
o "phone" (se despacha al celular conectado por WebSocket, ver `phone_link.py`).
`call_tool` actúa de router según ese campo — el LLM no necesita saber la
diferencia, solo ve una lista plana de tools.
"""

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal

Target = Literal["pc", "phone"]


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    target: Target = "pc"


_registry: Dict[str, Tool] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any], target: Target = "pc"):
    """Decorator para registrar una función (sync o async) como tool del agente.

    `parameters` es un JSON Schema de objeto (formato "parameters" de OpenAI tools).
    `target="phone"` marca la tool para que `call_tool` la despache al celular en
    vez de ejecutar el handler local; el handler de esas tools no se llega a
    invocar (ver `call_tool`), pero igual se declara por consistencia con el
    resto del registro.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _registry:
            raise ValueError(f"Tool '{name}' ya está registrada")
        _registry[name] = Tool(
            name=name, description=description, parameters=parameters, handler=fn, target=target
        )
        return fn

    return decorator


def get_tools() -> Dict[str, Tool]:
    return dict(_registry)


def openai_tool_schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in _registry.values()
    ]


async def call_tool(name: str, arguments: Dict[str, Any]) -> Any:
    if name not in _registry:
        raise ValueError(f"Tool desconocida: {name}")
    tool = _registry[name]

    if tool.target == "phone":
        from ..phone_link import dispatch_to_phone

        # Si la tool trae su propio argumento "timeout" (ej. phone_run_command,
        # que le dice a Termux cuánto esperar un comando), extenderlo también al
        # timeout con el que el backend espera la respuesta por WebSocket —
        # si no, el backend podría rendirse (settings.phone_tool_timeout, 30s
        # default) antes de que el celular termine de esperar su propio timeout
        # más largo, dejando el comando huérfano del lado del celular.
        dispatch_timeout = None
        if "timeout" in arguments:
            try:
                dispatch_timeout = float(arguments["timeout"]) + 5
            except (TypeError, ValueError):
                dispatch_timeout = None

        return await dispatch_to_phone(name, arguments, timeout=dispatch_timeout)

    result = tool.handler(**arguments)
    if inspect.isawaitable(result):
        result = await result
    return result


# Importar los módulos de tools para que se registren solos.
from . import filesystem  # noqa: E402,F401
from . import browser  # noqa: E402,F401
from . import desktop  # noqa: E402,F401
from . import phone  # noqa: E402,F401
from . import reflect  # noqa: E402,F401
from . import codebase  # noqa: E402,F401
from . import obsidian  # noqa: E402,F401

# generate_video/generate_image (video_gen.py/image_gen.py) DESACTIVADAS a
# propósito, no importadas -- no es un problema de estilo, es una precaución
# de hardware real: el 2026-07-27 la PC se apagó por completo (no un crash de
# proceso, un apagado físico) al menos dos veces, ambas coincidiendo al
# segundo con el arranque de una de estas dos tools (confirmado cruzando
# backend.log contra el Event Log de Windows, Event ID 41/6008 -- "se reinició
# el sistema sin apagarlo limpiamente"), más un patrón de apagados similares
# en días previos. No hay sandboxing de software posible contra esto -- si es
# térmico o de fuente de poder, hace falta resolverlo a nivel de hardware
# antes de volver a exponer estas tools al agente. Ver INFORME_COMPLETO.md.
# from . import video_gen  # noqa: E402,F401
# from . import image_gen  # noqa: E402,F401
