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
    }
    assert phone_tool_names <= tools.keys()
    for name in phone_tool_names:
        assert tools[name].target == "phone"


def test_pc_tools_default_to_pc_target():
    tools = get_tools()
    assert tools["fs_list_dir"].target == "pc"
    assert tools["browser_open"].target == "pc"


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
