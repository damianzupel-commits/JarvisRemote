import asyncio
import json

import pytest

from app import phone_link
from app.phone_link import (
    DestructiveCommandBlockedError,
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf ~",
        "rm -fr /",
        "sudo rm -rf /",
        "  rm   -rf    /  ",
        "mkfs.ext4 /dev/block/mmcblk0p1",
        "mkfs /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        ":(){ :|:& };:",
        "chmod -R 777 /",
        "chown -R user:user /",
        "echo pwned > /dev/sda",
    ],
)
async def test_dispatch_blocks_destructive_command_patterns(command, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_shell_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    with pytest.raises(DestructiveCommandBlockedError):
        await dispatch_to_phone("phone_run_command", {"command": command})

    # Ni siquiera debería haber llegado a mandarse por WebSocket.
    assert ws.sent == []


@pytest.mark.anyio
async def test_dispatch_blocked_command_logs_a_warning(monkeypatch, caplog):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_shell_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    with caplog.at_level("WARNING", logger="jarvis.phone_link"):
        with pytest.raises(DestructiveCommandBlockedError):
            await dispatch_to_phone("phone_run_command", {"command": "rm -rf /"})

    assert any("BLOQUEADO" in msg for msg in caplog.messages)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "command",
    [
        "echo hola",
        "rm -rf /tmp/foo",
        "rm archivo.txt",
        "rm -rf ./build",
        "rm -rf output/",
        "ls -la /",
        "chmod -R 755 ./myproject",
        "chmod 644 archivo.txt",
        "dd if=input.img of=output.img",
        "git clone https://example.com/repo.git",
        "python script.py",
        "cat /etc/hostname",
    ],
)
async def test_dispatch_allows_legitimate_commands_that_look_similar(command, monkeypatch):
    """Casos pensados para no bloquearse por accidente (falsos positivos) contra el
    blocklist — rutas relativas, comandos de solo-lectura, y variantes que se
    parecen superficialmente a un patrón bloqueado pero no lo son."""
    from app.config import settings

    monkeypatch.setattr(settings, "phone_shell_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    task = asyncio.create_task(
        dispatch_to_phone("phone_run_command", {"command": command}, timeout=5)
    )
    await asyncio.sleep(0.01)
    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])

    await handle_incoming({"id": sent["id"], "result": {"stdout": "", "exit_code": 0}})
    result = await task
    assert result == {"stdout": "", "exit_code": 0}


@pytest.mark.anyio
async def test_dispatch_phone_take_photo_blocked_when_camera_disabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_camera_enabled", False)
    ws = FakeWebSocket()
    await register_phone(ws)

    with pytest.raises(PermissionError):
        await dispatch_to_phone("phone_take_photo", {"camera": "back"})
    # Ni siquiera debería haber intentado mandarlo por WebSocket.
    assert ws.sent == []


@pytest.mark.anyio
async def test_dispatch_phone_take_photo_allowed_when_camera_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_camera_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    task = asyncio.create_task(
        dispatch_to_phone("phone_take_photo", {"camera": "back"}, timeout=5)
    )
    await asyncio.sleep(0.01)
    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent["tool"] == "phone_take_photo"

    fake_result = {"image_base64": "ZmFrZQ==", "mime_type": "image/jpeg", "width": 1024, "height": 768}
    await handle_incoming({"id": sent["id"], "result": fake_result})
    result = await task
    assert result == fake_result


@pytest.mark.anyio
async def test_dispatch_phone_record_video_blocked_when_camera_disabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_camera_enabled", False)
    ws = FakeWebSocket()
    await register_phone(ws)

    with pytest.raises(PermissionError):
        await dispatch_to_phone("phone_record_video", {"camera": "back", "duration_seconds": 5})
    assert ws.sent == []


@pytest.mark.anyio
async def test_dispatch_phone_record_video_allowed_when_camera_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "phone_camera_enabled", True)
    ws = FakeWebSocket()
    await register_phone(ws)

    task = asyncio.create_task(
        dispatch_to_phone("phone_record_video", {"camera": "back", "duration_seconds": 5}, timeout=5)
    )
    await asyncio.sleep(0.01)
    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent["tool"] == "phone_record_video"

    fake_result = {"video_base64": "ZmFrZQ==", "mime_type": "video/mp4", "duration_seconds": 5}
    await handle_incoming({"id": sent["id"], "result": fake_result})
    result = await task
    assert result == fake_result
