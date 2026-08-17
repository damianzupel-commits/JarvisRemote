import json
import logging.handlers
from types import SimpleNamespace

import pytest

from app import agent
from app import audit_log as audit_log_module
from app.agent import (
    _build_image_message,
    _cap_tool_result,
    _history_char_budget,
    _pending_blocked_write_paths,
    _trim_history,
    _trim_history_by_budget,
    run_agent,
)


@pytest.fixture(autouse=True)
def _isolated_audit_log(tmp_path, monkeypatch):
    """Bug real encontrado 2026-08-11 al agregar `_live_identical_rewrite_loop_error`
    (primer guardrail que LEE audit_log en vivo, no solo escribe): estos tests
    nunca aislaban `_AUDIT_LOG_PATH` porque hasta ahora nada en agent.py leía
    de vuelta lo que escribía -- pero el archivo real (`backend/audit.log`)
    persiste entre corridas de pytest, así que dos tests (o dos corridas
    distintas) que reusan el mismo `conversation_id` literal (ej.
    "test-iter-cap-1") terminaban viendo entradas de un turno anterior como si
    fueran de la sesión actual. `_AUDIT_LOG_PATH` solo, monkeypateado, no
    alcanza -- el handler de `_audit_logger` ya quedó atado al archivo real
    en el import del módulo, así que hay que reemplazarlo también."""
    log_path = tmp_path / "audit.log"
    handler = logging.handlers.RotatingFileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    monkeypatch.setattr(audit_log_module, "_AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr(audit_log_module._audit_logger, "handlers", [handler])
    yield
    handler.close()


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


def test_no_user_message_at_all_never_clears_body():
    # Caso degenerado: no hay NINGÚN mensaje 'user' en el cuerpo. La versión
    # vieja (con el bug real 2026-08-10, ver docstring de _trim_history)
    # vaciaba el cuerpo entero en este caso -- la versión corregida trata
    # todo el cuerpo como "turno en curso" (sin marcador de 'user' para
    # separar turnos viejos) y lo preserva entero, aunque eso signifique
    # pasarse del límite -- mejor eso que perder contexto sin aviso.
    history = [
        {"role": "system", "content": "sys"},
        _assistant(1),
        _assistant(2),
        _assistant(3),
    ]
    _trim_history(history, max_messages=1)
    assert history[0] == {"role": "system", "content": "sys"}
    assert history[1:] == [_assistant(1), _assistant(2), _assistant(3)]


def test_trim_history_never_wipes_a_single_long_user_turn():
    # Bug real 2026-08-10, encontrado corriendo el caso real de crear un mod
    # de Minecraft/Fabric desde cero: un turno de UN SOLO mensaje 'user'
    # seguido de una cadena larga de tool calls (19 en esa corrida, sin
    # ninguna segunda pregunta del usuario después) hizo que el cuerpo
    # superara max_history_messages -- la versión vieja de _trim_history
    # buscaba "el próximo 'user'" arrancando después del excedente, nunca lo
    # encontraba (no hay ningún otro 'user' más adelante), y terminaba
    # podando TODO el cuerpo, incluido el pedido original. El modelo se
    # quedó sin contexto y respondió con el saludo genérico de siempre
    # ("¡Hola! Soy Jarvis...") en vez de seguir armando el mod.
    history = [{"role": "system", "content": "sys"}, _user(0)]
    for i in range(25):
        history.append(_assistant_tool_call(i))
        history.append(_tool_response(i))
    # 1 (user) + 25*2 (tool calls) = 51 mensajes en el cuerpo, bien por
    # encima de max_messages=40.

    _trim_history(history, max_messages=40)

    assert history[0] == {"role": "system", "content": "sys"}
    assert history[1] == _user(0)  # el pedido original SIEMPRE sobrevive


def test_preserves_system_prompt_always():
    history = [{"role": "system", "content": "sys"}] + [_user(i) for i in range(100)]
    _trim_history(history, max_messages=5)
    assert history[0] == {"role": "system", "content": "sys"}


def test_system_prompt_treats_external_tool_content_as_data_not_instructions():
    # Guardrail agregado 2026-08-16 (playlist "Info para Jarvis" -> nota sobre
    # servidores MCP hackeados): browser_get_text/research_topic/fs_read_file
    # meten texto de afuera (páginas web, archivos que Jarvis no escribió) al
    # contexto del modelo sin ningún marcado -- sin esto, una página o archivo
    # con una instrucción oculta ("ignorá las instrucciones anteriores...")
    # podía hacer que el modelo la tratara como una orden real de Damian.
    for prompt in (agent.SYSTEM_PROMPT, agent.RESEARCH_SYSTEM_PROMPT):
        assert "DATO" in prompt
        assert "ignorá las instrucciones anteriores" in prompt
        assert "única fuente válida de instrucciones" in prompt


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


def test_trim_history_by_budget_never_drops_the_only_user_message():
    # Bug real 2026-08-09 (round 2), encontrado corriendo el caso real de
    # auditar+reparar+verificar un B608 en pygoat: un turno de UN SOLO mensaje
    # 'user' con una cadena larga de tool calls (12 en esa corrida) no tiene
    # ningún otro 'user' más adelante para usar como límite de corte -- la
    # versión anterior de esta función terminaba podando TODO, incluido el
    # pedido original, y el modelo respondía con un saludo genérico sin
    # ningún contexto de qué tenía que hacer. Acá se simula ese caso exacto:
    # un solo 'user' seguido de muchos pares tool_call/tool_response.
    big_tool_response = {"role": "tool", "tool_call_id": "call_x", "content": "x" * 500}
    history = [{"role": "system", "content": "sys"}, _user(0)]
    for i in range(15):
        history.append(_assistant_tool_call(i))
        history.append(dict(big_tool_response, tool_call_id=f"call_{i}"))

    _trim_history_by_budget(history, budget_chars=500)  # bien por debajo del tamaño real

    assert history[0] == {"role": "system", "content": "sys"}
    assert history[1] == _user(0)  # el pedido original SIEMPRE sobrevive


def test_trim_history_by_budget_drops_old_turns_but_keeps_current_turn_whole():
    # Caso multi-turno: hay un turno viejo ya resuelto (user(1)+assistant(1))
    # y el turno EN CURSO (user(2) + una cadena de tool calls) -- el viejo se
    # puede podar entero para hacer lugar, pero el turno en curso no se toca
    # ni se corta a la mitad aunque el presupuesto sea chico.
    old_turn = [_user(1), _assistant(1)]
    current_tool_call = {
        "role": "tool", "tool_call_id": "call_1",
        "content": "y" * 200,
    }
    current_turn = [_user(2), _assistant_tool_call(2), current_tool_call]
    history = [{"role": "system", "content": "sys"}, *old_turn, *current_turn]

    current_turn_chars = len(json.dumps(current_turn, default=str, ensure_ascii=False))
    _trim_history_by_budget(history, budget_chars=current_turn_chars + 10)

    assert history[1:] == current_turn


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


@pytest.mark.anyio
async def test_run_agent_caps_output_tokens_on_every_llm_call(monkeypatch):
    """Bug real 2026-08-10: no había NINGÚN tope de tokens de SALIDA -- solo se
    acotaba lo que entraba al prompt (_history_char_budget/_trim_history_by_budget),
    nada acotaba cuánto podía generar el modelo en una sola respuesta. En una
    corrida real (reparación masiva en pygoat), justo después de que Ollama
    disparara su propio context-shift (contexto casi lleno), la respuesta entró
    en lo que parece un loop de repetición y siguió generando sin parar (2800+
    tokens y subiendo cuando se cortó a mano, contra ~100-450 de lo normal).
    Acá se verifica que TODA llamada a la API (sea la que decide un tool_call o
    la que da la respuesta final) lleva max_tokens=settings.reserved_response_tokens,
    para que un loop roto quede acotado (finish_reason='length') en vez de poder
    consumir sin límite el resto del contexto."""
    monkeypatch.setattr(agent.settings, "reserved_response_tokens", 3000)

    tool_call = _fake_tool_call("call_9", "security_scan_project", {"path": "C:/some/project"})
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="listo"),
    ]
    seen_max_tokens = []

    async def fake_create(**kwargs):
        seen_max_tokens.append(kwargs.get("max_tokens"))
        return responses.pop(0)

    async def fake_call_tool(name, args):
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("auditá el proyecto", conversation_id="test-max-tokens-1")

    assert len(seen_max_tokens) == 2  # una por cada vuelta del loop (tool_call + respuesta final)
    assert all(v == 3000 for v in seen_max_tokens)


