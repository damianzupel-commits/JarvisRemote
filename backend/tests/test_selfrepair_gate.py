"""Tests del guardrail de self-target (app/selfrepair/gate.py) -- el gate más
severo del proyecto (bloquea escrituras al propio código de Jarvis), así que
se prueba con detalle: fs_write_file siempre bloqueado sin excepción,
code_apply_fix dry-run nunca bloqueado, confirm=true solo pasa con un
proposal_id real que matchea file+old_snippet+new_snippet exacto, y el
consumo de la propuesta después de aplicarla."""

from __future__ import annotations

import pytest

from app.selfrepair import gate, store
from app.selfrepair.models import SelfFixProposal


@pytest.fixture(autouse=True)
def _tmp_root(tmp_path, monkeypatch):
    fake_backend = tmp_path / "backend"
    (fake_backend / "app").mkdir(parents=True)
    (fake_backend / "app" / "agent.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(gate, "JARVIS_OWN_SOURCE_ROOT", fake_backend)
    monkeypatch.setattr(store.settings, "selfrepair_dir", str(tmp_path / "selfrepair_data"))
    return fake_backend


def _save_proposal(root, **overrides) -> SelfFixProposal:
    defaults = dict(
        proposal_id="sf-aaaaaaaa", file="app/agent.py", old_snippet="x = 1", new_snippet="x = 2",
        diff="...", commit_message="fix: x", rationale="porque si", status="proposed",
        created_at="2026-08-11T00:00:00Z",
    )
    defaults.update(overrides)
    proposal = SelfFixProposal(**defaults)
    store.save_proposal(proposal)
    return proposal


# ---------------------------------------------------------------------------
# is_self_target / extract_confirmed_proposal_ids
# ---------------------------------------------------------------------------


def test_is_self_target_true_for_a_path_inside_backend(_tmp_root):
    assert gate.is_self_target(_tmp_root / "app" / "agent.py") is True


def test_is_self_target_false_for_a_path_outside_backend(tmp_path, _tmp_root):
    other = tmp_path / "some_other_project" / "app.py"
    assert gate.is_self_target(other) is False


def test_extract_confirmed_proposal_ids_finds_it_in_free_text():
    assert gate.extract_confirmed_proposal_ids("dale, confirmo sf-a3f9c1d2, aplicalo") == ["sf-a3f9c1d2"]


def test_extract_confirmed_proposal_ids_returns_empty_without_one():
    assert gate.extract_confirmed_proposal_ids("dale, aplicalo nomás") == []


def test_extract_confirmed_proposal_ids_ignores_malformed_ids():
    assert gate.extract_confirmed_proposal_ids("confirmo sf-123 (muy corto)") == []


def test_extract_confirmed_proposal_ids_finds_more_than_one():
    """Un fix real puede necesitar dos snippets del mismo archivo (ej. la
    definición de una función y su call site, lejos una de la otra) -- ambos
    proposal_id tienen que poder confirmarse en el mismo mensaje."""
    ids = gate.extract_confirmed_proposal_ids("confirmo sf-aaaaaaaa y sf-bbbbbbbb, aplicá los dos")
    assert ids == ["sf-aaaaaaaa", "sf-bbbbbbbb"]


# ---------------------------------------------------------------------------
# self_target_gate_error
# ---------------------------------------------------------------------------


def test_fs_write_file_on_self_target_is_always_blocked_even_with_a_valid_proposal(_tmp_root):
    _save_proposal(_tmp_root)
    args = {"path": str(_tmp_root / "app" / "agent.py"), "content": "x = 2"}

    error = gate.self_target_gate_error("fs_write_file", args, "confirmo sf-aaaaaaaa")

    assert error is not None
    assert "fs_write_file" in error


def test_fs_write_file_on_a_normal_project_is_never_blocked(_tmp_root, tmp_path):
    args = {"path": str(tmp_path / "other_project" / "app.py"), "content": "x = 2"}

    assert gate.self_target_gate_error("fs_write_file", args, "") is None


def test_code_apply_fix_dry_run_on_self_target_is_never_blocked(_tmp_root):
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": False}

    assert gate.self_target_gate_error("code_apply_fix", args, "") is None


def test_code_apply_fix_confirm_true_on_self_target_blocked_without_proposal_id(_tmp_root):
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args, "dale aplicalo")

    assert error is not None
    assert "proposal_id" in error


def test_code_apply_fix_confirm_true_on_self_target_allowed_with_matching_proposal(_tmp_root):
    _save_proposal(_tmp_root)
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args, "confirmo sf-aaaaaaaa, dale")

    assert error is None


