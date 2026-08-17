"""Tests de audit_report.generate_report: compila hallazgos de seguridad +
calidad ya cacheados y fixes/ediciones ya auditados (mockeando audit_log.read_entries
para no tocar el audit.log real) en una nota Markdown guardada en el vault de
Obsidian."""

from datetime import datetime, timezone

import pytest

from app import audit_report
from app.findings.models import Finding, ScanResult
from app.obsidian import vault
from app.quality import store as quality_store
from app.security import store as security_store
from app.testing import store as test_store
from app.testing.models import RunOutcome


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "security_cache"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "quality_cache"))
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(test_store.settings, "test_run_dir", str(tmp_path / "test_run_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    return root


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_generate_report_raises_without_any_scan(project):
    with pytest.raises(ValueError):
        audit_report.generate_report(str(project))


def test_generate_report_compiles_findings_fixes_and_summary(project, monkeypatch):
    sec_finding = Finding(
        id="sec1", tool="bandit", file="app.py", line=6, end_line=6,
        severity="high", rule_id="B608", message="sqli", cwe=["CWE-89"],
    )
    qual_finding = Finding(
        id="qual1", tool="ruff", file="app.py", line=1, end_line=1,
        severity="low", rule_id="F401", message="unused import",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[sec_finding],
    ))
    quality_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["ruff"], tools_skipped={}, findings=[qual_finding],
    ))

    fix_entry = {
        "target": "code", "tool": "code_apply_fix", "ok": True,
        "arguments": {"path": str(project), "file": "app.py", "commit_message": "fix: sqli", "confirm": True},
        "result": {"applied": True, "file": "app.py", "committed": True, "commit_hash": "abc123", "diff": "..."},
    }
    edit_entry = {
        "target": "fs", "tool": "fs_write_file", "ok": True,
        "arguments": {"path": str(project), "file": "notes.md", "append": False},
        "result": {"committed": True, "commit_hash": "def456", "note": "ok"},
    }
    unrelated_entry = {
        "target": "code", "tool": "code_apply_fix", "ok": True,
        "arguments": {"path": str(project.parent / "other_proj"), "file": "x.py", "commit_message": "fix"},
        "result": {"applied": True, "committed": True, "commit_hash": "zzz"},
    }

    def _fake_read_entries(target=None, tool=None):
        entries = [fix_entry, edit_entry, unrelated_entry]
        if tool is not None:
            entries = [e for e in entries if e["tool"] == tool]
        return entries

    monkeypatch.setattr(audit_report.audit_log, "read_entries", _fake_read_entries)

    result = audit_report.generate_report(str(project))

    assert result["security_findings"] == 1
    assert result["quality_findings"] == 1
    assert result["fixes_applied"] == 1
    assert result["general_edits_applied"] == 1
    assert "abc123" in result["content_preview"]
    assert "def456" in result["content_preview"]
    assert "zzz" not in result["content_preview"]  # de otro proyecto, no debe aparecer

    note = vault.read_note(result["note_id"])
    assert note.author == "jarvis"
    assert "reportes" in note.tags
    assert "B608" in note.content
    assert "F401" in note.content


def test_generate_report_excludes_known_noise_from_executive_summary(project):
    """B101 (bandit assert_used) es ruido conocido -- confirmado auditando
    httpie/cli, donde dominaba el conteo total sin ser una vulnerabilidad real.
    El resumen ejecutivo tiene que destacar el hallazgo real (B608) y excluir
    el B101 del conteo destacado, pero sin borrarlo del todo -- sigue en la
    tabla de detalle, marcado como ruido conocido."""
    real_finding = Finding(
        id="sec1", tool="bandit", file="app.py", line=6, end_line=6,
        severity="high", rule_id="B608", message="sqli real", cwe=["CWE-89"],
    )
    noise_finding = Finding(
        id="sec2", tool="bandit", file="tests/test_app.py", line=12, end_line=12,
        severity="low", rule_id="B101", message="Use of assert detected.",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={},
        findings=[real_finding, noise_finding],
    ))

    result = audit_report.generate_report(str(project))

    assert result["security_findings"] == 2  # el total sigue contando todo, sin ocultar nada
    note = vault.read_note(result["note_id"])
    summary_section = note.content.split("## Resumen ejecutivo")[1].split("## Hallazgos de seguridad")[0]
    assert "1 hallazgo(s) de seguridad real(es)" in summary_section
    assert "excluyeron 1 hallazgo(s)" in summary_section
    assert "B101" in summary_section
    assert "B608" in note.content
    assert "B101" in note.content  # sigue en la tabla de detalle, no se borra
    assert "ruido conocido" in note.content


def _save_test_run(project, **overrides) -> None:
    defaults = dict(
        root=str(project), ran_at=_now(), detected=True, command="python -m pytest",
        language="Python", detect_reason="x", exit_code=0, passed=True, timed_out=False,
        stdout="1 passed", stderr="", stdout_truncated=False, stderr_truncated=False,
    )
    defaults.update(overrides)
    test_store.save_last_run(RunOutcome(**defaults))


def test_generate_report_flags_that_tests_were_never_run(project):
    """Gap principal identificado en el informe de estado 2026-08-10: el reporte
    NUNCA debe poder leerse como "resuelto" sin decir si hubo (o no) una
    verificación de tests real -- si nunca se corrió, el resumen ejecutivo lo
    dice explícitamente en la primera línea, no lo omite en silencio."""
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))

    result = audit_report.generate_report(str(project))

    assert result["tests"] is None
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "Nunca se corrió una verificación de tests real" in summary


def test_generate_report_flags_when_no_test_suite_was_detected(project):
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))
    _save_test_run(project, detected=False, command=None, language=None, detect_reason=None, exit_code=None, passed=False, stdout="")

    result = audit_report.generate_report(str(project))

    assert result["tests"]["detected"] is False
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "No se detectó ninguna suite de tests real" in summary


def test_generate_report_flags_a_green_test_run(project):
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))
    _save_test_run(project, passed=True, command="python -m pytest")

    result = audit_report.generate_report(str(project))

    assert result["tests"]["passed"] is True
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "EN VERDE" in summary


def test_generate_report_prominently_flags_a_failed_test_run(project):
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))
    _save_test_run(project, passed=False, exit_code=1, command="python -m pytest", stdout="1 failed")

    result = audit_report.generate_report(str(project))

    assert result["tests"]["passed"] is False
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "FALLÓ" in summary
    assert "no dar este proyecto por estable" in summary.lower()
