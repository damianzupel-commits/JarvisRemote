"""Corre el comando de test REAL de un proyecto (detectado por
`detect.py::detect_test_command`) reusando el mismo núcleo de ejecución que
`pc_run_command` (`app/shell_exec.py::run_shell_command`) -- mismo timeout
duro, mismo kill del árbol de procesos si se cuelga, mismo truncado de
salida.

No tiene blocklist ni flag de habilitación propios como `pc_run_command`: acá
el comando nunca lo elige el LLM libremente, sale de `detect_test_command`
(pytest/npm test/gradlew test/go test/cargo test, siempre atados a un
marcador real del proyecto), un caso de uso mucho más acotado que un comando
de shell arbitrario."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..codebase import store as codebase_store
from ..shell_exec import run_shell_command
from . import store as test_store
from .detect import detect_test_command
from .models import RunOutcome

# Más generoso que el default de pc_run_command (120s): una suite de tests
# real (sobre todo un build de Gradle en frío) puede tardar bastante más que
# un comando suelto -- sigue acotado por MAX_TIMEOUT_SECONDS de shell_exec
# (600s) sin importar lo que se pida acá.
_DEFAULT_TEST_TIMEOUT_SECONDS = 300.0


def run_tests(path: str, timeout: float = _DEFAULT_TEST_TIMEOUT_SECONDS) -> RunOutcome:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    index = codebase_store.get_or_build(root)
    command = detect_test_command(root, index)

    if command is None:
        result = RunOutcome(
            root=str(root),
            ran_at=datetime.now(timezone.utc).isoformat(),
            detected=False,
            command=None,
            language=None,
            detect_reason=None,
            exit_code=None,
            passed=False,
            timed_out=False,
            stdout="",
            stderr="",
            stdout_truncated=False,
            stderr_truncated=False,
        )
        test_store.save_last_run(result)
        return result

    exec_result = run_shell_command(command.command, root, timeout)
    passed = exec_result["exit_code"] == 0 and not exec_result["timed_out"]
    result = RunOutcome(
        root=str(root),
        ran_at=datetime.now(timezone.utc).isoformat(),
        detected=True,
        command=command.command,
        language=command.language,
        detect_reason=command.reason,
        exit_code=exec_result["exit_code"],
        passed=passed,
        timed_out=exec_result["timed_out"],
        stdout=exec_result["stdout"],
        stderr=exec_result["stderr"],
        stdout_truncated=exec_result["stdout_truncated"],
        stderr_truncated=exec_result["stderr_truncated"],
    )
    test_store.save_last_run(result)
    return result
