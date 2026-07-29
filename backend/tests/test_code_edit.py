"""Tests de la tool genérica `code_apply_fix` (app/tools/code_edit.py) --
la lógica de aplicar/commitear ya se prueba a fondo en test_codeedit_fixer.py;
acá se prueba la capa de tool en sí (paso de argumentos, forma del resultado,
y el rescan+mensaje de cascada que se dispara tras un fix confirmado)."""

import pytest

from app.codebase import store as codebase_store
from app.findings.models import Finding
from app.quality import scanners as quality_scanners
from app.quality import store as quality_store
from app.security import scanners as security_scanners
from app.security import store as security_store
from app.tools import code_edit


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "security_cache"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "quality_cache"))
    # code_apply_fix con confirm=true dispara un rescan de seguridad Y calidad
    # del archivo tocado -- se mockean ambos para que estos tests no dependan
    # de binarios reales (bandit/trivy/ruff/mypy) ni de que encuentren algo
    # inesperado en los archivos de prueba triviales.
    monkeypatch.setattr(security_scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(security_scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(quality_scanners, "run_ruff", lambda root, python_files: None)
    monkeypatch.setattr(quality_scanners, "run_mypy", lambda root, python_files: None)


def test_code_apply_fix_dry_run_via_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(security_scanners, "run_semgrep", lambda root, scan_target=None: [])
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("secret = 'hunter2'\n", encoding="utf-8")

    result = code_edit.code_apply_fix(
        path=str(project), file="app.py", old_snippet="secret = 'hunter2'",
        new_snippet="secret = os.environ['SECRET']", commit_message="fix", confirm=False,
    )

    assert result["applied"] is False
    assert (project / "app.py").read_text() == "secret = 'hunter2'\n"
    assert "rescan" not in result  # dry-run no dispara rescan -- nada se aplicó todavía


def test_code_apply_fix_confirmed_triggers_rescan_with_no_cascade(tmp_path, monkeypatch):
    monkeypatch.setattr(security_scanners, "run_semgrep", lambda root, scan_target=None: [])
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("secret = 'hunter2'\n", encoding="utf-8")

    result = code_edit.code_apply_fix(
        path=str(project), file="app.py", old_snippet="secret = 'hunter2'",
        new_snippet="secret = os.environ['SECRET']", commit_message="fix: no hardcoded secret", confirm=True,
    )

    assert result["applied"] is True
    assert result["rescan"]["resolved_findings"] == []
    assert result["rescan"]["new_findings"] == []
    assert result["rescan"]["cascade_message"] is None


def test_code_apply_fix_confirmed_reports_cascade_resolution(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("query = f\"SELECT * FROM users WHERE id={user_id}\"\n", encoding="utf-8")

    finding_critical = Finding(
        id="f1", tool="semgrep", file="app.py", line=1, end_line=1,
        severity="critical", rule_id="sql-injection", message="SQLi",
    )
    finding_low = Finding(
        id="f2", tool="semgrep", file="app.py", line=1, end_line=1,
        severity="low", rule_id="f-string-format", message="ruido relacionado",
    )
    monkeypatch.setattr(security_scanners, "run_semgrep", lambda root, scan_target=None: [finding_critical, finding_low])
    from app.security.runner import scan_project
    scan_project(str(project))  # cachea los dos hallazgos originales

    # Tras el fix, semgrep ya no encuentra nada -- ambos se resolvieron.
    monkeypatch.setattr(security_scanners, "run_semgrep", lambda root, scan_target=None: [])

    result = code_edit.code_apply_fix(
        path=str(project), file="app.py",
        old_snippet='query = f"SELECT * FROM users WHERE id={user_id}"',
        new_snippet='query = "SELECT * FROM users WHERE id=%s"',
        commit_message="fix: sql injection", confirm=True,
    )

    resolved_ids = {f["id"] for f in result["rescan"]["resolved_findings"]}
    assert resolved_ids == {"f1", "f2"}
    assert "2 hallazgo" in result["rescan"]["cascade_message"]
    assert "crítico" in result["rescan"]["cascade_message"]
    assert "bajo" in result["rescan"]["cascade_message"]
