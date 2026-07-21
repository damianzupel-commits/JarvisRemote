from app.agent import _trim_history


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