@pytest.mark.anyio
async def test_run_agent_blocks_fs_write_file_until_obsidian_search_notes_called(monkeypatch):
    """Bug real 2026-08-10: pedirle en el system prompt que consulte Obsidian antes
    de escribir código no alcanzó -- en dos corridas reales seguidas (crear un mod
    de Fabric para Minecraft, v2 y v3) el modelo lo ignoró las dos veces a pesar de
    la instrucción explícita en el pedido del usuario, y terminó escribiendo
    build.gradle con nombres de configuración inventados y un evento de golpe
    nunca conectado -- errores que una nota real ya cargada hubiera evitado, si
    se hubiera consultado. Acá se verifica el guardrail duro: el primer intento de
    fs_write_file sin haber llamado obsidian_search_notes antes en el turno se
    rechaza con un error (nunca llega a call_tool), el modelo lo ve, y recién el
    fs_write_file DESPUÉS de un obsidian_search_notes exitoso se ejecuta de verdad."""
    write_call = _fake_tool_call("call_1", "fs_write_file", {"path": "app.py", "content": "print(1)"})
    search_call = _fake_tool_call("call_2", "obsidian_search_notes", {"query": "Flask"})
    write_call_2 = _fake_tool_call("call_3", "fs_write_file", {"path": "app.py", "content": "print(1)"})
    responses = [
        _fake_response(tool_calls=[write_call]),  # 1er intento: debería bloquearse
        _fake_response(tool_calls=[search_call]),  # el modelo reacciona al error y consulta Obsidian
        _fake_response(tool_calls=[write_call_2]),  # reintento: ahora sí debería pasar
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent("creá una app Flask", conversation_id="test-obsidian-gate-1")

    # call_tool NUNCA se llamó para el primer fs_write_file -- se bloqueó antes.
    assert calls_made == ["obsidian_search_notes", "fs_write_file"]
    assert tool_log[0]["tool"] == "fs_write_file"
    assert "error" in tool_log[0]["result"]
    assert "obsidian_search_notes" in tool_log[0]["result"]["error"]
    assert tool_log[1]["tool"] == "obsidian_search_notes"
    assert tool_log[1]["result"] == {"ok": True}
    assert tool_log[2]["tool"] == "fs_write_file"
    assert tool_log[2]["result"] == {"ok": True}  # el segundo intento sí se ejecutó de verdad


@pytest.mark.anyio
async def test_run_agent_does_not_block_fs_write_file_after_obsidian_already_consulted(monkeypatch):
    """Si obsidian_search_notes ya se llamó ANTES en el turno (antes del primer
    fs_write_file), el guardrail no debe bloquear nada -- caso normal, sin fricción
    extra para el flujo que ya hace lo correcto."""
    search_call = _fake_tool_call("call_1", "obsidian_search_notes", {"query": "Flask"})
    write_call = _fake_tool_call("call_2", "fs_write_file", {"path": "app.py", "content": "print(1)"})
    responses = [
        _fake_response(tool_calls=[search_call]),
        _fake_response(tool_calls=[write_call]),
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("creá una app Flask", conversation_id="test-obsidian-gate-2")

    assert calls_made == ["obsidian_search_notes", "fs_write_file"]


@pytest.mark.anyio
async def test_run_agent_extends_iteration_cap_once_fs_write_file_is_used(monkeypatch):
    """Bug real 2026-08-10: crear un mod de Fabric multi-archivo (build.gradle,
    fabric.mod.json, varias clases Java, tags, lang, modelos) agotó las 30
    iteraciones default antes de terminar de armar el wrapper de Gradle o
    intentar compilar. Acá se verifica que, en cuanto el turno usa fs_write_file
    una vez, el tope efectivo de iteraciones sube al de tareas de código
    (settings.max_agent_iterations_code_task) en vez de quedarse en el default
    bajo pensado para chat/auditorías -- sin tocar el default general."""
    monkeypatch.setattr(agent.settings, "max_agent_iterations", 3)
    monkeypatch.setattr(agent.settings, "max_agent_iterations_code_task", 6)

    search_call = _fake_tool_call("call_0", "obsidian_search_notes", {"query": "algo"})
    write_call = _fake_tool_call("call_1", "fs_write_file", {"path": "a.py", "content": "x"})
    other_call = _fake_tool_call("call_2", "fs_read_file", {"path": "a.py"})
    # 1 (search) + 1 (write, sube el tope acá) + 3 más de otra tool + 1 respuesta
    # final = 6 vueltas del loop en total -- por encima del default (3) pero
    # justo dentro del tope extendido (6).
    responses = [_fake_response(tool_calls=[search_call])]
    responses.append(_fake_response(tool_calls=[write_call]))
    for i in range(3):
        responses.append(_fake_response(tool_calls=[other_call]))
    responses.append(_fake_response(content="listo"))

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent("creá un script", conversation_id="test-iter-cap-1")

    # Si el tope efectivo se hubiera quedado en 3 (el default), esto habría
    # cortado con el fallback de MAX_AGENT_ITERATIONS bastante antes.
    assert reply == "listo"
    assert len(tool_log) == 5


@pytest.mark.anyio
async def test_run_agent_keeps_default_iteration_cap_when_fs_write_file_never_used(monkeypatch):
    """El tope extendido es SOLO para tareas que de verdad terminan escribiendo
    código -- una auditoría normal (sin fs_write_file en ningún momento) tiene
    que seguir respetando el default bajo, no el extendido de tareas de código."""
    monkeypatch.setattr(agent.settings, "max_agent_iterations", 2)
    monkeypatch.setattr(agent.settings, "max_agent_iterations_code_task", 50)

    scan_call = _fake_tool_call("call_1", "security_scan_project", {"path": "C:/proj"})
    responses = [
        _fake_response(tool_calls=[scan_call]),
        _fake_response(tool_calls=[scan_call]),
        _fake_response(tool_calls=[scan_call]),  # nunca debería llegar a esta
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent("auditá el proyecto", conversation_id="test-iter-cap-2")

    assert reply == "No pude terminar la tarea dentro del límite de pasos permitidos (MAX_AGENT_ITERATIONS)."
    assert len(tool_log) == 2  # cortó en el default (2), no llegó a usar el tope de código


@pytest.mark.anyio
async def test_run_agent_blocks_the_third_identical_rewrite_of_the_same_file(monkeypatch):
    """Bug real de v6: el modelo reescribió sneaky_sword.json con contenido
    BYTE-IDÉNTICO 14 veces seguidas sin ningún freno -- Opción B
    (meta-observación) lo detecta, pero solo después de que la sesión termina.
    Este guardrail corre el mismo criterio EN VIVO (ver
    `_live_identical_rewrite_loop_error`, umbral 3): la 3ra escritura
    idéntica seguida al mismo archivo se bloquea antes de ejecutarse."""
    search_call = _fake_tool_call("call_0", "obsidian_search_notes", {"query": "x"})
    write_1 = _fake_tool_call("call_1", "fs_write_file", {"path": "a.json", "content": "{}"})
    write_2 = _fake_tool_call("call_2", "fs_write_file", {"path": "a.json", "content": "{}"})
    write_3 = _fake_tool_call("call_3", "fs_write_file", {"path": "a.json", "content": "{}"})
    responses = [
        _fake_response(tool_calls=[search_call]),
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[write_2]),
        _fake_response(tool_calls=[write_3]),  # la 3ra idéntica seguida -- debe bloquearse
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    _, _, tool_log = await run_agent("creá un archivo", conversation_id="test-live-loop-1")

    assert calls_made == ["obsidian_search_notes", "fs_write_file", "fs_write_file"]  # la 3ra nunca llegó a call_tool
    write_entries = [e for e in tool_log if e["tool"] == "fs_write_file"]
    assert len(write_entries) == 3
    assert write_entries[0]["result"] == {"ok": True}
    assert write_entries[1]["result"] == {"ok": True}
    assert "error" in write_entries[2]["result"]
    assert "loop de reescritura idéntica" in write_entries[2]["result"]["error"]


@pytest.mark.anyio
async def test_run_agent_does_not_block_writes_with_different_content(monkeypatch):
    """Caso normal: reescribir el mismo archivo varias veces con contenido
    REALMENTE distinto cada vez (una edición real, no un loop) nunca debe
    activar este guardrail."""
    search_call = _fake_tool_call("call_0", "obsidian_search_notes", {"query": "x"})
    write_1 = _fake_tool_call("call_1", "fs_write_file", {"path": "a.py", "content": "v1"})
    write_2 = _fake_tool_call("call_2", "fs_write_file", {"path": "a.py", "content": "v2"})
    write_3 = _fake_tool_call("call_3", "fs_write_file", {"path": "a.py", "content": "v3"})
    responses = [
        _fake_response(tool_calls=[search_call]),
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[write_2]),
        _fake_response(tool_calls=[write_3]),
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("editá un archivo tres veces", conversation_id="test-live-loop-2")

    assert calls_made == ["obsidian_search_notes", "fs_write_file", "fs_write_file", "fs_write_file"]


@pytest.mark.anyio
async def test_run_agent_does_not_block_identical_content_written_to_different_files(monkeypatch):
    """Mismo contenido, archivos DISTINTOS (ej. dos configs iguales a
    propósito) -- no es un loop, no debe bloquearse."""
    search_call = _fake_tool_call("call_0", "obsidian_search_notes", {"query": "x"})
    write_1 = _fake_tool_call("call_1", "fs_write_file", {"path": "a.json", "content": "{}"})
    write_2 = _fake_tool_call("call_2", "fs_write_file", {"path": "b.json", "content": "{}"})
    write_3 = _fake_tool_call("call_3", "fs_write_file", {"path": "c.json", "content": "{}"})
    responses = [
        _fake_response(tool_calls=[search_call]),
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[write_2]),
        _fake_response(tool_calls=[write_3]),
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("creá tres configs iguales", conversation_id="test-live-loop-3")

    assert calls_made == ["obsidian_search_notes", "fs_write_file", "fs_write_file", "fs_write_file"]


@pytest.mark.anyio
async def test_run_agent_reblocks_fs_write_file_after_a_real_build_failure(monkeypatch):
    """Bug real 2026-08-10, encontrado en el test v4 del mod de Fabric: se consultó
    Obsidian una sola vez al principio (sobre StatusEffect), nunca se volvió a
    consultar nada sobre cómo detectar un golpe (AttackEntityCallback) a pesar de
    que el build después falló, y el modelo terminó inventando una mecánica
    equivocada en vez de darse cuenta de que le faltaba información puntual sobre
    ESE problema. Acá se verifica el guardrail extendido: una vez que Obsidian ya
    se consultó una vez (pasa el gate inicial), si un pc_run_command de
    build/compilación después devuelve exit_code != 0, el SIGUIENTE fs_write_file
    se bloquea de nuevo hasta que se vuelva a consultar conocimiento (Obsidian o
    research_topic) DESPUÉS de ese fallo puntual -- no antes."""
    search_1 = _fake_tool_call("call_1", "obsidian_search_notes", {"query": "fabric mod structure"})
    write_1 = _fake_tool_call("call_2", "fs_write_file", {"path": "build.gradle", "content": "..."})
    run_fail = _fake_tool_call("call_3", "pc_run_command", {"command": "./gradlew build"})
    write_2 = _fake_tool_call("call_4", "fs_write_file", {"path": "Main.java", "content": "..."})
    search_2 = _fake_tool_call("call_5", "obsidian_search_notes", {"query": "gradlew build error"})
    write_3 = _fake_tool_call("call_6", "fs_write_file", {"path": "Main.java", "content": "fixed"})
    responses = [
        _fake_response(tool_calls=[search_1]),
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[run_fail]),
        _fake_response(tool_calls=[write_2]),  # debería bloquearse: hubo un fallo sin consultar después
        _fake_response(tool_calls=[search_2]),  # reacciona consultando conocimiento sobre el error
        _fake_response(tool_calls=[write_3]),  # ahora sí debería pasar
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        if name == "pc_run_command":
            return {"exit_code": 1, "stdout": "", "stderr": "gradlew.bat no reconocido"}
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent("creá un mod de Fabric", conversation_id="test-post-fail-gate-1")

    # call_tool nunca se llamó para el segundo fs_write_file (el bloqueado) --
    # solo aparece para el primero (antes del fallo) y el tercero (después de
    # volver a consultar).
    assert calls_made == ["obsidian_search_notes", "fs_write_file", "pc_run_command", "obsidian_search_notes", "fs_write_file"]
    assert tool_log[0]["tool"] == "obsidian_search_notes"
    assert tool_log[1]["tool"] == "fs_write_file" and tool_log[1]["result"] == {"ok": True}
    assert tool_log[2]["tool"] == "pc_run_command" and tool_log[2]["result"]["exit_code"] == 1
    assert tool_log[3]["tool"] == "fs_write_file"
    assert "error" in tool_log[3]["result"]
    assert "gradlew.bat no reconocido" in tool_log[3]["result"]["error"]  # el error real queda visible
    assert tool_log[4]["tool"] == "obsidian_search_notes"
    assert tool_log[5]["tool"] == "fs_write_file" and tool_log[5]["result"] == {"ok": True}


@pytest.mark.anyio
async def test_run_agent_does_not_reblock_fs_write_file_after_a_successful_build(monkeypatch):
    """Un pc_run_command que sale bien (exit_code=0) no tiene que activar el
    guardrail post-fallo -- solo los fallos reales cuentan."""
    search_1 = _fake_tool_call("call_1", "obsidian_search_notes", {"query": "fabric mod structure"})
    write_1 = _fake_tool_call("call_2", "fs_write_file", {"path": "build.gradle", "content": "..."})
    run_ok = _fake_tool_call("call_3", "pc_run_command", {"command": "./gradlew build"})
    write_2 = _fake_tool_call("call_4", "fs_write_file", {"path": "Main.java", "content": "..."})
    responses = [
        _fake_response(tool_calls=[search_1]),
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[run_ok]),
        _fake_response(tool_calls=[write_2]),
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        if name == "pc_run_command":
            return {"exit_code": 0, "stdout": "BUILD SUCCESSFUL", "stderr": ""}
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("creá un mod de Fabric", conversation_id="test-post-fail-gate-2")

    assert calls_made == ["obsidian_search_notes", "fs_write_file", "pc_run_command", "fs_write_file"]


@pytest.mark.anyio
async def test_run_agent_research_topic_also_satisfies_the_post_failure_gate(monkeypatch):
    """research_topic cuenta igual que obsidian_search_notes para reabrir el
    guardrail post-fallo -- es la vía de escape cuando Obsidian no tiene nada
    relevante sobre el error puntual."""
    search_1 = _fake_tool_call("call_1", "obsidian_search_notes", {"query": "fabric mod structure"})
    write_1 = _fake_tool_call("call_2", "fs_write_file", {"path": "build.gradle", "content": "..."})
    run_fail = _fake_tool_call("call_3", "pc_run_command", {"command": "./gradlew build"})
    write_blocked = _fake_tool_call("call_4", "fs_write_file", {"path": "Main.java", "content": "..."})
    research = _fake_tool_call("call_5", "research_topic", {"topic": "gradlew.bat missing wrapper fix"})
    write_ok = _fake_tool_call("call_6", "fs_write_file", {"path": "Main.java", "content": "fixed"})
    responses = [
        _fake_response(tool_calls=[search_1]),
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[run_fail]),
        _fake_response(tool_calls=[write_blocked]),
        _fake_response(tool_calls=[research]),
        _fake_response(tool_calls=[write_ok]),
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        if name == "pc_run_command":
            return {"exit_code": 1, "stdout": "", "stderr": "algo falló"}
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent("creá un mod de Fabric", conversation_id="test-post-fail-gate-3")

    assert tool_log[3]["tool"] == "fs_write_file"
    assert "error" in tool_log[3]["result"]  # bloqueado
    assert tool_log[4]["tool"] == "research_topic"
    assert tool_log[5]["tool"] == "fs_write_file" and tool_log[5]["result"] == {"ok": True}  # ya no bloqueado


@pytest.mark.anyio
async def test_run_agent_blocks_a_different_file_while_one_is_left_unretried(monkeypatch):
    """Bug real 2026-08-10 (test v5 del mod de Fabric): el guardrail de
    conocimiento bloqueó el primer fs_write_file (build.gradle), el modelo
    consultó Obsidian como se le pidió -- pero después de eso NUNCA volvió a
    intentar escribir build.gradle: se distrajo escribiendo otros archivos
    (clases Java, fabric.mod.json, assets) y el proyecto terminó sin
    build.gradle. Acá se verifica el guardrail nuevo: mientras haya un
    fs_write_file bloqueado sin reintento exitoso, cualquier fs_write_file a
    OTRO path se rechaza también (sin llegar a call_tool), hasta que se
    retome ESE archivo puntual."""
    write_gradle_1 = _fake_tool_call("call_1", "fs_write_file", {"path": "build.gradle", "content": "..."})
    search_1 = _fake_tool_call("call_2", "obsidian_search_notes", {"query": "fabric mod structure"})
    write_java_1 = _fake_tool_call("call_3", "fs_write_file", {"path": "Main.java", "content": "..."})
    write_gradle_2 = _fake_tool_call("call_4", "fs_write_file", {"path": "build.gradle", "content": "fixed"})
    write_java_2 = _fake_tool_call("call_5", "fs_write_file", {"path": "Main.java", "content": "..."})
    responses = [
        _fake_response(tool_calls=[write_gradle_1]),  # bloqueado: falta consultar Obsidian
        _fake_response(tool_calls=[search_1]),  # reacciona bien, consulta
        _fake_response(tool_calls=[write_java_1]),  # se distrae con OTRO archivo -- debería bloquearse
        _fake_response(tool_calls=[write_gradle_2]),  # retoma el archivo pendiente -- debería pasar
        _fake_response(tool_calls=[write_java_2]),  # ahora sí, ya no hay pendiente -- debería pasar
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(f"{name}:{args.get('path','')}")
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, tool_log = await run_agent("creá un mod de Fabric", conversation_id="test-abandoned-file-1")

    # call_tool NUNCA se llamó para Main.java la primera vez (index 2, bloqueado) --
    # solo aparece después de que build.gradle se reintentó con éxito.
    assert calls_made == [
        "obsidian_search_notes:",
        "fs_write_file:build.gradle",
        "fs_write_file:Main.java",
    ]
    assert tool_log[0]["tool"] == "fs_write_file" and "error" in tool_log[0]["result"]  # build.gradle, bloqueado
    assert tool_log[1]["tool"] == "obsidian_search_notes"
    assert tool_log[2]["tool"] == "fs_write_file" and tool_log[2]["arguments"]["path"] == "Main.java"
    assert "error" in tool_log[2]["result"]  # bloqueado por el archivo pendiente, no por falta de conocimiento
    assert "build.gradle" in tool_log[2]["result"]["error"]  # el mensaje nombra el archivo pendiente real
    assert tool_log[3]["tool"] == "fs_write_file" and tool_log[3]["arguments"]["path"] == "build.gradle"
    assert tool_log[3]["result"] == {"ok": True}  # el reintento del archivo correcto sí pasa
    assert tool_log[4]["tool"] == "fs_write_file" and tool_log[4]["arguments"]["path"] == "Main.java"
    assert tool_log[4]["result"] == {"ok": True}  # ya no queda nada pendiente
    assert reply == "listo"


@pytest.mark.anyio
async def test_run_agent_allows_retrying_the_same_pending_file_immediately(monkeypatch):
    """Caso normal: si el modelo reacciona bien y reintenta DIRECTO el mismo
    archivo que se bloqueó (sin distraerse con otro primero), no debería haber
    fricción extra más allá del guardrail de conocimiento ya validado."""
    write_1 = _fake_tool_call("call_1", "fs_write_file", {"path": "build.gradle", "content": "..."})
    search_1 = _fake_tool_call("call_2", "obsidian_search_notes", {"query": "fabric mod structure"})
    write_2 = _fake_tool_call("call_3", "fs_write_file", {"path": "build.gradle", "content": "fixed"})
    responses = [
        _fake_response(tool_calls=[write_1]),
        _fake_response(tool_calls=[search_1]),
        _fake_response(tool_calls=[write_2]),
        _fake_response(content="listo"),
    ]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("creá un mod de Fabric", conversation_id="test-abandoned-file-2")

    assert calls_made == ["obsidian_search_notes", "fs_write_file"]


def _blocked_result(error: str, blocked_reason: str | None = None) -> dict:
    result = {"error": error}
    if blocked_reason:
        result["blocked_reason"] = blocked_reason
    return result


def test_pending_blocked_write_paths_remembers_a_second_file_blocked_while_the_first_was_pending():
    """Bug real de v6 (encontrado por meta-observación/Opción B, corregido vía
    Opción C 2026-08-11 -- ver docs del piloto): SpadeMod.java se bloqueó
    porque fabric.mod.json seguía pendiente (blocked_reason='pending_retry'),
    y ese bloqueo se perdía apenas fabric.mod.json se reintentaba con éxito.
    La primera versión del fix (renombrar a set[str] sin más) NO alcanzaba --
    seguía excluyendo los rechazos 'pending_retry' de la cuenta. Esto prueba
    la versión corregida: B.java sigue pendiente después de que A.java se
    resuelve."""
    history = [
        {"role": "system", "content": "x"},
        {"role": "user", "content": "x"},
        {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "A.java"})}}]},
        {"role": "tool", "tool_call_id": "c1", "content": json.dumps(_blocked_result("consultá Obsidian primero"))},
        {"role": "assistant", "tool_calls": [{"id": "c2", "function": {"name": "obsidian_search_notes", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c2", "content": json.dumps({"ok": True})},
        {"role": "assistant", "tool_calls": [{"id": "c3", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "B.java"})}}]},
        {"role": "tool", "tool_call_id": "c3", "content": json.dumps(_blocked_result("pendiente A.java", blocked_reason="pending_retry"))},
        {"role": "assistant", "tool_calls": [{"id": "c4", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "A.java"})}}]},
        {"role": "tool", "tool_call_id": "c4", "content": json.dumps({"ok": True})},
    ]

    pending = _pending_blocked_write_paths(history)

    assert pending == {"B.java"}


