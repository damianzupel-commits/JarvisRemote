"""Registro de tools que el LLM puede invocar.

Cada módulo de tools (filesystem.py, browser.py, ...) se registra a si mismo con
el decorator `register_tool` al ser importado. El agente pide `openai_tool_schemas()`
para mandarle a LM Studio el listado en formato "function calling" de OpenAI, y usa
`call_tool(name, args)` para ejecutar la que el modelo haya elegido.
"""

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]


_registry: Dict[str, Tool] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator para registrar una función (sync o async) como tool del agente.

    `parameters` es un JSON Schema de objeto (formato "parameters" de OpenAI tools).
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _registry:
            raise ValueError(f"Tool '{name}' ya está registrada")
        _registry[name] = Tool(name=name, description=description, parameters=parameters, handler=fn)
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
    result = _registry[name].handler(**arguments)
    if inspect.isawaitable(result):
        result = await result
    return result


# Importar los módulos de tools para que se registren solos.
from . import filesystem  # noqa: E402,F401
from . import browser  # noqa: E402,F401
