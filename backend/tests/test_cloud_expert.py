"""Tests de cloud_expert_code/cloud_expert_marketing (app/tools/cloud_expert.py).
El cliente real de Gemini se mockea a propósito (sin API key real no hay
forma de pegarle de verdad, y no queremos que la suite dependa de una llamada
de red real ni de tener GOOGLE_AI_API_KEY seteada) -- lo que se prueba acá es
la lógica propia: el gate de configuración, el gate de sensibilidad
(confirm_non_sensitive), que 'task' es lo único que sale hacia el cliente
mockeado, y el audit log."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import audit_log
from app.tools import cloud_expert


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(cloud_expert.settings, "google_ai_api_key", "fake-key-para-tests")
    monkeypatch.setattr(cloud_expert.settings, "google_ai_model", "gemini-2.5-flash")


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.anyio
async def test_cloud_expert_code_requires_api_key(monkeypatch):
    monkeypatch.setattr(cloud_expert.settings, "google_ai_api_key", "")

    with pytest.raises(cloud_expert.CloudExpertNotConfigured):
        await cloud_expert.cloud_expert_code("crea un mod de fabric", confirm_non_sensitive=True)


@pytest.mark.anyio
async def test_cloud_expert_marketing_requires_api_key(monkeypatch):
    monkeypatch.setattr(cloud_expert.settings, "google_ai_api_key", "")

    with pytest.raises(cloud_expert.CloudExpertNotConfigured):
        await cloud_expert.cloud_expert_marketing("escribi un post", confirm_non_sensitive=True)


@pytest.mark.anyio
async def test_cloud_expert_code_requires_explicit_confirm_non_sensitive():
    with pytest.raises(cloud_expert.CloudExpertSensitiveDataBlocked):
        await cloud_expert.cloud_expert_code("crea un mod de fabric", confirm_non_sensitive=False)


@pytest.mark.anyio
async def test_cloud_expert_marketing_requires_explicit_confirm_non_sensitive():
    with pytest.raises(cloud_expert.CloudExpertSensitiveDataBlocked):
        await cloud_expert.cloud_expert_marketing("escribi un post", confirm_non_sensitive=False)


@pytest.mark.anyio
async def test_cloud_expert_code_default_confirm_is_false(monkeypatch):
    # El parametro tiene default False -- llamarlo sin pasarlo explicito
    # tiene que bloquearse igual, nunca asumir que esta confirmado.
    with pytest.raises(cloud_expert.CloudExpertSensitiveDataBlocked):
        await cloud_expert.cloud_expert_code("crea un mod de fabric")


@pytest.mark.anyio
async def test_cloud_expert_code_sends_only_the_task_text(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response("def hello(): pass")

    monkeypatch.setattr(cloud_expert.client.chat.completions, "create", fake_create)

    result = await cloud_expert.cloud_expert_code(
        "crea una funcion hello world en python", confirm_non_sensitive=True
    )

    assert result["draft"] == "def hello(): pass"
    assert result["model"] == "gemini-2.5-flash"
    user_msg = captured["messages"][1]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "crea una funcion hello world en python"
    assert captured["model"] == "gemini-2.5-flash"
    assert captured["max_tokens"] == cloud_expert._MAX_OUTPUT_TOKENS


@pytest.mark.anyio
async def test_cloud_expert_code_and_marketing_use_different_system_prompts(monkeypatch):
    captured = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        return _fake_response("borrador")

    monkeypatch.setattr(cloud_expert.client.chat.completions, "create", fake_create)

    await cloud_expert.cloud_expert_code("tarea de codigo", confirm_non_sensitive=True)
    await cloud_expert.cloud_expert_marketing("tarea de marketing", confirm_non_sensitive=True)

    code_system = captured[0]["messages"][0]["content"]
    marketing_system = captured[1]["messages"][0]["content"]
    assert code_system != marketing_system
    assert "código" in code_system
    assert "marketing" in marketing_system


@pytest.mark.anyio
async def test_cloud_expert_marketing_returns_draft(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response("Post real para r/LocalLLaMA sobre Jarvis.")

    monkeypatch.setattr(cloud_expert.client.chat.completions, "create", fake_create)

    result = await cloud_expert.cloud_expert_marketing(
        "escribi un post anunciando Jarvis", confirm_non_sensitive=True
    )

    assert "r/LocalLLaMA" in result["draft"]


@pytest.mark.anyio
async def test_cloud_expert_code_propagates_and_logs_client_errors(monkeypatch):
    async def fake_create(**kwargs):
        raise RuntimeError("rate limit excedido")

    monkeypatch.setattr(cloud_expert.client.chat.completions, "create", fake_create)

    with pytest.raises(RuntimeError, match="rate limit excedido"):
        await cloud_expert.cloud_expert_code("tarea", confirm_non_sensitive=True)

    entries = audit_log.read_entries(target="cloud", tool="cloud_expert_code")
    assert entries
    assert entries[-1]["ok"] is False
    assert "rate limit excedido" in entries[-1]["error"]


@pytest.mark.anyio
async def test_cloud_expert_code_logs_success_to_audit_log(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response("codigo real")

    monkeypatch.setattr(cloud_expert.client.chat.completions, "create", fake_create)

    await cloud_expert.cloud_expert_code("tarea auditada", confirm_non_sensitive=True)

    entries = audit_log.read_entries(target="cloud", tool="cloud_expert_code")
    assert entries
    last = entries[-1]
    assert last["ok"] is True
    assert last["arguments"]["task"] == "tarea auditada"
    assert last["arguments"]["confirm_non_sensitive"] is True


def test_cloud_expert_tools_are_registered():
    from app.tools import get_tools

    tools = get_tools()
    assert "cloud_expert_code" in tools
    assert "cloud_expert_marketing" in tools
    assert tools["cloud_expert_code"].target == "pc"
