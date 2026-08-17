"""Tests del perfil de investigación científica (ver app/agent.py +
app/obsidian/profile.py) -- ítem 4 de la cola, agregado 2026-08-12: comando
explícito de cambio de perfil, subconjunto de tools, system prompt propio, y
que el vault/directorio de trabajo quedan de verdad separados del perfil
default (verificado escribiendo notas reales, no solo revisando la
configuración)."""

from __future__ import annotations

import json
import logging.handlers
from types import SimpleNamespace

import pytest

from app import agent
from app import audit_log as audit_log_module
from app.agent import run_agent


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    log_path = tmp_path / "audit.log"
    handler = logging.handlers.RotatingFileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    monkeypatch.setattr(audit_log_module, "_AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr(audit_log_module._audit_logger, "handlers", [handler])

    # Nunca tocar el vault/directorio reales de Damian durante los tests.
    monkeypatch.setattr(agent.settings, "research_vault_path", str(tmp_path / "research_vault"))
    monkeypatch.setattr(agent.settings, "research_embeddings_path", str(tmp_path / "research_embeddings.json"))
    monkeypatch.setattr(agent.settings, "research_working_dir", str(tmp_path / "Investigacion"))

    yield
    handler.close()
    agent._conversation_profiles.clear()


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
async def test_modo_investigacion_switches_profile_without_calling_the_llm(monkeypatch):
    llm_called = False

    async def fake_create(**kwargs):
        nonlocal llm_called
        llm_called = True
        return _fake_response(content="no debería llamarse")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    conv_id, reply, tool_log = await run_agent("/modo investigacion", conversation_id="test-profile-1")

    assert llm_called is False
    assert tool_log == []
    assert agent._conversation_profiles[conv_id] == "research"
    assert "investigación" in reply.lower()


@pytest.mark.anyio
async def test_modo_seguridad_switches_back_to_default(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response(content="no debería llamarse")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("/modo investigacion", conversation_id="test-profile-2")
    conv_id, reply, _ = await run_agent("/modo seguridad", conversation_id="test-profile-2")

    assert agent._conversation_profiles[conv_id] == "default"
    assert "default" in reply.lower()


@pytest.mark.anyio
async def test_modo_investigacion_creates_the_research_working_dir(tmp_path):
    await run_agent("/modo investigacion", conversation_id="test-profile-3")

    assert (tmp_path / "Investigacion").is_dir()


@pytest.mark.anyio
async def test_research_profile_uses_the_research_system_prompt(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("/modo investigacion", conversation_id="test-profile-4")
    await run_agent("hola", conversation_id="test-profile-4")

    history = agent._conversations["test-profile-4"]
    assert history[0]["role"] == "system"
    assert history[0]["content"] == agent.RESEARCH_SYSTEM_PROMPT
    assert "biotecnología" in history[0]["content"]


@pytest.mark.anyio
async def test_default_profile_still_uses_the_default_system_prompt(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("hola, sin cambiar de perfil", conversation_id="test-profile-5")

    history = agent._conversations["test-profile-5"]
    assert history[0]["content"] == agent.SYSTEM_PROMPT


@pytest.mark.anyio
async def test_research_profile_only_exposes_the_research_tool_subset(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("/modo investigacion", conversation_id="test-profile-6")
    await run_agent("buscá algo", conversation_id="test-profile-6")

    tool_names = {t["function"]["name"] for t in captured["tools"]}
    assert tool_names == agent._RESEARCH_TOOL_NAMES
    assert "security_scan_project" not in tool_names
    assert "pc_run_command" not in tool_names
    assert "opencode_run_task" not in tool_names


@pytest.mark.anyio
async def test_default_profile_still_exposes_the_full_tool_set(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("hola", conversation_id="test-profile-7")

    tool_names = {t["function"]["name"] for t in captured["tools"]}
    assert "security_scan_project" in tool_names
    assert "pc_run_command" in tool_names


@pytest.mark.anyio
async def test_research_profile_routes_a_real_obsidian_save_note_call_to_the_research_vault(tmp_path, monkeypatch):
    """No mockea call_tool -- usa el call_tool REAL (app.tools.call_tool) para
    que el override de perfil (app/obsidian/profile.py) se ejercite de
    verdad de punta a punta, igual que en producción."""
    tool_call = _fake_tool_call(
        "call_1", "obsidian_save_note", {"title": "Hallazgo real", "content": "contenido de prueba"}
    )
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="Nota guardada."),
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("/modo investigacion", conversation_id="test-profile-8")
    await run_agent("guardá esta nota", conversation_id="test-profile-8")

    research_notes = list((tmp_path / "research_vault" / "jarvis").glob("*.md"))
    assert len(research_notes) == 1
    assert "contenido de prueba" in research_notes[0].read_text(encoding="utf-8")

    # El vault de seguridad/default (obsidian_vault_path real del proyecto)
    # no tiene que haber recibido nada de esta llamada -- el override de
    # perfil solo estaba activo durante ESTE turno.
    from app.obsidian import vault as vault_module

    assert not (tmp_path / "obsidian_vault").exists()
    assert vault_module.settings.obsidian_vault_path != str(tmp_path / "research_vault")
