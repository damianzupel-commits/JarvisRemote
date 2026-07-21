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
import uuid
from typing import Any, Protocol

from .config import settings

logger = logging.getLogger("jarvis.phone_link")


class PhoneNotConnectedError(RuntimeError):
    pass


class PhoneToolError(RuntimeError):
    """La tool falló del lado del celular; el mensaje ya viene listo para mostrar."""


class SendsText(Protocol):
    async def send_text(self, data: str) -> None: ...


_phone_ws: SendsText | None = None
_pending: dict[str, asyncio.Future] = {}

# Tools que ejecutan shell real en el celular (vía Termux) en vez de solo
# interactuar con la UI — nivel de riesgo distinto, se gatean con su propio
# flag (PHONE_SHELL_ENABLED) y se loguean como rastro de auditoría.
_SHELL_TOOL_NAMES = {"phone_run_command"}


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
            raise PermissionError(
                "Ejecución de comandos en el celular deshabilitada. Setear "
                "PHONE_SHELL_ENABLED=true en backend/.env para habilitarla."
            )
        logger.info("phone_shell: tool=%s arguments=%s", tool_name, arguments)

    timeout = timeout if timeout is not None else settings.phone_tool_timeout
    if _phone_ws is None:
        raise PhoneNotConnectedError("No hay ningún celular conectado a Jarvis en este momento")

    call_id = str(uuid.uuid4())
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    _pending[call_id] = fut

    payload = {"type": "tool_call", "id": call_id, "tool": tool_name, "arguments": arguments}
    try:
        await _phone_ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        _pending.pop(call_id, None)
        raise PhoneNotConnectedError(f"No se pudo mandar el tool call al celular: {exc}") from exc

    try:
        return await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError as exc:
        _pending.pop(call_id, None)
        raise TimeoutError(f"El celular no respondió el tool call '{tool_name}' a tiempo") from exc
