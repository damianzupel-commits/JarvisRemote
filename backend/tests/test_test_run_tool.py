"""Tests de la tool `code_run_tests` (app/tools/test_run.py) -- la lógica real
de detección/ejecución ya se prueba a fondo en test_testing_pipeline.py; acá
se prueba la capa de tool en sí (forma del resultado devuelto al LLM y
auditoría de cada llamada)."""

from __future__ import annotations

import pytest

from app import audit_log
from app.codebase import store as codebase_store
from app.testing import store as test_store
from app.tools import test_run


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(test_store.settings, "test_run_dir", str(tmp_path / "test_run_cache"))


def test_code_run_tests_runs_a_real_passing_suite_and_audits_success(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kw: logged.append(kw))

    result = test_run.code_run_tests(str(project), timeout=60)

    assert result["detected"] is True
    assert result["passed"] is True
    assert len(logged) == 1
    assert logged[0]["target"] == "code"
    assert logged[0]["tool"] == "code_run_tests"
    assert "error" not in logged[0]
    assert logged[0]["result"]["passed"] is True


def test_code_run_tests_reports_not_detected_for_a_project_without_a_suite(tmp_path, monkeypatch):
    project = tmp_path / "proj_no_tests"
    project.mkdir()
    (project / "readme.md").write_text("hola\n", encoding="utf-8")

    result = test_run.code_run_tests(str(project))

    assert result["detected"] is False
    assert result["passed"] is False


def test_code_run_tests_audits_and_reraises_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr(test_run, "run_tests", lambda path, timeout=300.0: (_ for _ in ()).throw(NotADirectoryError("nope")))
    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kw: logged.append(kw))

    with pytest.raises(NotADirectoryError):
        test_run.code_run_tests(str(tmp_path / "does_not_exist"))

    assert len(logged) == 1
    assert logged[0]["error"] == "nope"
