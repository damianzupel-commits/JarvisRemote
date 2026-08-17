"""Tests de app/selfrepair/propose.py -- propose_fix nunca escribe nada real
(dry-run siempre), guarda la propuesta en el store, y si viene de una nota de
diagnóstico se le adjunta el diff -- todo verificable contra un repo git real
en tmp_path (mismo criterio que test_codeedit_fixer.py: lo que importa acá es
que el archivo real NO cambió, no que se llamó a una función mockeada)."""

from __future__ import annotations

import pytest

from app.obsidian import embeddings, vault
from app.selfrepair import gate, propose, store


@pytest.fixture(autouse=True)
def _tmp_env(tmp_path, monkeypatch):
    fake_backend = tmp_path / "backend"
    (fake_backend / "app").mkdir(parents=True)
    (fake_backend / "app" / "agent.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(gate, "JARVIS_OWN_SOURCE_ROOT", fake_backend)
    monkeypatch.setattr(store.settings, "selfrepair_dir", str(tmp_path / "selfrepair_data"))
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return fake_backend


def test_propose_fix_never_writes_the_real_file(_tmp_env):
    propose.propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="bug real", commit_message="fix: x",
    )

    assert (_tmp_env / "app" / "agent.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"


def test_propose_fix_returns_a_real_diff_and_a_proposal_id(_tmp_env):
    proposal = propose.propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="bug real", commit_message="fix: x",
    )

    assert proposal.proposal_id.startswith("sf-")
    assert "-    return 1" in proposal.diff
    assert "+    return 2" in proposal.diff
    assert proposal.status == "proposed"


def test_propose_fix_persists_the_proposal_in_the_store(_tmp_env):
    proposal = propose.propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="bug real", commit_message="fix: x",
    )

    loaded = store.load_proposal(proposal.proposal_id)
    assert loaded is not None
    assert loaded.old_snippet == "return 1"
    assert loaded.new_snippet == "return 2"


def test_propose_fix_raises_when_the_snippet_does_not_match(_tmp_env):
    with pytest.raises(Exception):
        propose.propose_fix(
            file="app/agent.py", old_snippet="return 999", new_snippet="return 2",
            rationale="x", commit_message="fix: x",
        )


def test_propose_fix_attaches_the_diff_to_an_existing_diagnostic_note(_tmp_env):
    note = vault.save_note(
        title="autodiagnóstico: algo raro", content="Contenido original de la nota.",
        author="jarvis", tags=["autodiagnostico"],
    )

    proposal = propose.propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="arregla el bug X", commit_message="fix: x", note_id=note.id,
    )

    updated_note = vault.read_note(note.id)
    assert "Contenido original de la nota." in updated_note.content
    assert proposal.proposal_id in updated_note.content
    assert "arregla el bug X" in updated_note.content
    assert "+    return 2" in updated_note.content
    assert updated_note.author == "jarvis"  # metadata original preservada
    assert "autodiagnostico" in updated_note.tags


def test_propose_fix_without_note_id_does_not_touch_the_vault(_tmp_env):
    propose.propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="x", commit_message="fix: x",
    )

    assert vault.list_notes() == []


def test_propose_fix_tolerates_a_note_id_that_does_not_exist(_tmp_env):
    # No debe lanzar -- la propuesta igual se guarda en el store, solo no
    # se puede adjuntar a una nota que no existe.
    proposal = propose.propose_fix(
        file="app/agent.py", old_snippet="return 1", new_snippet="return 2",
        rationale="x", commit_message="fix: x", note_id="jarvis/no-existe",
    )
    assert store.load_proposal(proposal.proposal_id) is not None
