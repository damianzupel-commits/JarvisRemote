"""Tests de los reintentos con backoff del loop del agente (Mejora 2,
2026-08-19): reintentar SOLO fallas transitorias de red al llamar al LLM, con
backoff exponencial, sin enmascarar errores reales ni caer en loops infinitos.
Ver app/agent.py::_create_chat_completion / _is_transient_llm_error.

Todo mockeado: se reemplaza client.chat.completions.create y asyncio.sleep,
no hay red real ni esperas reales."""

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app import agent


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """El backoff no debe dormir de verdad en los tests -- se registra cuánto
    se 'durmió' para poder assertar el backoff sin ralentizar la suite."""
    slept: list[float] = []

    async def fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr(agent.asyncio, "sleep", fake_sleep)
    return slept


@pytest.fixture(autouse=True)
def _fast_retry_config(monkeypatch):
    monkeypatch.setattr(agent.settings, "llm_retry_max_attempts", 3)
    monkeypatch.setattr(agent.settings, "llm_retry_base_delay_seconds", 1.0)
    monkeypatch.setattr(agent.settings, "llm_retry_max_delay_seconds", 30.0)
    monkeypatch.setattr(agent.settings, "llm_retry_on_timeout", False)


def _conn_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://127.0.0.1:11434/v1/chat"))


def _timeout_error() -> APITimeoutError:
    return APITimeoutError(request=httpx.Request("POST", "http://127.0.0.1:11434/v1/chat"))


def _status_error() -> APIStatusError:
    req = httpx.Request("POST", "http://127.0.0.1:11434/v1/chat")
    resp = httpx.Response(400, request=req)
    return APIStatusError("bad request", response=resp, body=None)


# --- Clasificación transitorio vs permanente --------------------------------


def test_connection_error_is_transient():
    assert agent._is_transient_llm_error(_conn_error()) is True


def test_status_error_is_not_transient():
    assert agent._is_transient_llm_error(_status_error()) is False


def test_value_error_is_not_transient():
    assert agent._is_transient_llm_error(ValueError("respuesta inválida")) is False


def test_timeout_not_transient_by_default(monkeypatch):
    monkeypatch.setattr(agent.settings, "llm_retry_on_timeout", False)
    assert agent._is_transient_llm_error(_timeout_error()) is False


def test_timeout_transient_when_opted_in(monkeypatch):
    monkeypatch.setattr(agent.settings, "llm_retry_on_timeout", True)
    assert agent._is_transient_llm_error(_timeout_error()) is True


# --- Comportamiento de _create_chat_completion ------------------------------


@pytest.mark.anyio
async def test_transient_failure_is_retried_then_succeeds(monkeypatch, _no_real_sleep):
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _conn_error()
        return "OK"

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    result = await agent._create_chat_completion(model="m", messages=[])

    assert result == "OK"
    assert calls["n"] == 2  # falló una vez, reintentó y funcionó
    assert _no_real_sleep == [1.0]  # un backoff, base * 2**0


@pytest.mark.anyio
async def test_permanent_error_is_not_retried(monkeypatch, _no_real_sleep):
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        raise _status_error()

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with pytest.raises(APIStatusError):
        await agent._create_chat_completion(model="m", messages=[])

    assert calls["n"] == 1  # NO se reintentó un error permanente
    assert _no_real_sleep == []  # no hubo backoff


@pytest.mark.anyio
async def test_transient_failure_exhausts_attempts_and_raises_no_infinite_loop(
    monkeypatch, _no_real_sleep
):
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        raise _conn_error()

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with pytest.raises(APIConnectionError):
        await agent._create_chat_completion(model="m", messages=[])

    # Exactamente max_attempts intentos, ni uno más (no loop infinito).
    assert calls["n"] == 3
    # Backoff exponencial entre intentos: 1s, 2s (2 backoffs para 3 intentos).
    assert _no_real_sleep == [1.0, 2.0]


@pytest.mark.anyio
async def test_backoff_is_capped_at_max_delay(monkeypatch, _no_real_sleep):
    monkeypatch.setattr(agent.settings, "llm_retry_max_attempts", 5)
    monkeypatch.setattr(agent.settings, "llm_retry_base_delay_seconds", 10.0)
    monkeypatch.setattr(agent.settings, "llm_retry_max_delay_seconds", 25.0)

    async def fake_create(**kwargs):
        raise _conn_error()

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with pytest.raises(APIConnectionError):
        await agent._create_chat_completion(model="m", messages=[])

    # 10, 20, min(40,25)=25, min(80,25)=25 -> topeado en 25.
    assert _no_real_sleep == [10.0, 20.0, 25.0, 25.0]


@pytest.mark.anyio
async def test_timeout_retried_only_when_opted_in(monkeypatch, _no_real_sleep):
    monkeypatch.setattr(agent.settings, "llm_retry_on_timeout", True)
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _timeout_error()
        return "OK"

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    result = await agent._create_chat_completion(model="m", messages=[])
    assert result == "OK"
    assert calls["n"] == 2
