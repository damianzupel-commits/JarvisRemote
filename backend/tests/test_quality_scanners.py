"""Tests de integración reales contra Ruff/mypy (instalados como paquetes pip,
igual que Semgrep/Bandit) -- sin mockear el analizador en sí. ESLint/tsc/detekt
solo se prueban en la rama "binario ausente" (determinística, no requiere
Node.js/detekt instalados en esta máquina)."""

from pathlib import Path

import pytest

from app.quality import scanners

_UNUSED_IMPORT_SOURCE = "import os\nimport sys\n\n\ndef f():\n    x = 1\n    return\n"

_TYPE_ERROR_SOURCE = (
    "def add(a: int, b: int) -> int:\n"
    "    return a + \"x\"\n"
    "\n"
    "\n"
    "def greet(name: str) -> str:\n"
    "    return name.upper()\n"
    "\n"
    "\n"
    "greet(123)\n"
)


@pytest.fixture
def ruff_project(tmp_path) -> Path:
    root = tmp_path / "ruff_proj"
    root.mkdir()
    (root / "app.py").write_text(_UNUSED_IMPORT_SOURCE, encoding="utf-8")
    return root


@pytest.fixture
def typed_project(tmp_path) -> Path:
    root = tmp_path / "typed_proj"
    root.mkdir()
    (root / "app.py").write_text(_TYPE_ERROR_SOURCE, encoding="utf-8")
    return root


def test_run_ruff_detects_unused_import_and_variable(ruff_project):
    if scanners.tool_path("ruff") is None:
        pytest.skip("ruff no está instalado en este entorno")

    findings = scanners.run_ruff(ruff_project, python_files=["app.py"])

    assert findings is not None
    codes = {f.rule_id for f in findings}
    assert "F401" in codes
    assert "F841" in codes
    for f in findings:
        assert f.tool == "ruff"
        assert f.file == "app.py"


def test_run_ruff_returns_none_without_python_files(tmp_path):
    assert scanners.run_ruff(tmp_path, python_files=[]) is None


def test_run_ruff_returns_none_when_binary_missing(ruff_project, monkeypatch):
    monkeypatch.setattr(scanners, "tool_path", lambda name: None)
    assert scanners.run_ruff(ruff_project, python_files=["app.py"]) is None


def test_run_mypy_detects_real_type_errors(typed_project):
    if scanners.tool_path("mypy") is None:
        pytest.skip("mypy no está instalado en este entorno")

    findings = scanners.run_mypy(typed_project, python_files=["app.py"])

    assert findings is not None
    assert len(findings) >= 2
    codes = {f.rule_id for f in findings}
    assert "operator" in codes or "arg-type" in codes
    for f in findings:
        assert f.tool == "mypy"
        assert f.severity == "high"


def test_run_mypy_skips_untyped_code(tmp_path):
    root = tmp_path / "untyped_proj"
    root.mkdir()
    (root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    assert scanners.run_mypy(root, python_files=["app.py"]) is None


def test_run_mypy_returns_none_without_python_files(tmp_path):
    assert scanners.run_mypy(tmp_path, python_files=[]) is None


def test_run_mypy_resolves_relative_paths_against_project_root_not_cwd(typed_project, monkeypatch):
    """Regresión: mypy imprime rutas relativas a su cwd (el `root` del escaneo,
    no el cwd del proceso de Jarvis) -- si Jarvis corre desde una carpeta que
    resulta ser ancestro de `root` (ej. Jarvis corriendo desde 'backend/' y
    escaneando el repo completo que lo contiene), resolver esa ruta relativa
    ingenuamente duplicaba el prefijo del proyecto en el file devuelto (bug
    real encontrado al hacer dogfooding del propio repo)."""
    if scanners.tool_path("mypy") is None:
        pytest.skip("mypy no está instalado en este entorno")

    # Simula justamente ese escenario: cwd del proceso de test es un ancestro de root.
    monkeypatch.chdir(typed_project.parent)

    findings = scanners.run_mypy(typed_project, python_files=["app.py"])

    assert findings is not None
    assert len(findings) >= 1
    for f in findings:
        assert f.file == "app.py"


def test_run_eslint_returns_none_without_files(tmp_path):
    assert scanners.run_eslint(tmp_path, js_ts_files=[]) is None


def test_run_eslint_returns_none_when_binary_missing(tmp_path, monkeypatch):
    (tmp_path / "app.js").write_text("var x = 1;\n", encoding="utf-8")
    monkeypatch.setattr(scanners, "tool_path", lambda name: None)
    assert scanners.run_eslint(tmp_path, js_ts_files=["app.js"]) is None


@pytest.mark.timeout(60)
def test_run_eslint_detects_real_bug_without_project_config(tmp_path):
    """ESLint real (no mockeado), sin config propia del proyecto -- ejercita
    la rama de flat config temporal (`@eslint/js` `recommended`). Confirma que
    el flujo entero (generar config temporal, invocar ESLint 9+, resolver
    `require('@eslint/js')` via NODE_PATH) funciona de punta a punta, no solo
    que el binario devuelve JSON válido."""
    if scanners.tool_path("eslint") is None:
        pytest.skip("eslint no está instalado en este entorno")

    root = tmp_path / "js_proj"
    root.mkdir()
    (root / "app.js").write_text("function f() {\n  return undefinedVar;\n}\n", encoding="utf-8")

    findings = scanners.run_eslint(root, js_ts_files=["app.js"])

    assert findings is not None
    assert any(f.rule_id == "no-undef" for f in findings)
    assert not (root / ".jarvis-eslint.config.tmp.cjs").exists()  # config temporal se limpia siempre


def test_run_tsc_returns_none_without_tsconfig(tmp_path):
    (tmp_path / "app.ts").write_text("const x: number = 1;\n", encoding="utf-8")
    assert scanners.run_tsc(tmp_path, ts_files=["app.ts"]) is None


def test_run_tsc_returns_none_when_binary_missing(tmp_path, monkeypatch):
    (tmp_path / "app.ts").write_text("const x: number = 1;\n", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(scanners, "tool_path", lambda name: None)
    assert scanners.run_tsc(tmp_path, ts_files=["app.ts"]) is None


@pytest.mark.timeout(60)
def test_run_tsc_detects_real_type_error(tmp_path):
    """tsc real (no mockeado) sobre un tsconfig.json mínimo -- confirma que
    detecta un error de tipos real, no solo que el binario corre."""
    if scanners.tool_path("tsc") is None:
        pytest.skip("tsc no está instalado en este entorno")

    root = tmp_path / "ts_proj"
    root.mkdir()
    (root / "tsconfig.json").write_text(
        '{"compilerOptions": {"noEmit": true, "strict": true}}', encoding="utf-8"
    )
    (root / "app.ts").write_text("const x: number = 'not a number';\n", encoding="utf-8")

    findings = scanners.run_tsc(root, ts_files=["app.ts"])

    assert findings is not None
    assert len(findings) >= 1
    assert findings[0].file == "app.ts"
    assert findings[0].rule_id.startswith("TS")


def test_run_detekt_returns_none_without_files(tmp_path):
    assert scanners.run_detekt(tmp_path, kotlin_files=[]) is None


def test_run_detekt_returns_none_when_binary_missing(tmp_path, monkeypatch):
    (tmp_path / "App.kt").write_text("class App\n", encoding="utf-8")
    monkeypatch.setattr(scanners, "tool_path", lambda name: None)
    assert scanners.run_detekt(tmp_path, kotlin_files=["App.kt"]) is None
