"""Tool de shell real en la PC (`pc_run_command`) -- análogo directo de
`phone_run_command` (`app/tools/phone.py` + `app/phone_link.py`) pero
ejecutado en-proceso acá en el backend, en vez de despachado al celular por
WebSocket.

Mismo criterio de guardrails que ya usa el resto del proyecto para acciones
sensibles: flag de habilitación (`PC_SHELL_ENABLED`, ver `config.py`) +
blocklist de patrones obviamente destructivos por matching de texto (mismo
espíritu que `phone_link._check_command_blocklist` y
`desktop._check_launch_blocklist`, NO un sandbox real) + auditoría persistente
de cada intento (`audit_log`, target="pc"). No hay gate de confirm=true como
en `code_apply_fix`: ese patrón es para previsualizar un diff idempotente
antes de escribirlo, y no tiene un análogo razonable para un comando de shell
(no hay "diff" que mostrar de antemano para `pytest` o `pip install`) --
`phone_run_command`, el tool más parecido en espíritu (shell arbitrario), ya
sigue el patrón de flag+blocklist+auditoría sin confirm, así que este tool
sigue el mismo.

El directorio de trabajo (`cwd`) se resuelve con el mismo sandbox que
`filesystem._resolve` (relativo a `FS_ALLOWED_ROOT`, o absoluto si cae
adentro) -- reusa esa función en vez de reimplementar el chequeo de límites,
para no tener dos implementaciones del mismo boundary que puedan divergir.
"""

import logging
import re

from .. import audit_log
from ..config import settings
from ..shell_exec import MAX_TIMEOUT_SECONDS as _MAX_TIMEOUT_SECONDS
from ..shell_exec import run_shell_command
from . import register_tool
from .filesystem import _resolve

logger = logging.getLogger("jarvis.pc_shell")

_DEFAULT_TIMEOUT_SECONDS = 120.0


class PcShellDisabled(RuntimeError):
    pass


class DestructivePcCommandBlockedError(PermissionError):
    """El comando matcheó el blocklist de patrones obviamente destructivos."""


