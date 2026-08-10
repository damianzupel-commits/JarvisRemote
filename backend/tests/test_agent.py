import json
from types import SimpleNamespace

import pytest

from app import agent
from app.agent import (
    _build_image_message,
    _cap_tool_result,
    _history_char_budget,
    _trim_history,
    _trim_history_by_budget,
    run_agent,
)


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


def test_history_char_budget_shrinks_as_tools_schema_grows(monkeypatch):
    # Bug real 2026-08-09: el schema de tools crece con cada tool nueva
    # registrada -- el presupuesto disponible para historial tiene que
    # reflejar eso en vez de asumir un tamaño de baseline fijo.
    monkeypatch.setattr(agent.settings, "model_context_tokens", 32768)
    monkeypatch.setattr(agent.settings, "reserved_response_tokens", 3000)
    monkeypatch.setattr(agent.settings, "chars_per_token_estimate", 3.2)
    small_budget = _history_char_budget(tools_schema_chars=1000)
    big_budget = _history_char_budget(tools_schema_chars=50_000)
    assert small_budget > big_budget


def test_history_char_budget_never_negative(monkeypatch):
    # Si el baseline (system prompt + tools) solo ya supera lo disponible,
    # el presupuesto de historial tiene que quedar en 0, no negativo --
    # un negativo rompería la comparación de tamaño en _trim_history_by_budget.
    monkeypatch.setattr(agent.settings, "model_context_tokens", 16384)
    monkeypatch.setattr(agent.settings, "reserved_response_tokens", 3000)
    monkeypatch.setattr(agent.settings, "chars_per_token_estimate", 3.2)
    assert _history_char_budget(tools_schema_chars=1_000_000) == 0


def test_trim_history_by_budget_no_change_when_under_budget():
    history = [{"role": "system", "content": "sys"}] + [_user(i) for i in range(3)]
    original = list(history)
    _trim_history_by_budget(history, budget_chars=10_000)
    assert history == original


def test_trim_history_by_budget_drops_oldest_messages_over_budget():
    # Caso real: varios tool results, cada uno chico por separado, pero la
    # SUMA supera el presupuesto -- _trim_history (por cantidad) no lo
    # detectaría si la cantidad de mensajes está bajo su propio límite.
    big_tool_response = {"role": "tool", "tool_call_id": "call_x", "content": "x" * 500}
    history = [{"role": "system", "content": "sys"}]
    for i in range(10):
        history.append(_user(i))
        history.append(_assistant_tool_call(i))
        history.append(dict(big_tool_response, tool_call_id=f"call_{i}"))
    # cada bloque user+tool_call+tool_response ronda 730 chars serializado;
    # un presupuesto de 800 solo deja lugar para el más reciente (dos bloques
    # ya son 1460, no entran).
    _trim_history_by_budget(history, budget_chars=800)
    assert history[0] == {"role": "system", "content": "sys"}
    serialized = json.dumps(history[1:], default=str, ensure_ascii=False)
    assert len(serialized) <= 800
    # se quedó con lo más nuevo, no lo más viejo
    assert history[1] == _user(9)


def test_trim_history_by_budget_always_cuts_at_user_boundary():
    history = [
        {"role": "system", "content": "sys"},
        _user(1),
        _assistant_tool_call(1),
        _tool_response(1),
        _user(2),
        _assistant(2),
    ]
    # presupuesto chico fuerza el corte a caer sobre el tool_call/tool_response
    # de en medio -- tiene que seguir hasta el próximo 'user', igual que
    # _trim_history. 100 entra el tail user(2)+assistant(2) (96 chars) pero no
    # el bloque de en medio con el tool_call (285 chars).
    _trim_history_by_budget(history, budget_chars=100)
    assert history[0] == {"role": "system", "content": "sys"}
    assert history[1]["role"] == "user"


def test_trim_history_by_budget_empty_history_is_noop():
    history = [{"role": "system", "content": "sys"}]
    _trim_history_by_budget(history, budget_chars=0)
    assert history == [{"role": "system", "content": "sys"}]


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


