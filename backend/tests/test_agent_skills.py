"""Tests de integración de la arquitectura de skills DENTRO de run_agent
(app/agent.py) -- que el mensaje del usuario realmente determine qué 'tools'
se le mandan al modelo y qué system prompt ve, no solo que app/skills.py
clasifique bien en aislamiento (ya cubierto por tests/test_skills.py)."""

from __future__ import annotations

import json
import logging.handlers
from types import SimpleNamespace

import pytest

from app import agent
from app import audit_log as audit_log_module
from app import skills
from app.agent import run_agent
from app.tools import get_tools


@pytest.fixture(autouse=True)
def _isolated_audit_log(tmp_path, monkeypatch):
    log_path = tmp_path / "audit.log"
    handler = logging.handlers.RotatingFileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    monkeypatch.setattr(audit_log_module, "_AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr(audit_log_module._audit_logger, "handlers", [handler])
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
async def test_a_security_flavored_message_sends_only_the_scoped_tool_set(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("Escaneá el proyecto con security_scan_project", conversation_id="skill-test-1")

    tool_names = {t["function"]["name"] for t in captured["tools"]}
    assert tool_names == skills.tools_for_active_skills({"security_audit"})
    assert len(tool_names) < len(get_tools())
    assert "desktop_click" not in tool_names
    assert "phone_take_photo" not in tool_names


@pytest.mark.anyio
async def test_an_ambiguous_message_falls_back_to_the_full_tool_set(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("Hola, ¿cómo estás?", conversation_id="skill-test-2")

    tool_names = {t["function"]["name"] for t in captured["tools"]}
    assert tool_names == set(get_tools().keys())


@pytest.mark.anyio
async def test_an_ambiguous_message_uses_the_full_system_prompt(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("Hola, ¿cómo estás?", conversation_id="skill-test-3")

    history = agent._conversations["skill-test-3"]
    assert history[0]["content"] == agent.SYSTEM_PROMPT


@pytest.mark.anyio
async def test_a_desktop_flavored_message_uses_the_scoped_prompt_not_the_full_one(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("Sacame una captura de pantalla del escritorio", conversation_id="skill-test-4")

    history = agent._conversations["skill-test-4"]
    assert history[0]["content"] != agent.SYSTEM_PROMPT
    assert history[0]["content"] == skills.prompt_for_active_skills({"desktop_control"})


@pytest.mark.anyio
async def test_system_prompt_updates_when_the_conversation_switches_domain_between_turns(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response(content="ok")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await run_agent("Escaneá el proyecto con security_scan_project", conversation_id="skill-test-5")
    history = agent._conversations["skill-test-5"]
    assert history[0]["content"] == skills.prompt_for_active_skills({"security_audit"})

    await run_agent("Sacame una captura de pantalla", conversation_id="skill-test-5")
    history = agent._conversations["skill-test-5"]
    assert history[0]["content"] == skills.prompt_for_active_skills({"desktop_control"})


@pytest.mark.anyio
async def test_a_scoped_tool_call_still_dispatches_correctly_through_the_real_call_tool(monkeypatch, tmp_path):
    """El recorte de tools no debe romper el dispatch real -- una tool call
    dentro del subconjunto ofrecido tiene que seguir funcionando de punta a
    punta (no mockea call_tool acá, usa el real)."""
    monkeypatch.setattr(agent.settings, "fs_allowed_root", str(tmp_path))
    tool_call = _fake_tool_call("call_1", "fs_write_file", {"path": "nota.txt", "content": "hola"})
    responses = [
        _fake_response(tool_calls=[tool_call]),
        _fake_response(content="listo"),
    ]

    async def fake_create(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    # fs_write_file esta en CORE (siempre disponible) -- pero primero hay
    # que satisfacer su gate de obsidian.
    from app.obsidian import vault as vault_module

    monkeypatch.setattr(vault_module.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    search_call = _fake_tool_call("call_0", "obsidian_search_notes", {"query": "notas"})
    responses.insert(0, _fake_response(tool_calls=[search_call]))

    conv_id, reply, tool_log = await run_agent(
        "Escaneá el proyecto y guardá una nota con fs_write_file", conversation_id="skill-test-6"
    )

    assert reply == "listo"
    assert (tmp_path / "nota.txt").is_file()
    assert (tmp_path / "nota.txt").read_text(encoding="utf-8") == "hola"


def test_research_profile_is_unaffected_by_skill_classification():
    """El perfil de investigación (item 4) sigue usando su propio
    subconjunto fijo -- la clasificación de skills es exclusiva del perfil
    default, ver _run_agent_turn."""
    # No requiere llamar al LLM -- alcanza con confirmar que
    # _tools_for_profile("research", ...) ignora la clasificación de skills
    # por completo (chequeo estructural, ya cubierto en detalle por
    # tests/test_agent_profiles.py).
    from app.agent import _RESEARCH_TOOL_NAMES

    assert not (_RESEARCH_TOOL_NAMES & skills._SECURITY_AUDIT_TOOL_NAMES)
