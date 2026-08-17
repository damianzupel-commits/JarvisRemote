"""Tool `opencode_run_task` -- delega una tarea de escritura/edición de código
a la CLI de OpenCode (github.com/sst/opencode, MIT) en vez de al loop de
agente propio de Jarvis (app/agent.py). Pensado para tareas de generación de
código pesadas/largas (crear un proyecto entero, no un solo archivo chico),
donde el loop agéntico dedicado de OpenCode (con su propio manejo de
tool-calling iterativo, edición de diffs, etc.) puede ser más consistente que
dejar que el agente general de Jarvis improvise llamadas a fs_write_file una
por una.

Apunta al MISMO Ollama local que ya sirve jarvis-text-v2 (ver provider
"jarvis-ollama" en ~/.config/opencode/opencode.json, baseURL
http://127.0.0.1:11434/v1 -- confirmado real via backend/.env
LMSTUDIO_BASE_URL) a propósito: usar el mismo modelo aísla la variable que
importa comparar (el harness/loop de OpenCode vs. el de Jarvis), en vez de
mezclarla con un cambio de modelo. No hay un modelo más "apto para código"
disponible en este Ollama local (ver `ollama list` real 2026-08-11: solo
variantes de jarvis-text, ninguna especializada en código tipo
Qwen2.5-Coder/DeepSeek-Coder).

Mismo criterio de guardrails que pc_run_command (app/tools/pc_command.py):
gateado por PC_SHELL_ENABLED (esto ejecuta un binario externo que a su vez
escribe archivos y puede correr shell commands propios, target="pc",
auditoría persistente de cada intento) + cwd resuelto con el mismo sandbox
de app/tools/filesystem.py (_resolve, relativo a FS_ALLOWED_ROOT). A
diferencia de pc_run_command, el timeout tiene un techo mucho más alto
(OPENCODE_MAX_TIMEOUT_SECONDS, 1h): una tarea de código real con un modelo
local de 30B corriendo un loop agéntico propio (varias llamadas secuenciales,
no una sola) puede tardar bastante más que cualquier comando de shell
individual -- mismo espíritu que LLM_REQUEST_TIMEOUT_SECONDS en config.py,
generoso a propósito.

Se corre con `--auto` (auto-aprueba los permisos de OpenCode: escritura de
archivos, comandos de shell que el propio OpenCode decida correr) porque no
hay un humano interactivo del lado de esta tool call para aprobar uno por
uno -- el guardrail real es el gate de arriba (PC_SHELL_ENABLED) más el
directorio acotado (cwd sandboxeado), no una aprobación manual por acción
dentro de OpenCode.
"""

import logging
import subprocess
from pathlib import Path

from .. import audit_log
from ..config import settings
from ..shell_exec import kill_process_tree, truncate_output
from . import register_tool
from .fabric_reference import FABRIC_MOD_REFERENCE
from .filesystem import _resolve

logger = logging.getLogger("jarvis.opencode")

_DEFAULT_TIMEOUT_SECONDS = 1800.0
_MAX_TIMEOUT_SECONDS = 3600.0


class PcShellDisabled(RuntimeError):
    pass


class OpenCodeNotInstalled(RuntimeError):
    pass


def _snapshot(root: Path) -> dict[str, tuple[int, float]]:
    if not root.is_dir():
        return {}
    snapshot = {}
    for path in root.rglob("*"):
        if path.is_file():
            stat = path.stat()
            snapshot[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime)
    return snapshot


def _diff_snapshots(before: dict[str, tuple[int, float]], after: dict[str, tuple[int, float]]) -> dict:
    created = sorted(p for p in after if p not in before)
    modified = sorted(p for p in after if p in before and after[p] != before[p])
    return {"created": created, "modified": modified}