def test_cap_tool_result_no_change_when_under_limit():
    result = {"findings": [{"id": i} for i in range(3)], "total_findings": 3}
    assert _cap_tool_result(result, max_chars=10_000) is result


def test_cap_tool_result_shrinks_largest_list_field():
    # Bug real (2026-08-03): security_scan_project sobre pygoat devolvió 312
    # hallazgos (~47KB de JSON) en un solo tool result -- sumado al system
    # prompt + schema de ~50 tools, eso desplazaba el contexto real del modelo
    # (n_ctx=16384 confirmado en Ollama) y el modelo perdía el pedido original.
    findings = [
        {
            "id": f"finding_{i}",
            "message": "Detected user input used to manually construct a SQL string. " * 5,
        }
        for i in range(300)
    ]
    result = {"total_findings": 300, "findings": findings, "findings_omitted": 0}
    original_size = len(json.dumps(result))

    capped = _cap_tool_result(result, max_chars=6000)

    capped_size = len(json.dumps(capped, default=str, ensure_ascii=False))
    assert capped_size <= 6000
    assert capped_size < original_size
    # el campo lista más grande ('findings') es el que se recorta, no otros campos
    assert capped["total_findings"] == 300
    assert len(capped["findings"]) < len(findings)
    assert capped["findings_omitted_by_size_limit"] == 300 - len(capped["findings"])
    assert "_note" in capped
    # los items que sí quedaron no se alteran (recorte por cantidad, no por contenido)
    assert capped["findings"][0] == findings[0]


def test_cap_tool_result_shrinks_to_zero_items_if_even_one_is_too_big():
    huge_item = {"id": "x", "blob": "a" * 20_000}
    result = {"findings": [huge_item]}
    capped = _cap_tool_result(result, max_chars=1000)
    assert capped["findings"] == []
    assert capped["findings_omitted_by_size_limit"] == 1


def test_cap_tool_result_falls_back_to_raw_truncation_when_no_list_field():
    result = {"content": "x" * 20_000}
    capped = _cap_tool_result(result, max_chars=1000)
    assert "_note" in capped
    assert len(capped["truncated_content"]) <= 1000


def test_cap_tool_result_falls_back_when_result_is_not_a_dict():
    result = "y" * 20_000
    capped = _cap_tool_result(result, max_chars=1000)
    assert isinstance(capped, dict)
    assert len(capped["truncated_content"]) <= 1000


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
async def test_run_agent_attaches_video_frames_and_strips_video_base64(monkeypatch):
    tool_call = _fake_tool_call("call_3", "phone_record_video", {"camera": "back", "duration_seconds": 5})
    video_result = {"video_base64": "ZmFrZXZpZGVv", "mime_type": "video/mp4", "duration_seconds": 5}
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="Vi que la persona caminaba de izquierda a derecha."),
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        assert name == "phone_record_video"
        return video_result

    def fake_extract_frames(video_base64, interval_seconds, max_frames):
        assert video_base64 == "ZmFrZXZpZGVv"
        return ["frame1_b64", "frame2_b64", "frame3_b64"]

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)
    monkeypatch.setattr(agent, "extract_frames_from_video_base64", fake_extract_frames)

    conv_id, reply, _ = await run_agent("grabá un video y decime qué ves", conversation_id="test-video-1")

    assert reply == "Vi que la persona caminaba de izquierda a derecha."
    history = agent._conversations[conv_id]

    tool_messages = [m for m in history if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "video_base64" not in tool_messages[0]["content"]
    assert "frames_extracted" in tool_messages[0]["content"]

    image_messages = [
        m for m in history if m.get("role") == "user" and isinstance(m.get("content"), list)
    ]
    assert len(image_messages) == 1
    blocks = image_messages[0]["content"]
    assert len(blocks) == 4  # 1 bloque de texto + 3 frames
    assert [b["image_url"]["url"] for b in blocks[1:]] == [
        "data:image/jpeg;base64,frame1_b64",
        "data:image/jpeg;base64,frame2_b64",
        "data:image/jpeg;base64,frame3_b64",
    ]


@pytest.mark.anyio
async def test_run_agent_handles_video_decode_failure_gracefully(monkeypatch):
    tool_call = _fake_tool_call("call_4", "phone_record_video", {"camera": "back"})
    video_result = {"video_base64": "Z2FyYmFnZQ==", "mime_type": "video/mp4"}
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="El video no se pudo procesar, avisale al usuario."),
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        return video_result

    def fake_extract_frames(video_base64, interval_seconds, max_frames):
        from app.video_frames import VideoDecodeError

        raise VideoDecodeError("archivo corrupto")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)
    monkeypatch.setattr(agent, "extract_frames_from_video_base64", fake_extract_frames)

    conv_id, reply, tool_log = await run_agent("grabá un video", conversation_id="test-video-2")

    # No crashea: el error queda en el resultado de la tool, no se propaga.
    assert "error" in tool_log[-1]["result"]
    history = agent._conversations[conv_id]
    image_messages = [
        m for m in history if m.get("role") == "user" and isinstance(m.get("content"), list)
    ]
    assert image_messages == []
    # No dispara el fallback de visión: nunca se llegó a adjuntar una imagen real,
    # así que el modelo sigue respondiendo texto plano normal.
    assert reply == "El video no se pudo procesar, avisale al usuario."


