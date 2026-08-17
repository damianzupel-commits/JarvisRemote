"""Tests de la tool `selfrepair_propose_fix` (app/tools/selfrepair.py) -- la
lógica real ya se prueba en test_selfrepair_propose.py; acá se prueba la capa
de tool (forma del resultado, auditoría)."""

from __future__ import annotations

import pytest

from app import audit_log
from app.selfrepair import gate, store
from app.tools import selfrepair as selfrepair_tool


@pytest.fixture(autouse=True)
def _tmp_env(tmp_path, monkeypatch):
    fake_backend = tmp_path / "backend"
    (fake_backend / "app").mkdir(parents=True)
    (fake_backend / "app" / "agent.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(gate, "JARVIS_OWN_SOURCE_ROOT", fake_backend)
    monkeypatch.setattr(store.settings, "selfrepair_dir", str(tmp_path / "selfrepair_data"))
    return fake_backend


def test_selfrepair_propose_fix_returns_proposal_id_and_diff_never_applies(_tmp_env, monkeypatch):
    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kw: logged.append(kw))

    result = selfrepair_tool.selfrepair_propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="bug real", commit_message="fix: x",
    )

    assert result["proposal_id"].startswith("sf-")
    assert "return 2" in result["diff"]
    assert (_tmp_env / "app" / "agent.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"
    assert len(logged) == 1
    assert logged[0]["tool"] == "selfrepair_propose_fix"


def test_selfrepair_propose_fix_audits_and_reraises_on_error(_tmp_env, monkeypatch):
    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kw: logged.append(kw))

    with pytest.raises(Exception):
        selfrepair_tool.selfrepair_propose_fix(
            file="app/agent.py", old_snippet="no existe esto", new_snippet="x",
            rationale="x", commit_message="fix: x",
        )

    assert len(logged) == 1
    assert "error" in logged[0]
