import asyncio
import json

import pytest

from app import phone_link
from app.phone_link import (
    PhoneNotConnectedError,
    PhoneToolError,
    dispatch_to_phone,
    handle_incoming,
    is_phone_connected,
    register_phone,
    unregister_phone,
)


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


@pytest.fixture(autouse=True)
def _reset_phone_link():
    """El estado de conexión vive en variables de módulo; aislar entre tests."""
    phone_link._phone_ws = None
    phone_link._pending.clear()
    yield
    phone_link._phone_ws = None
    phone_link._pending.clear()


@pytest.mark.anyio
async def test_dispatch_without_phone_raises():
    assert not is_phone_connected()
    with pytest.raises(PhoneNotConnectedError):
        await dispatch_to_phone("phone_tap", {"x": 1, "y": 2})


@pytest.mark.anyio
async def test_dispatch_round_trip_resolves_with_phone_result():
    ws = FakeWebSocket()
    await register_phone(ws)
    assert is_phone_connected()

    task = asyncio.create_task(dispatch_to_phone("phone_tap", {"x": 1, "y": 2}, timeout=5))
    await asyncio.sleep(0.01)

    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent["type"] == "tool_call"
    assert sent["tool"] == "phone_tap"
    assert sent["arguments"] == {"x": 1, "y": 2}

    await handle_incoming({"id": sent["id"], "result": {"ok": True}})
    result = await task
    assert result == {"ok": True}


@pytest.mark.anyio
async def test_dispatch_propagates_phone_side_error():
    ws = FakeWebSocket()
    await register_phone(ws)

    task = asyncio.create_task(dispatch_to_phone("phone_read_file", {"path": "nope.txt"}, timeout=5))
    await asyncio.sleep(0.01)
    sent = json.loads(ws.sent[0])

    await handle_incoming({"id": sent["id"], "error": "archivo no encontrado"})
    with pytest.raises(PhoneToolError, match="archivo no encontrado"):
        await task


@pytest.mark.anyio
async def test_dispatch_times_out_if_phone_never_responds():
    ws = FakeWebSocket()
    await register_phone(ws)

    with pytest.raises(TimeoutError):
        await dispatch_to_phone("phone_tap", {"x": 1, "y": 2}, timeout=0.05)


@pytest.mark.anyio
async def test_unregister_fails_pending_calls():
    ws = FakeWebSocket()
    await register_phone(ws)

    task = asyncio.create_task(dispatch_to_phone("phone_tap", {"x": 1, "y": 2}, timeout=5))
    await asyncio.sleep(0.01)

    await unregister_phone(ws)
    assert not is_phone_connected()

    with pytest.raises(PhoneNotConnectedError):
        await task


@pytest.mark.anyio
async def test_handle_incoming_ignores_unknown_or_stale_id():
    # No debe explotar si llega una respuesta para un id que no está pendiente.
    await handle_incoming({"id": "no-existe", "result": {}})


@pytest.mark.anyio
async def test_dispatch_phone_run_command_blocked_when_shell_disabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_shell_enabled", False)
    ws = FakeWebSocket()
    await register_phone(ws)

    with pytest.raises(PermissionError):
        await dispatch_to_phone("phone_run_command", {"command": "echo hola"})
    # Ni siquiera debería haber intentado mandarlo por WebSocket.
    assert ws.sent == []


@pytest.mark.anyio
async def test_dispatch_phone_run_command_allowed_when_shell_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_shell_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    task = asyncio.create_task(
        dispatch_to_phone("phone_run_command", {"command": "echo hola"}, timeout=5)
    )
    await asyncio.sleep(0.01)
    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent["tool"] == "phone_run_command"

    await handle_incoming({"id": sent["id"], "result": {"stdout": "hola\n", "exit_code": 0}})
    result = await task
    assert result == {"stdout": "hola\n", "exit_code": 0}


@pytest.mark.anyio
async def test_dispatch_phone_run_command_logs_audit_line(monkeypatch, caplog):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_shell_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    with caplog.at_level("INFO", logger="jarvis.phone_link"):
        task = asyncio.create_task(
            dispatch_to_phone("phone_run_command", {"command": "rm -rf algo"}, timeout=5)
        )
        await asyncio.sleep(0.01)
        sent = json.loads(ws.sent[0])
        await handle_incoming({"id": sent["id"], "result": {}})
        await task

    assert any("phone_shell" in msg and "rm -rf algo" in msg for msg in caplog.messages)