@pytest.mark.anyio
async def test_run_agent_reraises_llm_error_when_not_awaiting_vision(monkeypatch):
    """El try/except del fallback de visión no debe tragarse errores reales de la
    llamada al modelo que no tengan nada que ver con una foto recién mandada."""

    async def fake_create(**kwargs):
        raise RuntimeError("Context size has been exceeded.")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with pytest.raises(RuntimeError, match="Context size has been exceeded"):
        await run_agent("hola", conversation_id="test-image-3")


@pytest.mark.anyio
async def test_run_agent_caps_huge_tool_result_before_reinjecting_to_model(monkeypatch):
    """Reproduce a nivel de código el bug real (2026-08-03): security_scan_project
    sobre un proyecto con muchos hallazgos devuelve un resultado gigante que, sin
    recorte, se manda entero al modelo como mensaje 'tool' -- eso es lo que hacía
    que el modelo perdiera el system prompt y el pedido original (contexto real de
    16384 tokens en Ollama para jarvis-text-v2, ver app/config.py::
    max_tool_result_chars). Acá no probamos el LLM real: probamos que `run_agent`
    nunca vuelve a inyectar un tool result sin pasar por `_cap_tool_result`."""
    monkeypatch.setattr(agent.settings, "max_tool_result_chars", 500)

    tool_call = _fake_tool_call("call_5", "security_scan_project", {"path": "C:/some/project"})
    huge_findings = [
        {"id": f"f{i}", "message": "Possible SQL injection vector. " * 10} for i in range(300)
    ]
    scan_result = {"total_findings": 300, "findings": huge_findings}
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="Encontré el hallazgo B608 y te propongo un fix."),
    ]

    async def fake_create(**kwargs):
        # Esto es justo lo que se rompía: si el mensaje 'tool' de la vuelta
        # anterior no está capado, el payload que "llega al modelo" en la
        # siguiente vuelta lleva el JSON gigante entero.
        for msg in kwargs["messages"]:
            if msg.get("role") == "tool":
                assert len(msg["content"]) <= 500
        return responses.pop(0)

    async def fake_call_tool(name, args):
        assert name == "security_scan_project"
        return scan_result

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent(
        "auditá y arreglá el hallazgo B608", conversation_id="test-cap-1"
    )

    assert reply == "Encontré el hallazgo B608 y te propongo un fix."
    history = agent._conversations[conv_id]
    tool_messages = [m for m in history if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert len(tool_messages[0]["content"]) <= 500
    # el resultado original (sin capar) tenía las 300 findings intactas
    assert len(json.dumps(scan_result)) > 500
    # tool_log (lo que ve la UI del tray) refleja lo mismo que vio el modelo,
    # no el resultado sin capar -- si no, la UI mostraría datos que el modelo
    # nunca llegó a "ver".
    assert len(tool_log[-1]["result"]["findings"]) < len(huge_findings)
