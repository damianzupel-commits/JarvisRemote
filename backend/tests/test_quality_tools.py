"""Tests de las tools expuestas al LLM (`app/tools/quality_scan.py`). Los
analizadores reales ya se prueban sin mockear en test_quality_scanners.py; acá
se mockean `scanners.run_*` para probar de forma determinística la capa de
orquestación (runner), cache (store) y las tools en sí."""

import pytest

from app.codebase import store as codebase_store
from app.findings.models import Finding
from app.quality import scanners, store as quality_store
from app.tools import quality_scan


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "quality_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")
    return root


def _no_scanners(monkeypatch):
    monkeypatch.setattr(scanners, "run_ruff", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_mypy", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_eslint", lambda root, js_ts_files: None)
    monkeypatch.setattr(scanners, "run_tsc", lambda root, ts_files: None)
    monkeypatch.setattr(scanners, "run_detekt", lambda root, kotlin_files: None)


def test_quality_scan_project_aggregates_and_sorts_by_severity(project, monkeypatch):
    findings = [
        Finding(id="a", tool="ruff", file="app.py", line=10, end_line=10, severity="low", rule_id="F401", message="unused import"),
        Finding(id="b", tool="mypy", file="app.py", line=5, end_line=5, severity="high", rule_id="arg-type", message="type error"),
    ]
    _no_scanners(monkeypatch)
    monkeypatch.setattr(scanners, "run_ruff", lambda root, python_files: findings[:1])
    monkeypatch.setattr(scanners, "run_mypy", lambda root, python_files: findings[1:])

    result = quality_scan.quality_scan_project(str(project))

    assert result["total_findings"] == 2
    assert set(result["tools_run"]) == {"ruff", "mypy"}
    assert result["findings"][0]["id"] == "b"  # high primero
    assert result["findings"][1]["id"] == "a"
    assert result["findings_by_severity"] == {"low": 1, "high": 1}


def test_quality_scan_project_passes_python_files_from_index(project, monkeypatch):
    captured = {}

    def _run_ruff(root, python_files):
        captured["python_files"] = python_files
        return None

    _no_scanners(monkeypatch)
    monkeypatch.setattr(scanners, "run_ruff", _run_ruff)

    quality_scan.quality_scan_project(str(project))

    assert captured["python_files"] == ["app.py"]


def test_quality_scan_project_uses_cache_unless_refresh(project, monkeypatch):
    calls = {"n": 0}

    def _run(root, python_files):
        calls["n"] += 1
        return []

    _no_scanners(monkeypatch)
    monkeypatch.setattr(scanners, "run_ruff", _run)

    quality_scan.quality_scan_project(str(project))
    quality_scan.quality_scan_project(str(project))
    assert calls["n"] == 1

    quality_scan.quality_scan_project(str(project), refresh=True)
    assert calls["n"] == 2


def test_quality_get_finding_returns_code_context(project, monkeypatch):
    (project / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    finding = Finding(id="xyz", tool="mypy", file="app.py", line=10, end_line=10, severity="high", rule_id="arg-type", message="type error")
    _no_scanners(monkeypatch)
    monkeypatch.setattr(scanners, "run_mypy", lambda root, python_files: [finding])

    quality_scan.quality_scan_project(str(project))
    result = quality_scan.quality_get_finding(str(project), "xyz", context_lines=2)

    assert result["finding"]["id"] == "xyz"
    context_lines = {c["line"]: c["text"] for c in result["code_context"]}
    assert context_lines[10] == "line10"
    assert set(context_lines) == {8, 9, 10, 11, 12}


def test_quality_get_finding_raises_for_unknown_id(project):
    with pytest.raises(ValueError):
        quality_scan.quality_get_finding(str(project), "no-existe")
