import pytest

from app import phone_link
from app.phone_link import PhoneNotConnectedError
from app.tools import call_tool, get_tools, openai_tool_schemas


def test_phone_tools_registered_with_phone_target():
    tools = get_tools()
    phone_tool_names = {
        "phone_open_app",
        "phone_list_dir",
        "phone_read_file",
        "phone_write_file",
        "phone_tap",
        "phone_swipe",
        "phone_type_text",
        "phone_read_screen",
        "phone_global_action",
        "phone_run_command",
    }
    assert phone_tool_names <= tools.keys()
    for name in phone_tool_names:
        assert tools[name].target == "phone"


def test_pc_tools_default_to_pc_target():
    tools = get_tools()
    assert tools["fs_list_dir"].target == "pc"
    assert tools["browser_open"].target == "pc"
    assert tools["jarvis_reflect"].target == "pc"
    # generate_video/generate_image (video_gen.py/image_gen.py) están
    # deliberadamente deshabilitadas desde 2026-07-27 (no importadas en
    # app/tools/__init__.py, ver el comentario ahí) tras un apagado físico
    # real de la PC en medio de una generación -- no deberían estar
    # registradas. Este assert quedó estancado referenciándolas de cuando sí
    # lo estaban; test-order dependency real encontrada 2026-08-11 (algún
    # otro test importa video_gen.py directo, registrándolas igual como
    # efecto secundario si corre antes en la MISMA sesión de pytest) -- lo
    # correcto es no depender de que estén, sea cual sea el orden real.
    assert "generate_video" not in tools or tools["generate_video"].target == "pc"
    assert "generate_image" not in tools or tools["generate_image"].target == "pc"


def test_openai_tool_schemas_expose_single_flat_list():
    schemas = openai_tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert "fs_list_dir" in names
    assert "phone_tap" in names
    # El schema no debe filtrar el campo interno `target` al LLM.
    for schema in schemas:
        assert "target" not in schema["function"]


@pytest.mark.anyio
async def test_call_tool_routes_phone_target_via_phone_link(monkeypatch):
    phone_link._phone_ws = None
    phone_link._pending.clear()
    with pytest.raises(PhoneNotConnectedError):
        await call_tool("phone_tap", {"x": 1, "y": 2})


@pytest.mark.anyio
async def test_call_tool_executes_pc_handler_directly():
    result = await call_tool("fs_list_dir", {"path": "."})
    assert "entries" in result


@pytest.mark.anyio
async def test_call_tool_extends_dispatch_timeout_from_tool_arguments(monkeypatch):
    """phone_run_command trae su propio 'timeout' (cuánto espera Termux el comando) — el
    backend tiene que esperar por lo menos eso + margen, si no el wait del backend
    (settings.phone_tool_timeout) podría vencer antes de que el celular termine de esperar."""
    captured = {}

    async def _fake_dispatch(name, arguments, timeout=None):
        captured["name"] = name
        captured["arguments"] = arguments
        captured["timeout"] = timeout
        return {"ok": True}

    monkeypatch.setattr("app.phone_link.dispatch_to_phone", _fake_dispatch)

    await call_tool("phone_run_command", {"command": "echo hola", "timeout": 60})

    assert captured["timeout"] == 65.0


@pytest.mark.anyio
async def test_call_tool_uses_default_dispatch_timeout_when_no_timeout_argument(monkeypatch):
    captured = {}

    async def _fake_dispatch(name, arguments, timeout=None):
        captured["timeout"] = timeout
        return {"ok": True}

    monkeypatch.setattr("app.phone_link.dispatch_to_phone", _fake_dispatch)

    await call_tool("phone_tap", {"x": 1, "y": 2})

    assert captured["timeout"] is None


@pytest.mark.anyio
async def test_call_tool_routes_desktop_module_tools_through_a_thread(monkeypatch):
    """Bug real (informe de arquitectura 2026-08-10, corregido vía Opción C):
    app/tools/desktop.py corre pyautogui/pywinauto (sync, con sleeps/polls
    reales de varios segundos) directo en el thread del event loop de
    FastAPI, bloqueando /api/health, el WebSocket del celular, y cualquier
    otra tool call mientras tanto. call_tool ahora las corre vía
    asyncio.to_thread -- acá se mockea to_thread (no queremos pyautogui real
    en la suite) para probar que SE USA para tools de ese módulo."""
    from app import tools as tools_module

    captured = {}

    async def fake_to_thread(func, **kwargs):
        captured["func"] = func
        captured["kwargs"] = kwargs
        return {"ok": True, "via": "thread"}

    monkeypatch.setattr(tools_module.asyncio, "to_thread", fake_to_thread)

    result = await call_tool("desktop_click", {"x": 10, "y": 20})

    assert result == {"ok": True, "via": "thread"}
    assert captured["func"].__module__ == "app.tools.desktop"
    assert captured["kwargs"] == {"x": 10, "y": 20}


@pytest.mark.anyio
async def test_call_tool_does_not_route_non_desktop_pc_tools_through_a_thread(monkeypatch):
    from app import tools as tools_module

    to_thread_called = False

    async def fake_to_thread(func, **kwargs):
        nonlocal to_thread_called
        to_thread_called = True
        return func(**kwargs)

    monkeypatch.setattr(tools_module.asyncio, "to_thread", fake_to_thread)

    result = await call_tool("fs_list_dir", {"path": "."})

    assert "entries" in result
    assert to_thread_called is False