def test_pending_blocked_write_paths_clears_once_every_pending_file_is_retried():
    history = [
        {"role": "system", "content": "x"},
        {"role": "user", "content": "x"},
        {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "A.java"})}}]},
        {"role": "tool", "tool_call_id": "c1", "content": json.dumps(_blocked_result("x"))},
        {"role": "assistant", "tool_calls": [{"id": "c2", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "B.java"})}}]},
        {"role": "tool", "tool_call_id": "c2", "content": json.dumps(_blocked_result("pendiente A.java", blocked_reason="pending_retry"))},
        {"role": "assistant", "tool_calls": [{"id": "c3", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "A.java"})}}]},
        {"role": "tool", "tool_call_id": "c3", "content": json.dumps({"ok": True})},
        {"role": "assistant", "tool_calls": [{"id": "c4", "function": {"name": "fs_write_file", "arguments": json.dumps({"path": "B.java"})}}]},
        {"role": "tool", "tool_call_id": "c4", "content": json.dumps({"ok": True})},
    ]

    assert _pending_blocked_write_paths(history) == set()


@pytest.mark.anyio
async def test_run_agent_still_blocks_a_third_file_when_a_second_pending_file_was_forgotten_before_the_fix(monkeypatch):
    """Reproduce la secuencia exacta de v6 a través de run_agent(): A se
    bloquea, se consulta Obsidian, B se bloquea (pending_retry, porque A
    sigue pendiente), A se reintenta con éxito -- y ACÁ es donde v6 fallaba:
    el modelo se iba a escribir C sin haber retomado B nunca. Con el fix
    real ya aplicado (piloto Opción C, 2026-08-11), intentar C debe seguir
    bloqueado citando B."""
    write_a1 = _fake_tool_call("call_1", "fs_write_file", {"path": "A.java", "content": "..."})
    search_1 = _fake_tool_call("call_2", "obsidian_search_notes", {"query": "x"})
    write_b1 = _fake_tool_call("call_3", "fs_write_file", {"path": "B.java", "content": "..."})
    write_a2 = _fake_tool_call("call_4", "fs_write_file", {"path": "A.java", "content": "fixed"})
    write_c1 = _fake_tool_call("call_5", "fs_write_file", {"path": "C.java", "content": "..."})
    responses = [
        _fake_response(tool_calls=[write_a1]),
        _fake_response(tool_calls=[search_1]),
        _fake_response(tool_calls=[write_b1]),
        _fake_response(tool_calls=[write_a2]),
        _fake_response(tool_calls=[write_c1]),  # v6: esto pasaba sin más; ahora debe bloquearse
        _fake_response(content="listo"),
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    _, _, tool_log = await run_agent("creá tres archivos", conversation_id="test-v6-regression")

    write_c_entry = next(e for e in tool_log if e["tool"] == "fs_write_file" and e["arguments"]["path"] == "C.java")
    assert "error" in write_c_entry["result"]
    assert "B.java" in write_c_entry["result"]["error"]


@pytest.mark.anyio
async def test_run_agent_audits_a_successful_fs_write_file_with_content_hashed_not_raw(monkeypatch):
    """El hook de auditoría agregado 2026-08-10 para `app/introspection/analyzer.py`
    (ver esa sesión: detectar el loop de reescritura idéntica y el archivo
    bloqueado-y-abandonado que se vieron en v6) tiene que loguear CADA tool call
    del agente con target="agent" y el conversation_id real -- y para
    fs_write_file, el contenido real nunca debe llegar a audit_log (solo su hash
    y longitud), para no inflar el log con código entero."""
    search_call = _fake_tool_call("call_1", "obsidian_search_notes", {"query": "Flask"})
    write_call = _fake_tool_call("call_2", "fs_write_file", {"path": "app.py", "content": "print('secreto')"})
    responses = [
        _fake_response(tool_calls=[search_call]),
        _fake_response(tool_calls=[write_call]),
        _fake_response(content="listo"),
    ]
    logged: list[dict] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        return {"ok": True}

    def fake_log_tool_call(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)
    monkeypatch.setattr(agent.audit_log, "log_tool_call", fake_log_tool_call)

    await run_agent("creá una app Flask", conversation_id="test-audit-hook-1")

    write_entries = [e for e in logged if e["tool"] == "fs_write_file"]
    assert len(write_entries) == 1
    entry = write_entries[0]
    assert entry["target"] == "agent"
    assert entry["conversation_id"] == "test-audit-hook-1"
    assert entry["error"] is None
    assert "content" not in entry["arguments"]
    assert entry["arguments"]["path"] == "app.py"
    assert entry["arguments"]["content_length"] == len("print('secreto')")
    assert "content_sha256" in entry["arguments"]
    assert entry["arguments"]["content_sha256"] != "print('secreto')"


@pytest.mark.anyio
async def test_run_agent_audits_a_blocked_fs_write_file_with_the_gate_error(monkeypatch):
    """El mismo hook, para el caso bloqueado: debe quedar `error` seteado (no
    `result`, mismo contrato que ya valida `test_audit_log.py`), con el
    conversation_id real -- es la señal que usa
    `analyzer._find_abandoned_blocked_writes` para saber que este path quedó
    pendiente."""
    write_call = _fake_tool_call("call_1", "fs_write_file", {"path": "app.py", "content": "print(1)"})
    responses = [
        _fake_response(tool_calls=[write_call]),  # se bloquea: nunca consultó Obsidian
        _fake_response(content="listo"),
    ]
    logged: list[dict] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    def fake_log_tool_call(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent.audit_log, "log_tool_call", fake_log_tool_call)

    await run_agent("creá una app Flask", conversation_id="test-audit-hook-2")

    write_entries = [e for e in logged if e["tool"] == "fs_write_file"]
    assert len(write_entries) == 1
    entry = write_entries[0]
    assert entry["target"] == "agent"
    assert entry["conversation_id"] == "test-audit-hook-2"
    assert entry["result"] is None
    assert "obsidian_search_notes" in entry["error"]


@pytest.fixture
def _self_target_env(tmp_path, monkeypatch):
    """Opción C (2026-08-11): apunta el guardrail de self-target a una raíz
    falsa en tmp_path, para poder probar el gate en run_agent() sin tocar el
    backend/ real."""
    fake_backend = tmp_path / "backend"
    (fake_backend / "app").mkdir(parents=True)
    (fake_backend / "app" / "agent.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(agent.selfrepair_gate, "JARVIS_OWN_SOURCE_ROOT", fake_backend)
    from app.selfrepair import store as selfrepair_store

    monkeypatch.setattr(selfrepair_store.settings, "selfrepair_dir", str(tmp_path / "selfrepair_data"))
    return fake_backend


@pytest.mark.anyio
async def test_run_agent_blocks_fs_write_file_on_self_target_unconditionally(_self_target_env, monkeypatch):
    write_call = _fake_tool_call(
        "call_1", "fs_write_file", {"path": str(_self_target_env / "app" / "agent.py"), "content": "def f():\n    return 2\n"}
    )
    responses = [_fake_response(tool_calls=[write_call]), _fake_response(content="listo")]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    _, _, tool_log = await run_agent("arreglá agent.py", conversation_id="test-self-target-1")

    assert calls_made == []  # nunca se llegó a ejecutar
    assert "fs_write_file" in tool_log[0]["result"]["error"]


@pytest.mark.anyio
async def test_run_agent_blocks_self_target_code_apply_fix_confirm_without_proposal_id(_self_target_env, monkeypatch):
    apply_call = _fake_tool_call(
        "call_1", "code_apply_fix",
        {
            "path": str(_self_target_env), "file": "app/agent.py",
            "old_snippet": "return 1", "new_snippet": "return 2",
            "commit_message": "fix: x", "confirm": True,
        },
    )
    responses = [_fake_response(tool_calls=[apply_call]), _fake_response(content="listo")]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"applied": True}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    _, _, tool_log = await run_agent("aplicá el fix, dale nomás", conversation_id="test-self-target-2")

    assert calls_made == []
    assert "proposal_id" in tool_log[0]["result"]["error"]


@pytest.mark.anyio
async def test_run_agent_allows_self_target_code_apply_fix_with_a_confirmed_matching_proposal(_self_target_env, monkeypatch):
    from app.selfrepair import gate as selfrepair_gate_module
    from app.selfrepair.models import SelfFixProposal
    from app.selfrepair import store as selfrepair_store

    proposal = SelfFixProposal(
        proposal_id="sf-deadbeef", file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        diff="...", commit_message="fix: x", rationale="bug real", status="proposed",
        created_at="2026-08-11T00:00:00Z",
    )
    selfrepair_store.save_proposal(proposal)

    apply_call = _fake_tool_call(
        "call_1", "code_apply_fix",
        {
            "path": str(_self_target_env), "file": "app/agent.py",
            "old_snippet": "return 1", "new_snippet": "return 2",
            "commit_message": "fix: x", "confirm": True,
        },
    )
    responses = [_fake_response(tool_calls=[apply_call]), _fake_response(content="listo")]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"applied": True, "committed": True, "commit_hash": "abc123"}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("confirmo sf-deadbeef, aplicalo", conversation_id="test-self-target-3")

    assert calls_made == ["code_apply_fix"]
    # la propuesta usada queda consumida -- no se puede reusar el mismo id
    assert selfrepair_store.load_proposal("sf-deadbeef").status == "applied"


