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

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal

Target = Literal["pc", "phone"]

# Bug real (informe de arquitectura 2026-08-10): app/tools/desktop.py corre
# funciones SINCRÓNICAS (pyautogui/pywinauto, con sleeps/polls reales -- ej.
# `_wait_for_new_window` espera hasta 5s en un loop bloqueante) directo en el
# thread del event loop de FastAPI -- durante esos segundos, TODO el server
# queda sin atender: ni /api/health, ni los frames del WebSocket del celular,
# ni ninguna otra tool call. Mismo problema que ya se resolvió para el
# cliente LLM con un cliente async (ver app/llm_client.py), acá con
# asyncio.to_thread en vez de reescribir pyautogui/pywinauto como async.
# Clasificado por MÓDULO (no tool por tool) a propósito: cualquier tool que
# se agregue a app/tools/desktop.py en el futuro queda cubierta
# automáticamente, sin depender de acordarse de marcarla una por una.
_BLOCKING_MODULES = ("app.tools.desktop",)

# Bug real encontrado 2026-08-13 implementando sqlmap_scan, mismo problema
# de fondo que el de desktop.py de arriba: `nmap_scan` (app/tools/
# network_scan.py) es una función SINCRÓNICA que corre `subprocess.run`
# con timeout de hasta 1200s -- bloquea el event loop entero durante todo
# el escaneo, exactamente el mismo bug ya arreglado para desktop.py, pero
# nunca se agregó a _BLOCKING_MODULES cuando se creó. `sqlmap_scan`
# (app/tools/pentest_sqlmap.py) tiene el mismo problema (polling HTTP
# bloqueante contra la REST API de SQLMap).
#
# Por NOMBRE de tool, no por módulo (a diferencia de _BLOCKING_MODULES) --
# `network_scan.py` mezcla `nmap_scan` (síncrona, bloqueante) con
# `phone_nmap_scan` (`async def`, ya no-bloqueante porque awaitea
# `dispatch_to_phone`): meter el MÓDULO entero acá rompería
# `phone_nmap_scan` -- `asyncio.to_thread` sobre una función async
# devuelve la corrutina sin ejecutarla, nunca corre de verdad.
_BLOCKING_TOOL_NAMES = frozenset({"nmap_scan", "sqlmap_scan", "packet_capture_scan", "packet_capture_analyze", "zap_scan"})



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

    if tool.handler.__module__ in _BLOCKING_MODULES or name in _BLOCKING_TOOL_NAMES:
        # Ver _BLOCKING_MODULES/_BLOCKING_TOOL_NAMES arriba -- corre en un
        # thread aparte para no bloquear el event loop del server entero
        # mientras pyautogui/pywinauto/subprocess.run/polling HTTP hacen su
        # cosa (incluye sleeps/polls reales de varios segundos o minutos).
        # to_thread, no run_in_executor a mano: mismo resultado, API más
        # simple (Python 3.9+, este proyecto ya requiere 3.12).
        result = await asyncio.to_thread(tool.handler, **arguments)
    else:
        result = tool.handler(**arguments)
        if inspect.isawaitable(result):
            result = await result
    return result


# Importar los módulos de tools para que se registren solos.
from . import filesystem  # noqa: E402,F401
from . import browser  # noqa: E402,F401
from . import desktop  # noqa: E402,F401
from . import pc_command  # noqa: E402,F401
from . import phone  # noqa: E402,F401
from . import reflect  # noqa: E402,F401
from . import codebase  # noqa: E402,F401
from . import obsidian  # noqa: E402,F401
from . import security_scan  # noqa: E402,F401
from . import quality_scan  # noqa: E402,F401
from . import code_edit  # noqa: E402,F401
from . import test_run  # noqa: E402,F401
from . import selfrepair  # noqa: E402,F401
from . import audit_report  # noqa: E402,F401
from . import network_scan  # noqa: E402,F401
from . import research  # noqa: E402,F401
from . import investigation  # noqa: E402,F401
from . import pentest_sqlmap  # noqa: E402,F401
from . import pentest_wireshark  # noqa: E402,F401
from . import pentest_zap  # noqa: E402,F401

# generate_video/generate_image (video_gen.py/image_gen.py) DESACTIVADAS a
# propósito, no importadas -- no es un problema de estilo, es una precaución
# de hardware real: el 2026-07-27 la PC se apagó por completo (no un crash de
# proceso, un apagado físico) mientras generate_video estaba en pleno cómputo
# de GPU (confirmado cruzando comfyui.log -- última escritura 16:57:01, a
# mitad de un paso de sampling -- contra el Event Log de Windows, reinicio a
# las 16:57:26). Además, esta PC ya tenía un patrón de apagados del mismo
# tipo (Kernel-Power ID 41, BugcheckCode 0 -- sin BSOD/crash de software) casi
# a diario desde fines de junio hasta el 23/07, semanas antes de que estas
# tools existieran -- probablemente un problema de entrega de energía más
# amplio (fuente al límite o instalación eléctrica), no algo causado
# específicamente por esta tool, aunque el pico de consumo de la GPU lo hizo
# más probable ese día. No hay sandboxing de software posible contra esto --
# si es térmico o de fuente de poder, hace falta resolverlo a nivel de
# hardware antes de volver a exponer estas tools al agente. AIDA64 quedó
# configurado con logging a CSV para la próxima prueba. Ver INFORME_COMPLETO.md.
# from . import video_gen  # noqa: E402,F401
# from . import image_gen  # noqa: E402,F401
