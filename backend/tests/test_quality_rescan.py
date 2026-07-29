"""Tests de `quality/runner.py::rescan_file` -- mismo criterio que
test_security_rescan.py, mockeando `scanners.run_*`."""

import pytest

from app.codebase import store as codebase_store
from app.findings.models import Finding
from app.quality import runner, scanners
from app.quality import store as quality_store


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "quality_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("x=1\n", encoding="utf-8")
    return root


def _finding(file, line, severity, rule_id, tool="ruff"):
    return Finding(id=f"{tool}-{file}-{line}-{rule_id}", tool=tool, file=file, line=line, end_line=None, severity=severity, rule_id=rule_id, message="msg")


def test_rescan_file_runs_ruff_and_mypy_for_python(project, monkeypatch):
    captured = {}

    def _ruff(root, python_files):
        captured["ruff_files"] = python_files
        return []

    def _mypy(root, python_files):
        captured["mypy_files"] = python_files
        return []

    monkeypatch.setattr(scanners, "run_ruff", _ruff)
    monkeypatch.setattr(scanners, "run_mypy", _mypy)

    runner.rescan_file(str(project), "app.py")

    assert captured["ruff_files"] == ["app.py"]
    assert captured["mypy_files"] == ["app.py"]


def test_rescan_file_skips_ruff_mypy_for_non_python(project, monkeypatch):
    (project / "index.ts").write_text("const x = 1;\n", encoding="utf-8")
    called = {"n": 0}

    def _fail(*a, **k):
        called["n"] += 1
        return []

    monkeypatch.setattr(scanners, "run_ruff", _fail)
    monkeypatch.setattr(scanners, "run_mypy", _fail)
    monkeypatch.setattr(scanners, "run_eslint", lambda root, js_ts_files: [])

    runner.rescan_file(str(project), "index.ts")

    assert called["n"] == 0


def test_rescan_file_runs_eslint_for_ts_file(project, monkeypatch):
    (project / "index.ts").write_text("const x = 1;\n", encoding="utf-8")
    captured = {}

    def _eslint(root, js_ts_files):
        captured["files"] = js_ts_files
        return []

    monkeypatch.setattr(scanners, "run_eslint", _eslint)

    runner.rescan_file(str(project), "index.ts")

    assert captured["files"] == ["index.ts"]


def test_rescan_file_does_not_run_tsc(project, monkeypatch):
    (project / "index.ts").write_text("const x = 1;\n", encoding="utf-8")
    tsc_called = {"n": 0}

    def _tsc(root, ts_files):
        tsc_called["n"] += 1
        return []

    monkeypatch.setattr(scanners, "run_eslint", lambda root, js_ts_files: [])
    monkeypatch.setattr(scanners, "run_tsc", _tsc)

    runner.rescan_file(str(project), "index.ts")

    assert tsc_called["n"] == 0


def test_rescan_file_detects_cascade_resolution(project, monkeypatch):
    critical_like = _finding("app.py", 1, "high", "F821")
    low1 = _finding("app.py", 2, "low", "F401")
    low2 = _finding("app.py", 3, "low", "F841")

    monkeypatch.setattr(scanners, "run_ruff", lambda root, python_files: [critical_like, low1, low2])
    monkeypatch.setattr(scanners, "run_mypy", lambda root, python_files: None)
    runner.scan_project(str(project))

    # El fix resolvió las 3 de una -- típico de un solo import roto que
    # generaba encadenados F821 (nombre indefinido) + F401/F841 relacionados.
    monkeypatch.setattr(scanners, "run_ruff", lambda root, python_files: [])
    result = runner.rescan_file(str(project), "app.py")

    assert {f["id"] for f in result["resolved"]} == {critical_like.id, low1.id, low2.id}
    assert result["persisting"] == []


def test_rescan_file_raises_for_missing_file(project):
    with pytest.raises(FileNotFoundError):
        runner.rescan_file(str(project), "no-existe.py")
