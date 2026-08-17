"""Núcleo de ejecución real de un comando de shell (subprocess + timeout duro +
kill del árbol de procesos + truncado de salida) -- extraído de
`app/tools/pc_command.py` (donde vivía en exclusiva hasta 2026-08-10) para que
`app/testing/runner.py` (corrida real de tests después de un fix, ver la
sesión de meta-observación de esa fecha) lo reuse tal cual en vez de
reimplementar su propia versión de "correr un comando y no colgar el turno de
chat si se cuelga".

Vive en `app/` (no en `app/tools/`) a propósito: es infraestructura compartida
entre un tool (`pc_run_command`) y un módulo de librería (`app/testing/`), y
`app/tools/*` nunca debería importarse desde `app/<librería>/` -- mismo
criterio de dirección de dependencias que separa `app/security/`,
`app/quality/`, `app/codeedit/` (lógica) de `app/tools/*.py` (wrappers finos
que exponen esa lógica al LLM).

No hace ningún chequeo de habilitación ni de blocklist -- eso es
responsabilidad de cada caller (`pc_run_command` corre su propio
`PC_SHELL_ENABLED` + blocklist antes de llamar acá; `app/testing/runner.py` no
tiene blocklist propio porque el comando nunca lo elige el LLM libremente,
sale de `detect_test_command`)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("jarvis.shell_exec")

# Tope duro de timeout, sin importar lo que pida el caller -- evita que un
# comando lento (o un timeout mal elegido) cuelgue el turno de chat
# indefinidamente. 600s (10 min) alcanza para instalar dependencias pesadas o
# correr una suite de tests grande sin dejar la puerta abierta a un comando
# que nunca termine.
MAX_TIMEOUT_SECONDS = 600.0

# Cuánto de stdout/stderr devolver como máximo -- un comando con salida
# gigante (ej. un build verboso o una suite de tests grande) no debe inflar el
# historial de chat sin límite, mismo criterio que `fs_read_file(max_chars=...)`.
MAX_OUTPUT_CHARS = 20000


def truncate_output(text: str) -> tuple[str, bool]:
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS], True
    return text, False


def kill_process_tree(pid: int) -> None:
    """Mata el proceso y todos sus hijos -- necesario en Windows porque un
    comando corrido con shell=True (cmd.exe /c ...) puede spawnear
    subprocesos (ej. pip instalando, pytest lanzando workers) que
    proc.kill() por sí solo no toca, dejándolos huérfanos corriendo en
    background después de que ya se reportó timeout."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        import signal

        try:
            import os

            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_shell_command(command: str, work_dir: str | Path, timeout: float) -> dict:
    effective_timeout = min(float(timeout), MAX_TIMEOUT_SECONDS)
    logger.info("shell_exec: command=%r cwd=%s timeout=%s", command, work_dir, effective_timeout)

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        command,
        cwd=str(work_dir),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=effective_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_tree(proc.pid)
        stdout, stderr = proc.communicate()

    stdout, stdout_truncated = truncate_output(stdout)
    stderr, stderr_truncated = truncate_output(stderr)
    return {
        "command": command,
        "cwd": str(work_dir),
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }
