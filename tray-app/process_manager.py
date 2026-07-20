"""Arranca/para el backend como subproceso y le manda stdout+stderr a un log file."""

import subprocess
import sys
import threading

import config

_process: subprocess.Popen | None = None
_lock = threading.Lock()


def is_running() -> bool:
    with _lock:
        return _process is not None and _process.poll() is None


def start() -> str:
    global _process
    with _lock:
        if _process is not None and _process.poll() is None:
            return "El backend ya está corriendo."

        log_file = open(config.LOG_PATH, "a", encoding="utf-8")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        _process = subprocess.Popen(
            [config.BACKEND_PYTHON, "run.py"],
            cwd=str(config.BACKEND_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        pid = _process.pid
    return f"Backend iniciado (pid {pid})."


def stop() -> str:
    global _process
    with _lock:
        proc = _process
        if proc is None or proc.poll() is not None:
            _process = None
            return "El backend no estaba corriendo."

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        pid = proc.pid
        _process = None
    return f"Backend detenido (pid {pid})."
