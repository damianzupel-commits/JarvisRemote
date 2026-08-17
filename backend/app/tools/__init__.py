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
import logging
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
_BLOCKING_TOOL_NAMES = frozenset({
    "nmap_scan", "sqlmap_scan", "packet_capture_scan", "packet_capture_analyze", "zap_scan",
    # Centinela de malware (ver app/malware/, spec 2026-08-16) -- escaneo de
    # carpetas/disco completo (I/O real sobre potencialmente miles de
    # archivos) y el recorrido recursivo de FIM sobre app/ entero, mismo
    # motivo que nmap_scan/sqlmap_scan de arriba: sin esto, cualquiera de
    # estas tools bloquearía el event loop del server entero mientras corre.
    "malware_scan_path", "malware_full_scan_run", "malware_check_integrity", "malware_rebuild_integrity_baseline",
})

# Grabación automática de pantalla (ver app/recording.py) alrededor del
# pipeline real de auditoría->fix->test -- pedido explícito de Damian
# 2026-08-13, motivación completa en el docstring de app/recording.py.
# Clasificado por NOMBRE de tool (no por módulo como _BLOCKING_MODULES de
# arriba) porque el pipeline real cruza varios archivos de app/tools/
# (security_scan.py, quality_scan.py, test_run.py, selfrepair.py,
# audit_report.py, code_edit.py) que también tienen tools de solo
# lectura/navegación que NO valen la pena grabar (security_get_finding/
# quality_get_finding son lookups puntuales de un snippet, codebase_* es
# indexado/búsqueda) -- clasificar por módulo entero agarraría esas también,
# fragmentando "todo el flujo de punta a punta" en ruido de lookups en vez
# de las acciones reales del pipeline. Verificado 2026-08-13 contra el
# registro real (grep de `register_tool(` en esos archivos), no una lista
# adivinada:
# - security_scan_project / security_triage_findings / security_audit_find_fix_verify
#   (app/tools/security_scan.py): escanear, triage, y el ciclo atómico
#   apply+commit+verify.
# - quality_scan_project (app/tools/quality_scan.py).
# - code_apply_fix (app/tools/code_edit.py): el paso de FIX cuando no se usa
#   el ciclo atómico de arriba -- vive en un archivo distinto a los otros
#   pero es la misma etapa del pipeline (aplicar una corrección real).
# - code_run_tests (app/tools/test_run.py): el paso de TEST.
# - selfrepair_propose_fix (app/tools/selfrepair.py): auto-reparación del
#   propio backend de Jarvis.
# - audit_generate_report (app/tools/audit_report.py): cierre del ciclo.
_RECORDABLE_TOOL_NAMES = frozenset({
    "security_scan_project",
    "security_triage_findings",
    "security_audit_find_fix_verify",
    "quality_scan_project",
    "code_apply_fix",
    "code_run_tests",
    "selfrepair_propose_fix",
    "audit_generate_report",
})


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

    if name in _RECORDABLE_TOOL_NAMES:
        # UNA sola grabación continua por turno, no un clip por tool call --
        # ver docstring de _RECORDABLE_TOOL_NAMES. Si ya está grabando (ej.
        # esta es la 2da+ tool recordable de este turno, o Damian arrancó
        # una a mano con recording_start antes) no se toca nada; el guard
        # está acá adentro (no antes, en el caller) para que aplique sea
        # cual sea el punto de entrada real a call_tool.
        from ..config import settings
        from .. import recording

        if settings.screen_recording_enabled and not recording.is_recording():
            try:
                recording.start_recording(session_name=name)
            except recording.RecordingAlreadyActiveError:
                # Carrera rarísima (ver is_recording() recién arriba) -- no
                # es motivo para abortar la tool call real, solo lo dejamos
                # en el log general en vez de romper el pipeline entero.
                logging.getLogger("jarvis.recording").warning(
                    "recording ya activa justo al arrancar %s, se sigue sin grabación nueva", name
                )
            except Exception as exc:
                # ffmpeg no encontrado, permisos, etc. -- la grabación es un
                # extra sobre el pipeline real, nunca debe bloquear la
                # auditoría/fix/test en sí.
                logging.getLogger("jarvis.recording").warning(
                    "no se pudo arrancar la grabación automática para %s: %s", name, exc
                )

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
from . import web_forms  # noqa: E402,F401
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
from . import opencode  # noqa: E402,F401
from . import cloud_expert  # noqa: E402,F401
from . import investigation  # noqa: E402,F401
from . import recording  # noqa: E402,F401
from . import pentest_sqlmap  # noqa: E402,F401
from . import pentest_wireshark  # noqa: E402,F401
from . import pentest_zap  # noqa: E402,F401
from . import malware  # noqa: E402,F401

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
