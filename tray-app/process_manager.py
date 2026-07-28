"""Arranca/para el backend como subproceso y le manda stdout+stderr a un log file."""

import subprocess
import sys
import threading

import config

_process: subprocess.Popen | None = None
_lock = threading.Lock()


def _find_listening_pid(port: int) -> int | None:
    """Busca qué PID tiene el puerto del backend en LISTENING, sin asumir que
    coincide con `_process` -- durante desarrollo el backend se reinició muchas
    veces a mano (por fuera de la tray), así que `_process` no siempre refleja
    el proceso real corriendo. Sin esto, `stop()`/`start()` podían terminar
    lanzando un segundo backend compitiendo por el mismo puerto."""
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"], text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        return None
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
            try:
                return int(parts[-1])
            except ValueError:
                continue
    return None


def is_running() -> bool:
    with _lock:
        if _process is not None and _process.poll() is None:
            return True
        return _find_listening_pid(config.PORT) is not None


def start() -> str:
    global _process
    with _lock:
        if _process is not None and _process.poll() is None:
            return "El backend ya está corriendo."
        if _find_listening_pid(config.PORT) is not None:
            return "El backend ya está corriendo (proceso externo, no lanzado por esta tray)."

        log_file = open(config.LOG_PATH, "a", encoding="utf-8")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        _process = subprocess.Popen(
            [config.BACKEND_PYTHON, "run.py"],
            cwd=str(config.BACKEND_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            # Sin esto, el backend hereda el stdin de la tray (pythonw.exe, sin
            # consola en absoluto) -- un handle de stdin inválido/heredado de una
            # cadena sin consola rompe el spawn de subprocesos DEL BACKEND, como
            # el que hace Playwright para lanzar Chromium (browser_open fallaba
            # 100% de las veces con "BrowserType.launch: spawn UNKNOWN", bug real
            # encontrado el 26/07 durante las pruebas de voz). DEVNULL le da al
            # backend un stdin válido y vacío en vez de uno heredado y roto.
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        pid = _process.pid
    return f"Backend iniciado (pid {pid})."


def stop() -> str:
    global _process
    with _lock:
        proc = _process
        _process = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            return f"Backend detenido (pid {proc.pid})."

        # `_process` no coincide con la realidad (reinicio manual durante
        # desarrollo, u otra instancia de la tray) -- verificar por el puerto
        # real antes de reportar "no estaba corriendo".
        pid = _find_listening_pid(config.PORT)
        if pid is not None:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
            )
            return f"Backend detenido (pid {pid})."
        return "El backend no estaba corriendo."


def set_active_model(model_id: str) -> str:
    """Cambia el modelo activo del backend: reescribe LMSTUDIO_MODEL en
    backend/.env y reinicia el proceso para que lo tome (el backend lee el .env
    una sola vez, al arrancar). Usado por el selector de modelo de la UI."""
    lines = config.ENV_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("LMSTUDIO_MODEL="):
            new_lines.append(f"LMSTUDIO_MODEL={model_id}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"LMSTUDIO_MODEL={model_id}")
    config.ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    stop()
    return start()