# Blocklist de "evitar el desastre obvio" para pc_run_command -- mitigación
# por matching de texto, NO una garantía de seguridad completa: cualquier
# comando que no matchee ninguno de estos patrones se ejecuta igual, sin
# restricciones adicionales. Cubre tanto utilidades nativas de Windows
# (cmd/PowerShell, lo que de verdad va a usar esta tool en la práctica) como
# los equivalentes de bash/WSL/git-bash (por si el usuario los tiene
# instalados y el modelo los usa) -- mismo criterio que
# `phone_link._check_command_blocklist` y
# `desktop._check_launch_blocklist`, comparado sobre el comando en minúsculas
# con espacios repetidos colapsados.
_DESTRUCTIVE_COMMAND_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("format (formatear un disco)", re.compile(r"\bformat(\.com)?\b")),
    ("diskpart (partición de discos)", re.compile(r"\bdiskpart(\.exe)?\b")),
    ("cipher /w (borrado seguro de espacio libre)", re.compile(r"\bcipher\b[^\n]*\s/w\b")),
    ("vssadmin delete (borra shadow copies/backups)", re.compile(r"\bvssadmin\b[^\n]*\bdelete\b")),
    ("bcdedit (config de arranque)", re.compile(r"\bbcdedit(\.exe)?\b")),
    (
        "shutdown/reinicio/cierre de sesión forzado de la PC",
        re.compile(r"\bshutdown\b[^\n]*(/s|/r|/l|-s\b|-r\b)"),
    ),
    (
        "rmdir /s o del /f /s /q sobre una unidad completa",
        re.compile(r"\b(rmdir|rd|del|erase)\b[^\n]*\s/s\b[^\n]*\b[a-z]:\\?\s*($|[\\\"'])"),
    ),
    (
        "Remove-Item recursivo/forzado sobre la raíz o el home (PowerShell)",
        re.compile(r"remove-item[^\n]*-recurse[^\n]*-force[^\n]*(\$env:userprofile|~|[a-z]:\\\s*($|[\"']))"),
    ),
    (
        "rm -rf sobre la raíz o el home (bash/WSL/git-bash)",
        re.compile(r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+(/|~|\$home)(\s|/\*|$)"),
    ),
    ("mkfs (formatear un filesystem)", re.compile(r"\bmkfs(\.\w+)?\b")),
    ("dd escribiendo directo a un block device", re.compile(r"\bdd\b[^\n]*\bof=/dev/")),
    ("fork bomb (bash)", re.compile(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:.*&.*\}\s*;\s*:")),
    ("fork bomb (batch de Windows, %0|%0)", re.compile(r"%0\s*\|\s*%0")),
]


def _check_command_blocklist(command: str) -> None:
    normalized = " ".join(command.lower().split())
    for name, pattern in _DESTRUCTIVE_COMMAND_PATTERNS:
        if pattern.search(normalized):
            logger.warning("pc_shell: comando BLOQUEADO (%s): %r", name, command)
            raise DestructivePcCommandBlockedError(
                f"Comando rechazado por el blocklist de seguridad (patrón: {name}). "
                "Es una mitigación de 'evitar el desastre obvio' por matching de texto, "
                "no un sandbox real -- si de verdad hace falta correr esto, hacelo a mano."
            )


@register_tool(
    name="pc_run_command",
    description=(
        "Ejecuta un comando de shell REAL en la PC del usuario (vía cmd.exe en Windows, 'shell -c' "
        "equivalente en otros sistemas) -- análogo de phone_run_command pero del lado de la PC. Es el "
        "nivel más invasivo posible de las tools de PC: código/comandos arbitrarios, no solo archivos o "
        "control de UI -- usalo para lo que necesite un intérprete o herramientas de línea de comandos "
        "de verdad: instalar dependencias (pip install, npm install), correr tests (pytest, npm test) "
        "después de escribir código con fs_write_file, git, o cualquier otro comando real. El directorio "
        "de trabajo (cwd) se resuelve igual que en las tools de filesystem: relativo a la raíz permitida "
        "(FS_ALLOWED_ROOT), o '.' para esa raíz -- no se puede correr por fuera de esa carpeta. Devuelve "
        "stdout, stderr, exit_code y timed_out. Hay un blocklist de patrones obviamente destructivos "
        "(formatear/particionar discos, borrado recursivo de una unidad completa o el home, apagar o "
        "reiniciar la PC, fork bombs) que rechaza el comando antes de correrlo -- es una mitigación de "
        "'evitar el desastre obvio' por matching de texto, NO un sandbox real ni una garantía de "
        "seguridad completa: cualquier comando que no matchee esos patrones se ejecuta igual, sin "
        "restricciones adicionales, así que no lo uses para nada que el usuario no haya pedido. Si un "
        "comando se cuelga, se lo mata (a él y a sus subprocesos) al llegar al timeout y se devuelve la "
        "salida parcial con timed_out=true en vez de esperar para siempre."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Comando de shell a ejecutar (se corre como 'cmd.exe /c <command>' en Windows).",
            },
            "cwd": {
                "type": "string",
                "description": "Directorio de trabajo, relativo a la raíz permitida (default '.', la raíz).",
            },
            "timeout": {
                "type": "integer",
                "description": (
                    f"Segundos a esperar antes de matar el comando (default {_DEFAULT_TIMEOUT_SECONDS:.0f}, "
                    f"tope duro {_MAX_TIMEOUT_SECONDS:.0f} sin importar lo que se pida)."
                ),
            },
        },
        "required": ["command"],
    },
)
def pc_run_command(command: str, cwd: str = ".", timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> dict:
    arguments = {"command": command, "cwd": cwd, "timeout": timeout}

    if not settings.pc_shell_enabled:
        error = "Ejecución de comandos en la PC deshabilitada. Setear PC_SHELL_ENABLED=true en backend/.env para habilitarla."
        audit_log.log_tool_call(target="pc", tool="pc_run_command", arguments=arguments, error=error)
        raise PcShellDisabled(error)

    try:
        _check_command_blocklist(command)
    except DestructivePcCommandBlockedError as exc:
        audit_log.log_tool_call(target="pc", tool="pc_run_command", arguments=arguments, error=str(exc))
        raise

    work_dir = _resolve(cwd)
    if not work_dir.is_dir():
        error = f"El directorio de trabajo '{cwd}' no existe o no es una carpeta ({work_dir})."
        audit_log.log_tool_call(target="pc", tool="pc_run_command", arguments=arguments, error=error)
        raise NotADirectoryError(error)

    result = run_shell_command(command, work_dir, timeout)
    audit_log.log_tool_call(target="pc", tool="pc_run_command", arguments=arguments, result=result)
    return result
