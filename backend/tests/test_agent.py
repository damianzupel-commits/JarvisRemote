import json
from types import SimpleNamespace

import pytest

from app import agent
from app.agent import _build_image_message, _trim_history, run_agent


def _user(i: int) -> dict:
    return {"role": "user", "content": f"user msg {i}"}


def _assistant(i: int) -> dict:
    return {"role": "assistant", "content": f"assistant msg {i}"}


def _assistant_tool_call(i: int) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": f"call_{i}", "function": {"name": "some_tool", "arguments": "{}"}}],
    }


def _tool_response(i: int) -> dict:
    return {"role": "tool", "tool_call_id": f"call_{i}", "content": "{}"}


def test_no_trim_when_under_limit():
    history = [{"role": "system", "content": "sys"}] + [_user(i) for i in range(5)]
    original = list(history)
    _trim_history(history, max_messages=40)
    assert history == original


def test_no_trim_when_exactly_at_limit():
    history = [{"role": "system", "content": "sys"}] + [_user(i) for i in range(10)]
    original = list(history)
    _trim_history(history, max_messages=10)
    assert history == original


def test_trims_oldest_messages_past_limit():
    history = [{"role": "system", "content": "sys"}] + [_user(i) for i in range(20)]
    _trim_history(history, max_messages=10)
    # el system prompt siempre se conserva
    assert history[0] == {"role": "system", "content": "sys"}
    # el cuerpo quedó acotado al límite (todos son 'user', así que corta justo ahí)
    assert len(history) - 1 == 10
    # se quedó con los mensajes más nuevos, no los viejos
    assert history[1] == _user(10)
    assert history[-1] == _user(19)


def test_cut_lands_on_next_user_message_not_mid_tool_call():
    # excedente cae justo sobre un par assistant(tool_call)/tool — no se puede
    # cortar ahí sin romper el pedido al modelo (tool_call sin su respuesta).
    history = [
        {"role": "system", "content": "sys"},
        _user(1),
        _assistant_tool_call(1),
        _tool_response(1),
        _user(2),
        _assistant(2),
    ]
    # limit=3 fuerza el corte a caer sobre _assistant_tool_call(1) o _tool_response(1);
    # como ninguno es 'user', tiene que seguir buscando hasta _user(2).
    _trim_history(history, max_messages=3)
    assert history[0] == {"role": "system", "content": "sys"}
    assert history[1] == _user(2)
    assert history[2] == _assistant(2)
    # nunca queda un mensaje 'tool' o un tool_call sin pareja al principio del cuerpo
    assert history[1]["role"] == "user"


def test_no_user_message_in_excess_clears_body():
    # caso degenerado: todo el excedente es no-'user' y no hay ningún 'user'
    # más adelante para cortar — se vacía el cuerpo en vez de romper algo.
    history = [
        {"role": "system", "content": "sys"},
        _assistant(1),
        _assistant(2),
        _assistant(3),
    ]
    _trim_history(history, max_messages=1)
    assert history[0] == {"role": "system", "content": "sys"}
    assert history[1:] == []


def test_preserves_system_prompt_always():
    history = [{"role": "system", "content": "sys"}] + [_user(i) for i in range(100)]
    _trim_history(history, max_messages=5)
    assert history[0] == {"role": "system", "content": "sys"}


def test_build_image_message_shape():
    result = {"image_base64": "ZmFrZQ==", "mime_type": "image/png"}
    msg = _build_image_message(result)
    assert msg["role"] == "user"
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,ZmFrZQ=="},
    }


def test_build_image_message_defaults_to_jpeg_mime():
    msg = _build_image_message({"image_base64": "abc"})
    assert msg["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,abc"


def _fake_tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    args_json = json.dumps(arguments)
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=args_json),
        model_dump=lambda: {"id": call_id, "function": {"name": name, "arguments": args_json}},
    )


def _fake_response(tool_calls: list | None = None, content: str | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.anyio
async def test_run_agent_attaches_image_message_and_strips_base64_from_tool_message(monkeypatch):
    tool_call = _fake_tool_call("call_1", "phone_take_photo", {"camera": "back"})
    photo_result = {"image_base64": "ZmFrZQ==", "mime_type": "image/jpeg", "width": 1024, "height": 768}
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="Veo una foto de prueba."),
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        assert name == "phone_take_photo"
        return photo_result

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, _ = await run_agent("sacá una foto y decime qué ves", conversation_id="test-image-1")

    assert reply == "Veo una foto de prueba."
    history = agent._conversations[conv_id]

    tool_messages = [m for m in history if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "image_base64" not in tool_messages[0]["content"]

    image_messages = [
        m for m in history if m.get("role") == "user" and isinstance(m.get("content"), list)
    ]
    assert len(image_messages) == 1
    blocks = image_messages[0]["content"]
    assert blocks[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,ZmFrZQ=="},
    }


@pytest.mark.anyio
async def test_run_agent_returns_vision_fallback_when_model_cant_see_image(monkeypatch):
    tool_call = _fake_tool_call("call_2", "phone_take_photo", {"camera": "back"})
    photo_result = {"image_base64": "ZmFrZQ==", "mime_type": "image/jpeg"}
    responses = [_fake_response(tool_calls=[tool_call])]

    async def fake_create(**kwargs):
        if responses:
            return responses.pop(0)
        raise RuntimeError("el modelo cargado no soporta contenido multimodal")

    async def fake_call_tool(name, args):
        return photo_result

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, _ = await run_agent("qué ves con la cámara?", conversation_id="test-image-2")

    assert reply == agent._VISION_FALLBACK_MSG
    assert agent._conversations[conv_id][-1] == {
        "role": "assistant",
        "content": agent._VISION_FALLBACK_MSG,
    }


@pytest.mark.anyio
async def test_run_agent_reraises_llm_error_when_not_awaiting_vision(monkeypatch):
    """El try/except del fallback de visión no debe tragarse errores reales de la
    llamada al modelo que no tengan nada que ver con una foto recién mandada."""

    async def fake_create(**kwargs):
        raise RuntimeError("Context size has been exceeded.")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with pytest.raises(RuntimeError, match="Context size has been exceeded"):
        await run_agent("hola", conversation_id="test-image-3")