@pytest.mark.anyio
async def test_run_agent_does_not_consume_the_proposal_if_the_apply_call_fails(_self_target_env, monkeypatch):
    from app.selfrepair.models import SelfFixProposal
    from app.selfrepair import store as selfrepair_store

    proposal = SelfFixProposal(
        proposal_id="sf-deadbeef", file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        diff="...", commit_message="fix: x", rationale="bug real", status="proposed",
        created_at="2026-08-11T00:00:00Z",
    )
    selfrepair_store.save_proposal(proposal)

    apply_call = _fake_tool_call(
        "call_1", "code_apply_fix",
        {
            "path": str(_self_target_env), "file": "app/agent.py",
            "old_snippet": "return 1", "new_snippet": "return 2",
            "commit_message": "fix: x", "confirm": True,
        },
    )
    responses = [_fake_response(tool_calls=[apply_call]), _fake_response(content="listo")]

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        raise RuntimeError("el snippet ya no matchea")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("confirmo sf-deadbeef, aplicalo", conversation_id="test-self-target-4")

    assert selfrepair_store.load_proposal("sf-deadbeef").status == "proposed"


@pytest.mark.anyio
async def test_run_agent_never_blocks_a_self_target_dry_run_proposal(_self_target_env, monkeypatch):
    """code_apply_fix con confirm=false (el paso de proponer) nunca debe
    pasar por el gate de self-target -- si no, no habría forma de generar
    una propuesta en primer lugar."""
    dry_run_call = _fake_tool_call(
        "call_1", "code_apply_fix",
        {
            "path": str(_self_target_env), "file": "app/agent.py",
            "old_snippet": "return 1", "new_snippet": "return 2",
            "commit_message": "fix: x", "confirm": False,
        },
    )
    responses = [_fake_response(tool_calls=[dry_run_call]), _fake_response(content="listo")]
    calls_made: list[str] = []

    async def fake_create(**kwargs):
        return responses.pop(0)

    async def fake_call_tool(name, args):
        calls_made.append(name)
        return {"applied": False, "diff": "..."}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    await run_agent("mostrame el diff", conversation_id="test-self-target-5")

    assert calls_made == ["code_apply_fix"]
