"""Detección del comando de test REAL de un proyecto -- reusa el índice de
Codebase (`app/codebase/`, el mismo que `security/runner.py` y
`quality/runner.py` ya reusan para decidir qué escáner correr) en vez de
reimplementar la detección de lenguaje.

La detección es por MARCADOR real en el proyecto (archivos de test con
convención de pytest para Python, package.json con script "test" real,
wrapper de Gradle, go.mod, Cargo.toml) -- nunca inventa un comando para un
lenguaje que no tiene ninguno de estos marcadores; si no hay nada, devuelve
None y el caller (`runner.py`) lo reporta como "no se pudo verificar", no
como un fallo silencioso.

Para Python, el marcador es la presencia de archivos de test reales
(`test_*.py`/`*_test.py`/carpeta `tests`) -- NO se exige además un archivo de
config de pytest (pytest.ini/pyproject.toml/etc.): pytest descubre esos
archivos igual sin ningún config, y exigirlo de más hacía fallar la detección
en un proyecto real durante la validación end-to-end de este módulo
(todo-app-test, 2026-08-10: solo app.py + test_app.py + requirements.txt, sin
ningún archivo de config, y pytest lo corre perfectamente).

Orden de prioridad cuando hay más de un marcador (repo mixto): Python > Node >
Gradle (Java/Kotlin) > Go > Rust -- arbitrario pero estable. Esta primera
versión detecta y corre UN solo comando por proyecto, no una batería completa
multi-lenguaje (mismo alcance que pidió Damian: "el comando de test real del
proyecto", en singular)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..codebase.models import CodebaseIndex
from .models import DetectedCommand


def _has_python_test_files(index: CodebaseIndex) -> bool:
    for f in index.files:
        if f.language != "Python":
            continue
        parts = Path(f.path).parts
        name = parts[-1] if parts else ""
        if name.startswith("test_") or name.endswith("_test.py") or "tests" in parts or "test" in parts:
            return True
    return False


def _python_test_command(root: Path) -> str:
    # Preferir el pytest del venv del propio proyecto si existe -- correr
    # "python -m pytest" a secas puede terminar usando un intérprete/entorno
    # distinto del que el proyecto espera.
    venv_pytest = root / ".venv" / ("Scripts/pytest.exe" if sys.platform == "win32" else "bin/pytest")
    if venv_pytest.is_file():
        return f'"{venv_pytest}"'
    return "python -m pytest"


def _node_test_command(root: Path) -> str | None:
    package_json = root / "package.json"
    if not package_json.is_file():
        return None
    try:
        data = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    test_script = (data.get("scripts") or {}).get("test")
    if not test_script:
        return None
    # El placeholder que deja "npm init" por default ('echo "Error: no test
    # specified" && exit 1') no es un test real -- correrlo solo daría un
    # exit_code != 0 que se leería como "los tests fallaron" cuando en
    # realidad nunca hubo ninguno.
    if "no test specified" in test_script.lower():
        return None
    return "npm test"


def _gradle_test_command(root: Path) -> str | None:
    if sys.platform == "win32":
        return "gradlew.bat test" if (root / "gradlew.bat").is_file() else None
    return "./gradlew test" if (root / "gradlew").is_file() else None


def detect_test_command(root: Path, index: CodebaseIndex) -> DetectedCommand | None:
    # Bug real encontrado en la validación end-to-end contra un proyecto real
    # (todo-app-test, 2026-08-10): pytest descubre test_*.py sin NINGÚN archivo
    # de config -- exigir además un marcador de config (pytest.ini/pyproject.toml/
    # etc.) hacía que un proyecto Python real y perfectamente testeable (solo
    # app.py + test_app.py + requirements.txt, sin config alguna) diera
    # 'detected=False'. Los archivos de test reales (ver _has_python_test_files)
    # ya son señal suficiente por sí sola; el marcador de config, si existe, no
    # agrega nada que valga la pena exigir.
    if _has_python_test_files(index):
        return DetectedCommand(
            command=_python_test_command(root),
            language="Python",
            reason="archivos de test reales (test_*.py / *_test.py / carpeta tests) detectados por el índice de Codebase",
        )

    node_command = _node_test_command(root)
    if node_command:
        return DetectedCommand(
            command=node_command,
            language="JavaScript/TypeScript",
            reason="package.json con un script 'test' real (no el placeholder de 'npm init')",
        )

    gradle_command = _gradle_test_command(root)
    if gradle_command:
        return DetectedCommand(
            command=gradle_command,
            language="Java/Kotlin",
            reason="wrapper de Gradle (gradlew/gradlew.bat) presente en la raíz del proyecto",
        )

    if (root / "go.mod").is_file() and any(f.language == "Go" for f in index.files):
        return DetectedCommand(
            command="go test ./...", language="Go", reason="go.mod en la raíz + archivos Go en el índice"
        )

    if (root / "Cargo.toml").is_file():
        return DetectedCommand(command="cargo test", language="Rust", reason="Cargo.toml en la raíz del proyecto")

    return None
