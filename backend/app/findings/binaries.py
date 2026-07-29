"""Helpers de proceso compartidos por los wrappers de escáneres/analizadores
externos reales (`security/scanners.py`, `quality/scanners.py`): ubicar el
binario de una herramienta y convertir rutas absolutas en relativas al
proyecto."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def tool_path(name: str) -> str | None:
    """Busca el binario en PATH primero; si no aparece, prueba junto al
    intérprete Python actual (venv/Scripts) -- cubre el caso en que el backend
    corre desde un venv cuyo Scripts/ no llegó a exportarse al PATH del proceso
    padre (ej. lanzado por la tray-app)."""
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(sys.executable).parent / f"{name}.exe"
    if candidate.is_file():
        return str(candidate)
    candidate = Path(sys.executable).parent / name
    if candidate.is_file():
        return str(candidate)
    return None


def node_shim_argv(exe: str, package_name: str, bin_name: str) -> list[str] | None:
    """En Windows, los binarios globales de npm (ESLint, tsc) son shims
    `.CMD` que internamente invocan node -- pasárselos directo a
    `subprocess.run([exe, ...])` (sin `shell=True`) se cuelga indefinidamente
    en cuanto la lista de argumentos crece (confirmado real y reproducible:
    ESLint sobre los 40 archivos JS de NodeGoat, timeout de 120s; invocar
    `node.exe` directo sobre el script real de ESLint con los mismos
    argumentos tardó 0.6s). El fix es saltear el shim: resolver el script real
    vía el campo `bin` del `package.json` del paquete (no parseando el .cmd
    generado, que cambia de formato entre versiones de npm) e invocarlo con
    `node.exe` directo. Devuelve `None` si `exe` no es un shim de Windows (en
    Linux/Mac los binarios de npm son symlinks ejecutables normales, no hace
    falta este rodeo) o si no se pudo resolver."""
    if not exe.lower().endswith((".cmd", ".bat")):
        return None
    shim_dir = Path(exe).resolve().parent
    pkg_json = shim_dir / "node_modules" / package_name / "package.json"
    if not pkg_json.is_file():
        return None
    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    bin_field = pkg.get("bin")
    if isinstance(bin_field, dict):
        script_rel = bin_field.get(bin_name)
    elif isinstance(bin_field, str):
        script_rel = bin_field
    else:
        script_rel = None
    if not script_rel:
        return None
    script_path = (shim_dir / "node_modules" / package_name / script_rel).resolve()
    if not script_path.is_file():
        return None
    node_exe = tool_path("node")
    if node_exe is None:
        return None
    return [node_exe, str(script_path)]


def relpath(root: Path, absolute: str) -> str:
    try:
        return Path(absolute).resolve().relative_to(root).as_posix()
    except ValueError:
        return Path(absolute).as_posix()


# Límite conservador de longitud total (en caracteres) para un lote de rutas
# pasadas como argumentos de línea de comando -- Windows soporta hasta ~32k en
# CreateProcess, pero varios subsistemas intermedios (cmd.exe, algunos shims)
# tienen límites más bajos; 20k deja margen real de sobra. Confirmado real:
# `bandit <743 rutas absolutas>` sobre un repo grande (SuperSaaSFastAPI, 2026-07-29)
# tiraba `FileNotFoundError: [WinError 206] El nombre del archivo o la
# extensión es demasiado largo` -- CreateProcess rechazando la línea de
# comando completa, no un archivo puntual (el mensaje de Windows es engañoso).
_MAX_BATCH_CHARS = 20000


def chunk_paths(paths: list[str], max_chars: int = _MAX_BATCH_CHARS) -> list[list[str]]:
    """Divide una lista de rutas absolutas en lotes que se mantienen por
    debajo de `max_chars` en total -- para pasarle a un escáner en varias
    invocaciones en vez de una sola línea de comando gigante. Afecta a
    cualquier wrapper que arme `cmd = [exe, *absolute_files, ...]`
    (bandit/ruff/mypy/eslint); Semgrep no lo necesita porque escanea el
    directorio raíz de una sola pasada, no archivo por archivo."""
    batches: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for p in paths:
        p_len = len(p) + 1  # +1 por el espacio/separador entre argumentos
        if current and current_len + p_len > max_chars:
            batches.append(current)
            current = []
            current_len = 0
        current.append(p)
        current_len += p_len
    if current:
        batches.append(current)
    return batches