def test_code_apply_fix_confirm_true_allowed_when_its_id_is_the_second_of_two_confirmed(_tmp_root):
    """Escenario real del piloto: dos proposals para el mismo archivo (la
    definición de una función y su call site), confirmados juntos en un solo
    mensaje -- el segundo tool call tiene que poder encontrar SU proposal_id
    aunque no sea el primero mencionado en el texto."""
    (_tmp_root / "app" / "other.py").write_text("y = 1\n", encoding="utf-8")
    _save_proposal(_tmp_root, proposal_id="sf-11111111", file="app/agent.py")
    _save_proposal(_tmp_root, proposal_id="sf-22222222", file="app/other.py", old_snippet="y = 1", new_snippet="y = 2")

    args_second = {"path": str(_tmp_root), "file": "app/other.py", "old_snippet": "y = 1", "new_snippet": "y = 2", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args_second, "confirmo sf-11111111 y sf-22222222, aplicá los dos")

    assert error is None


def test_code_apply_fix_confirm_true_blocked_when_proposal_id_does_not_exist(_tmp_root):
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args, "confirmo sf-ffffffff")

    assert error is not None


def test_code_apply_fix_confirm_true_blocked_when_snippet_does_not_match_the_proposal(_tmp_root):
    """El caso clave que motivó chequear old_snippet/new_snippet además del
    file: reusar un proposal_id ya aprobado para colar un cambio DISTINTO al
    mismo archivo."""
    _save_proposal(_tmp_root)
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 999_evil", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args, "confirmo sf-aaaaaaaa")

    assert error is not None


def test_code_apply_fix_confirm_true_blocked_when_file_does_not_match_the_proposal(_tmp_root):
    (_tmp_root / "app" / "other.py").write_text("x = 1\n", encoding="utf-8")
    _save_proposal(_tmp_root)  # propuesta es para app/agent.py
    args = {"path": str(_tmp_root), "file": "app/other.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args, "confirmo sf-aaaaaaaa")

    assert error is not None


def test_code_apply_fix_confirm_true_blocked_when_proposal_already_applied(_tmp_root):
    _save_proposal(_tmp_root, status="applied", applied_at="2026-08-11T01:00:00Z")
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    error = gate.self_target_gate_error("code_apply_fix", args, "confirmo sf-aaaaaaaa")

    assert error is not None


def test_code_apply_fix_on_a_normal_project_never_needs_a_proposal(_tmp_root, tmp_path):
    args = {"path": str(tmp_path / "other_project"), "file": "app.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    assert gate.self_target_gate_error("code_apply_fix", args, "") is None


def test_other_tools_are_never_gated(_tmp_root):
    assert gate.self_target_gate_error("obsidian_search_notes", {"query": "x"}, "") is None


# ---------------------------------------------------------------------------
# consume_proposal_if_applied
# ---------------------------------------------------------------------------


def test_consume_proposal_marks_it_applied_after_a_successful_self_fix(_tmp_root):
    _save_proposal(_tmp_root)
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    gate.consume_proposal_if_applied("code_apply_fix", args, "confirmo sf-aaaaaaaa", {"applied": True}, "2026-08-11T02:00:00Z")

    updated = store.load_proposal("sf-aaaaaaaa")
    assert updated.status == "applied"
    assert updated.applied_at == "2026-08-11T02:00:00Z"


def test_consume_proposal_does_nothing_when_the_call_failed(_tmp_root):
    _save_proposal(_tmp_root)
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    gate.consume_proposal_if_applied("code_apply_fix", args, "confirmo sf-aaaaaaaa", {"error": "algo salió mal"}, "2026-08-11T02:00:00Z")

    assert store.load_proposal("sf-aaaaaaaa").status == "proposed"


def test_consume_proposal_does_nothing_for_non_self_target_writes(_tmp_root, tmp_path):
    args = {"path": str(tmp_path / "other_project"), "file": "app.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}

    # no debe lanzar aunque no haya ninguna propuesta relacionada
    gate.consume_proposal_if_applied("code_apply_fix", args, "", {"applied": True}, "2026-08-11T02:00:00Z")


def test_a_second_apply_attempt_with_the_same_proposal_id_is_blocked_after_it_was_consumed(_tmp_root):
    """Cierra el hueco real que motivó esto: un proposal_id ya usado no debe
    poder reusarse para aplicar otra cosa (o lo mismo) de nuevo."""
    _save_proposal(_tmp_root)
    args = {"path": str(_tmp_root), "file": "app/agent.py", "old_snippet": "x = 1", "new_snippet": "x = 2", "confirm": True}
    gate.consume_proposal_if_applied("code_apply_fix", args, "confirmo sf-aaaaaaaa", {"applied": True}, "2026-08-11T02:00:00Z")

    error = gate.self_target_gate_error("code_apply_fix", args, "confirmo sf-aaaaaaaa")

    assert error is not None
