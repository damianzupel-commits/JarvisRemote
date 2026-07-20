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

        return await dispatch_to_phone(name, arguments)

    result = tool.handler(**arguments)
    if inspect.isawaitable(result):
        result = await result
    return result


# Importar los módulos de tools para que se registren solos.
from . import filesystem  # noqa: E402,F401
from . import browser  # noqa: E402,F401
from . import phone  # noqa: E402,F401
