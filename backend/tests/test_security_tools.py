"""Tests de las tools expuestas al LLM (`app/tools/security_scan.py`). Los
escáneres reales ya se prueban sin mockear en test_security_scanners.py; acá
se mockean `scanners.run_*` para probar de forma determinística la capa de
orquestación (runner), cache (store) y las tools en sí -- que es donde vive la
lógica propia de Jarvis, no la de Semgrep/Bandit."""

import pytest

from app.codebase import store as codebase_store
from app.security import scanners, store as security_store
from app.security.models import Finding
from app.tools import security_scan


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "security_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")
    return root


def test_security_scan_project_aggregates_and_sorts_by_severity(project, monkeypatch):
    findings = [
        Finding(id="a", tool="semgrep", file="app.py", line=10, end_line=10, severity="low", rule_id="r1", message="low sev"),
        Finding(id="b", tool="semgrep", file="app.py", line=5, end_line=5, severity="critical", rule_id="r2", message="crit sev", cwe=["CWE-89"], owasp=["A03:2021"]),
    ]
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: findings)
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    result = security_scan.security_scan_project(str(project))

    assert result["total_findings"] == 2
    assert result["tools_run"] == ["semgrep"]
    assert "bandit" in result["tools_skipped"]
    assert result["findings"][0]["id"] == "b"  # critical primero
    assert result["findings"][1]["id"] == "a"
    assert result["findings_by_severity"] == {"low": 1, "critical": 1}


def test_security_scan_project_passes_python_files_to_bandit(project, monkeypatch):
    """Regresión: el indexador de Codebase marca los .py como language='Python'
    (con mayúscula) -- runner.scan_project tiene que filtrar por ese mismo
    valor exacto, si no Bandit nunca recibe archivos y se salta siempre (bug
    real encontrado al hacer dogfooding del propio repo)."""
    captured = {}

    def _run_bandit(root, python_files):
        captured["python_files"] = python_files
        return None

    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", _run_bandit)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))

    assert captured["python_files"] == ["app.py"]


def test_security_scan_project_uses_cache_unless_refresh(project, monkeypatch):
    calls = {"n": 0}

    def _run(root):
        calls["n"] += 1
        return []

    monkeypatch.setattr(scanners, "run_semgrep", _run)
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))
    security_scan.security_scan_project(str(project))
    assert calls["n"] == 1

    security_scan.security_scan_project(str(project), refresh=True)
    assert calls["n"] == 2


def test_security_get_finding_returns_code_context(project, monkeypatch):
    (project / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    finding = Finding(id="xyz", tool="bandit", file="app.py", line=10, end_line=10, severity="high", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))
    result = security_scan.security_get_finding(str(project), "xyz", context_lines=2)

    assert result["finding"]["id"] == "xyz"
    context_lines = {c["line"]: c["text"] for c in result["code_context"]}
    assert context_lines[10] == "line10"
    assert set(context_lines) == {8, 9, 10, 11, 12}


def test_security_get_finding_raises_for_unknown_id(project):
    with pytest.raises(ValueError):
        security_scan.security_get_finding(str(project), "no-existe")
