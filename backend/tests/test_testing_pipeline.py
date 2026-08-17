"""Tests del paso de 'testear real' (app/testing/) agregado 2026-08-10 --
detección del comando de test real de un proyecto y su ejecución, reusando el
mismo núcleo de shell_exec que pc_run_command.

`test_run_tests_runs_a_real_passing_pytest_suite_end_to_end` y
`test_run_tests_runs_a_real_failing_pytest_suite_end_to_end` corren
`python -m pytest` DE VERDAD contra un proyecto de prueba en tmp_path (no
mockeado) -- mismo criterio que test_pc_command.py/test_codeedit_fixer.py:
lo que hay que verificar acá es que el subproceso corre y su exit_code se
interpreta bien, no que se llamó a una función mockeada con los argumentos
correctos."""

from __future__ import annotations

import json

import pytest

from app.codebase import store as codebase_store
from app.testing import detect, runner
from app.testing import store as test_store


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(test_store.settings, "test_run_dir", str(tmp_path / "test_run_cache"))


def _index(root):
    return codebase_store.get_or_build(root)


# ---------------------------------------------------------------------------
# detect_test_command
# ---------------------------------------------------------------------------


def test_detects_pytest_when_config_and_test_files_present(tmp_path):
    root = tmp_path / "pyproj"
    root.mkdir()
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (root / "app.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    command = detect.detect_test_command(root, _index(root))

    assert command is not None
    assert command.language == "Python"
    assert "pytest" in command.command


def test_does_not_detect_pytest_without_real_test_files(tmp_path):
    """pyproject.toml solo no alcanza -- tiene que haber archivos de test reales
    detectados por el índice de Codebase, si no cualquier proyecto Python con
    un pyproject.toml (la mayoría) matchearía sin tener ninguna suite real."""
    root = tmp_path / "pyproj_no_tests"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")

    command = detect.detect_test_command(root, _index(root))

    assert command is None


def test_detects_pytest_with_no_config_file_at_all(tmp_path):
    """Regresión de un bug real encontrado en la validación end-to-end contra
    todo-app-test (2026-08-10): un proyecto Python real y perfectamente
    testeable puede no tener NINGÚN archivo de config de pytest (ni
    pytest.ini, ni pyproject.toml, ni setup.cfg) -- solo un archivo de test
    con la convención de nombres. La versión anterior de detect_test_command
    exigía además un marcador de config y devolvía None acá, un falso
    negativo real."""
    root = tmp_path / "todo_app_style"
    root.mkdir()
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")
    (root / "requirements.txt").write_text("flask\n", encoding="utf-8")
    (root / "test_app.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    command = detect.detect_test_command(root, _index(root))

    assert command is not None
    assert command.language == "Python"
    assert "pytest" in command.command


def test_detects_npm_test_when_package_json_has_real_script(tmp_path):
    root = tmp_path / "nodeproj"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"name": "x", "scripts": {"test": "jest"}}), encoding="utf-8"
    )

    command = detect.detect_test_command(root, _index(root))

    assert command is not None
    assert command.command == "npm test"
    assert command.language == "JavaScript/TypeScript"


def test_ignores_npm_init_placeholder_test_script(tmp_path):
    root = tmp_path / "nodeproj_placeholder"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"name": "x", "scripts": {"test": 'echo "Error: no test specified" && exit 1'}}),
        encoding="utf-8",
    )

    command = detect.detect_test_command(root, _index(root))

    assert command is None


def test_detects_gradle_wrapper_test_command(tmp_path):
    root = tmp_path / "gradleproj"
    root.mkdir()
    (root / "gradlew.bat").write_text("@echo off\n", encoding="utf-8")

    command = detect.detect_test_command(root, _index(root))

    assert command is not None
    assert "gradlew" in command.command
    assert command.language == "Java/Kotlin"


def test_detects_go_test_command(tmp_path):
    root = tmp_path / "goproj"
    root.mkdir()
    (root / "go.mod").write_text("module x\n", encoding="utf-8")
    (root / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")

    command = detect.detect_test_command(root, _index(root))

    assert command is not None
    assert command.command == "go test ./..."


def test_detects_cargo_test_command(tmp_path):
    root = tmp_path / "rustproj"
    root.mkdir()
    (root / "Cargo.toml").write_text("[package]\nname = \"x\"\n", encoding="utf-8")

    command = detect.detect_test_command(root, _index(root))

    assert command is not None
    assert command.command == "cargo test"


def test_returns_none_when_no_marker_matches(tmp_path):
    root = tmp_path / "plainproj"
    root.mkdir()
    (root / "readme.md").write_text("hola\n", encoding="utf-8")

    assert detect.detect_test_command(root, _index(root)) is None


# ---------------------------------------------------------------------------
# run_tests (end-to-end real, sin mockear el subproceso)
# ---------------------------------------------------------------------------


def test_run_tests_runs_a_real_passing_pytest_suite_end_to_end(tmp_path):
    root = tmp_path / "realproj_pass"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    result = runner.run_tests(str(root), timeout=60)

    assert result.detected is True
    assert result.language == "Python"
    assert result.passed is True
    assert result.exit_code == 0
    assert "1 passed" in result.stdout


def test_run_tests_runs_a_real_failing_pytest_suite_end_to_end(tmp_path):
    root = tmp_path / "realproj_fail"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_bad.py").write_text("def test_bad():\n    assert 1 + 1 == 3\n", encoding="utf-8")

    result = runner.run_tests(str(root), timeout=60)

    assert result.detected is True
    assert result.passed is False
    assert result.exit_code != 0
    assert "1 failed" in result.stdout


def test_run_tests_reports_not_detected_without_raising_when_no_suite_exists(tmp_path):
    root = tmp_path / "no_tests_here"
    root.mkdir()
    (root / "readme.md").write_text("hola\n", encoding="utf-8")

    result = runner.run_tests(str(root))

    assert result.detected is False
    assert result.passed is False
    assert result.exit_code is None


def test_run_tests_persists_the_last_run_to_the_store(tmp_path):
    root = tmp_path / "persisted_proj"
    root.mkdir()
    (root / "readme.md").write_text("hola\n", encoding="utf-8")

    runner.run_tests(str(root))
    loaded = test_store.load_last_run(root)

    assert loaded is not None
    assert loaded.detected is False


def test_load_last_run_returns_none_when_nothing_recorded(tmp_path):
    root = tmp_path / "never_tested"
    root.mkdir()

    assert test_store.load_last_run(root) is None
