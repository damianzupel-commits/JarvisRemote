"""Gestiona la conexión WebSocket entrante del celular y el despacho de tool calls.

El celular abre una única conexión WebSocket saliente hacia `/ws/phone` (mantenida
por un foreground service en la app), autenticada con el mismo Bearer token que
`/api/chat`. Este módulo guarda esa conexión activa y expone `dispatch_to_phone`,
que las tools con `target="phone"` usan para mandarle un tool call al celular y
esperar la respuesta, correlacionando por un id de request.

Solo se soporta un celular conectado a la vez (mismo modelo 1:1 que el resto del
proyecto); una conexión nueva reemplaza a la anterior.
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Protocol

from . import audit_log
from .config import settings

logger = logging.getLogger("jarvis.phone_link")


class PhoneNotConnectedError(RuntimeError):
    pass


class PhoneToolError(RuntimeError):
    """La tool falló del lado del celular; el mensaje ya viene listo para mostrar."""


class DestructiveCommandBlockedError(PermissionError):
    """El comando matcheó el blocklist de patrones obviamente destructivos."""


class SendsText(Protocol):
    async def send_text(self, data: str) -> None: ...


_phone_ws: SendsText | None = None
_pending: dict[str, asyncio.Future] = {}

# Tools que ejecutan shell real en el celular (vía Termux) en vez de solo
# interactuar con la UI — nivel de riesgo distinto, se gatean con su propio
# flag (PHONE_SHELL_ENABLED) y se loguean como rastro de auditoría.
_SHELL_TOOL_NAMES = {"phone_run_command"}

# Tools que usan la cámara del celular — se gatean con su propio flag
# (PHONE_CAMERA_ENABLED), mismo criterio que las tools de shell/escritorio.
# phone_record_video usa la misma cámara física que phone_take_photo, así que
# comparte el mismo flag (no hay un PHONE_VIDEO_ENABLED separado).
_CAMERA_TOOL_NAMES = {"phone_take_photo", "phone_record_video"}

# Blocklist de patrones obviamente destructivos para phone_run_command. Esto es
# una mitigación de "evitar el desastre obvio" por matching de texto — NO es un
# sandbox real ni una garantía de seguridad completa. Cualquier comando que no
# matchee ninguno de estos patrones se manda igual a Termux sin restricciones
# (ver docstring de la tool en tools/phone.py). Comparado sobre el comando en
# minúsculas con espacios repetidos colapsados, para no depender de formateo
# exacto.
_DESTRUCTIVE_COMMAND_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "rm -rf sobre la raíz o el home",
        re.compile(r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+(/|~|\$home)(\s|/\*|$)"),
    ),
    ("mkfs (formatear un filesystem)", re.compile(r"\bmkfs(\.\w+)?\b")),
    ("dd escribiendo directo a un block device", re.compile(r"\bdd\b[^\n]*\bof=/dev/")),
    ("fork bomb", re.compile(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:.*&.*\}\s*;\s*:")),
    ("chmod/chown recursivo sobre la raíz", re.compile(r"\b(chmod|chown)\s+-r\s+\S+\s+/(\s|$)")),
    ("escritura directa a un block device", re.compile(r">\s*/dev/(sd|mmcblk|block)\w*")),
]


def _check_command_blocklist(command: str) -> None:
    normalized = " ".join(command.lower().split())
    for name, pattern in _DESTRUCTIVE_COMMAND_PATTERNS:
        if pattern.search(normalized):
            logger.warning("phone_shell: comando BLOQUEADO (%s): %r", name, command)
            raise DestructiveCommandBlockedError(
                f"Comando rechazado por el blocklist de seguridad (patrón: {name}). "
                "Es una mitigación de 'evitar el desastre obvio' por matching de texto, "
                "no un sandbox real — si de verdad hace falta correr esto, hacelo a mano "
                "en Termux."
            )


async def register_phone(ws: SendsText) -> None:
    global _phone_ws
    if _phone_ws is not None and _phone_ws is not ws:
        logger.info("phone_link: nueva conexión reemplaza a la anterior")
        _fail_all_pending("Se reemplazó la conexión del celular por una nueva")
    _phone_ws = ws


async def unregister_phone(ws: SendsText) -> None:
    global _phone_ws
    if _phone_ws is ws:
        _phone_ws = None
        _fail_all_pending("El celular se desconectó")


def _fail_all_pending(reason: str) -> None:
    for call_id, fut in list(_pending.items()):
        if not fut.done():
            fut.set_exception(PhoneNotConnectedError(reason))
        _pending.pop(call_id, None)


def is_phone_connected() -> bool:
    return _phone_ws is not None


async def handle_incoming(message: dict) -> None:
    """Procesa un mensaje recibido del celular (respuesta a un tool call pendiente)."""
    call_id = message.get("id")
    fut = _pending.pop(call_id, None) if call_id else None
    if fut is None or fut.done():
        return
    error = message.get("error")
    if error:
        fut.set_exception(PhoneToolError(str(error)))
    else:
        fut.set_result(message.get("result"))


async def dispatch_to_phone(tool_name: str, arguments: dict[str, Any], timeout: float | None = None) -> Any:
    if tool_name in _SHELL_TOOL_NAMES:
        if not settings.phone_shell_enabled:
            error = "Ejecución de comandos en el celular deshabilitada. Setear PHONE_SHELL_ENABLED=true en backend/.env para habilitarla."
            audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=error)
            raise PermissionError(error)
        command = arguments.get("command")
        if isinstance(command, str):
            try:
                _check_command_blocklist(command)
            except DestructiveCommandBlockedError as exc:
                audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=str(exc))
                raise
        logger.info("phone_shell: tool=%s arguments=%s", tool_name, arguments)

    if tool_name in _CAMERA_TOOL_NAMES:
        if not settings.phone_camera_enabled:
            error = "Uso de la cámara del celular deshabilitado. Setear PHONE_CAMERA_ENABLED=true en backend/.env para habilitarlo."
            audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=error)
            raise PermissionError(error)
        logger.info("phone_camera: tool=%s arguments=%s", tool_name, arguments)

    timeout = timeout if timeout is not None else settings.phone_tool_timeout
    if _phone_ws is None:
        error = "No hay ningún celular conectado a Jarvis en este momento"
        audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=error)
        raise PhoneNotConnectedError(error)

    call_id = str(uuid.uuid4())
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    _pending[call_id] = fut

    payload = {"type": "tool_call", "id": call_id, "tool": tool_name, "arguments": arguments}
    try:
        await _phone_ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        _pending.pop(call_id, None)
        error = f"No se pudo mandar el tool call al celular: {exc}"
        audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=error)
        raise PhoneNotConnectedError(error) from exc

    try:
        result = await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError as exc:
        _pending.pop(call_id, None)
        error = f"El celular no respondió el tool call '{tool_name}' a tiempo"
        audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=error)
        raise TimeoutError(error) from exc
    except Exception as exc:
        audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, error=str(exc))
        raise
    else:
        audit_log.log_tool_call(target="phone", tool=tool_name, arguments=arguments, result=result)
        return result