@register_tool(
    name="opencode_run_task",
    description=(
        "Delega una tarea de escritura/edición de código a la CLI de OpenCode (github.com/sst/opencode), "
        "apuntada al mismo modelo local que ya usa Jarvis (Ollama, jarvis-text-v2) pero corrida con SU "
        "PROPIO loop agéntico en vez del de Jarvis -- usala para tareas de generación de código grandes/"
        "autocontenidas (crear un proyecto entero desde cero: varios archivos, estructura de carpetas, "
        "un build.gradle, etc.), no para ediciones puntuales chicas (para eso usá fs_write_file o "
        "code_apply_fix directamente, son más rápidas). Recibe una descripción de la tarea en lenguaje "
        "natural y un directorio de trabajo (se crea si no existe); OpenCode corre ahí adentro con "
        "permisos auto-aprobados (--auto, no hay aprobación manual paso a paso) y devuelve stdout/stderr/"
        "exit_code de la CLI más la lista real de archivos creados/modificados (comparando el directorio "
        "antes y después de correr). Puede tardar varios minutos -- es un modelo local de 30B corriendo "
        "su propio loop de varias llamadas, no una sola generación. Para tareas de mods de Fabric/Minecraft, "
        "pasá fabric_reference=true -- inyecta una referencia curada y VERIFICADA contra fuente real de "
        "AttackEntityCallback/StatusEffect/registro de items/fabric.mod.json/Gradle Loom en la descripción "
        "de la tarea, en vez de dejar que el modelo dependa de su propia memoria (que ya inventó la clase "
        "del evento de ataque dos veces: una vez el propio loop de Jarvis, otra vez OpenCode sin esta "
        "referencia)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Descripción en lenguaje natural de la tarea de código a delegar a OpenCode.",
            },
            "cwd": {
                "type": "string",
                "description": (
                    "Directorio de trabajo, relativo a la raíz permitida (se crea si no existe)."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": (
                    f"Segundos a esperar antes de matar el proceso (default {_DEFAULT_TIMEOUT_SECONDS:.0f}, "
                    f"tope duro {_MAX_TIMEOUT_SECONDS:.0f})."
                ),
            },
            "model": {
                "type": "string",
                "description": (
                    "Modelo en formato provider/model (default: settings.opencode_default_model, "
                    "jarvis-ollama/jarvis-text-v2)."
                ),
            },
            "fabric_reference": {
                "type": "boolean",
                "description": (
                    "Si es true, antepone a 'task' una referencia curada y verificada de Fabric API/Loom "
                    "(AttackEntityCallback, StatusEffect, registro de items, fabric.mod.json, Gradle) -- "
                    "usalo para cualquier tarea de mods de Minecraft/Fabric. Default false."
                ),
            },
        },
        "required": ["task", "cwd"],
    },
)
def opencode_run_task(
    task: str,
    cwd: str,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    model: str | None = None,
    fabric_reference: bool = False,
) -> dict:
    arguments = {"task": task, "cwd": cwd, "timeout": timeout, "model": model, "fabric_reference": fabric_reference}
    # Bug real 2026-08-12: el CLI parser de OpenCode (yargs) interpreta un
    # mensaje que EMPIEZA con "-"/"--" como un flag desconocido en vez de
    # texto -- devuelve el usage/help y sale con exit_code=1 al instante, sin
    # llegar a procesar nada (verificado con un binary-search real: el mismo
    # texto con guiones en el medio corre bien, el mismo texto empezando con
    # "---" falla siempre, sin importar la longitud). FABRIC_MOD_REFERENCE
    # arranca con "--- Referencia curada..." a propósito (se lee bien como
    # nota independiente) -- por eso 'task' va PRIMERO acá, nunca al revés.
    effective_task = f"{task}\n\n{FABRIC_MOD_REFERENCE}" if fabric_reference else task

    if not settings.pc_shell_enabled:
        error = "Ejecución de comandos en la PC deshabilitada. Setear PC_SHELL_ENABLED=true en backend/.env para habilitarla."
        audit_log.log_tool_call(target="pc", tool="opencode_run_task", arguments=arguments, error=error)
        raise PcShellDisabled(error)

    opencode_bin = Path(settings.opencode_bin_path)
    if not opencode_bin.is_file():
        error = (
            f"No se encontró el binario de OpenCode en '{opencode_bin}'. Instalarlo con "
            "`curl -fsSL https://opencode.ai/install | bash` (o setear OPENCODE_BIN_PATH si quedó en otro lado)."
        )
        audit_log.log_tool_call(target="pc", tool="opencode_run_task", arguments=arguments, error=error)
        raise OpenCodeNotInstalled(error)

    work_dir = _resolve(cwd)
    work_dir.mkdir(parents=True, exist_ok=True)

    effective_timeout = min(float(timeout), _MAX_TIMEOUT_SECONDS)
    effective_model = model or settings.opencode_default_model

    before = _snapshot(work_dir)

    command = [
        str(opencode_bin), "run", effective_task,
        "--dir", str(work_dir),
        "--auto",
        "-m", effective_model,
    ]
    logger.info("opencode_run_task: dir=%s model=%s timeout=%s", work_dir, effective_model, effective_timeout)

    proc = subprocess.Popen(
        command,
        cwd=str(work_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=effective_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_tree(proc.pid)
        stdout, stderr = proc.communicate()

    after = _snapshot(work_dir)
    stdout, stdout_truncated = truncate_output(stdout)
    stderr, stderr_truncated = truncate_output(stderr)

    result = {
        "task": task,
        "cwd": str(work_dir),
        "model": effective_model,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "files": _diff_snapshots(before, after),
    }
    audit_log.log_tool_call(target="pc", tool="opencode_run_task", arguments=arguments, result=result)
    return result
