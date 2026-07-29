"""Tests de `security/runner.py::rescan_file` -- re-escaneo acotado a un solo
archivo (usado por code_apply_fix después de aplicar un fix). Mockea
`scanners.run_*` igual que test_security_tools.py, para probar de forma
determinística la orquestación y el merge con el cache existente."""

import pytest

from app.codebase import store as codebase_store
from app.findings.models import Finding
from app.security import runner, scanners
from app.security import store as security_store


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "security_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")
    (root / "other.py").write_text("print('chau')\n", encoding="utf-8")
    return root


def _finding(file, line, severity, rule_id, tool="semgrep"):
    return Finding(id=f"{tool}-{file}-{line}-{rule_id}", tool=tool, file=file, line=line, end_line=None, severity=severity, rule_id=rule_id, message="msg")


def test_rescan_file_without_prior_scan_reports_everything_as_new(project, monkeypatch):
    finding = _finding("app.py", 1, "high", "r1")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [finding])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)

    result = runner.rescan_file(str(project), "app.py")

    assert result["resolved"] == []
    assert result["persisting"] == []
    assert [f["id"] for f in result["new"]] == [finding.id]


def test_rescan_file_detects_resolved_finding(project, monkeypatch):
    finding = _finding("app.py", 1, "critical", "sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [finding])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    runner.scan_project(str(project))  # cachea el hallazgo original

    # Después del fix, semgrep ya no encuentra nada en ese archivo.
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    result = runner.rescan_file(str(project), "app.py")

    assert [f["id"] for f in result["resolved"]] == [finding.id]
    assert result["persisting"] == []
    assert result["new"] == []


def test_rescan_file_only_touches_the_target_files_findings(project, monkeypatch):
    app_finding = _finding("app.py", 1, "high", "r1")
    other_finding = _finding("other.py", 1, "high", "r2")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [app_finding, other_finding])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    runner.scan_project(str(project))

    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    runner.rescan_file(str(project), "app.py")

    cached = security_store.load_scan(project)
    assert [f.id for f in cached.findings] == [other_finding.id]


def test_rescan_file_passes_single_file_list_to_bandit(project, monkeypatch):
    captured = {}

    def _run_bandit(root, python_files):
        captured["python_files"] = python_files
        return None

    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", _run_bandit)

    runner.rescan_file(str(project), "app.py")

    assert captured["python_files"] == ["app.py"]


def test_rescan_file_skips_bandit_for_non_python_files(project, monkeypatch):
    (project / "index.js").write_text("console.log(1)\n", encoding="utf-8")
    bandit_called = {"n": 0}

    def _run_bandit(root, python_files):
        bandit_called["n"] += 1
        return None

    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", _run_bandit)

    runner.rescan_file(str(project), "index.js")

    assert bandit_called["n"] == 0


def test_rescan_file_skips_trivy_for_non_manifest_files(project, monkeypatch):
    trivy_called = {"n": 0}

    def _run_trivy(root):
        trivy_called["n"] += 1
        return []

    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", _run_trivy)

    runner.rescan_file(str(project), "app.py")

    assert trivy_called["n"] == 0


def test_rescan_file_runs_trivy_for_manifest_files(project, monkeypatch):
    (project / "requirements.txt").write_text("flask==0.1\n", encoding="utf-8")
    trivy_finding = _finding("requirements.txt", 1, "high", "CVE-1", tool="trivy")
    other_manifest_finding = _finding("package.json", 1, "high", "CVE-2", tool="trivy")

    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: [trivy_finding, other_manifest_finding])

    result = runner.rescan_file(str(project), "requirements.txt")

    # Trivy escanea TODO el árbol de manifiestos -- se filtra a solo el
    # archivo que se está re-escaneando antes de reportar/cachear.
    assert [f["id"] for f in result["new"]] == [trivy_finding.id]
    cached = security_store.load_scan(project)
    assert [f.id for f in cached.findings] == [trivy_finding.id]


def test_rescan_file_raises_for_missing_file(project):
    with pytest.raises(FileNotFoundError):
        runner.rescan_file(str(project), "no-existe.py")
