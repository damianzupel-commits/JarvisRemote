"""Modos de operación de Jarvis: SUPERVISADO vs AUTÓNOMO (agregado 2026-08-19).

Resuelve la tensión potencia-vs-seguridad para poder "dar vuelta la relación"
(que Jarvis trabaje solo) sin que un modo desatendido tenga el mismo radio de
daño que una sesión donde Damian está mirando en vivo.

- SUPERVISADO (attended): hay un humano usando Jarvis en vivo (chat/voz). El
  sandbox de filesystem se ABRE al root amplio (HOME o el que Damian configure,
  ver Settings.fs_supervised_roots). Es el comportamiento potente de siempre:
  cuando Damian está presente para frenar una macana, no pierde capacidad.
- AUTÓNOMO (unattended): Jarvis corre solo (tareas programadas, CLIs corridas
  por scheduler, self-repair desatendido, el bucle nocturno, futuras misiones
  remotas). El sandbox se ACOTA al chico (raíz del proyecto + FS_ALLOWED_ROOTS,
  ver Settings.fs_allowed_roots). Radio de daño limitado.

DISEÑO CLAVE -- FAIL-SAFE:
- El default del PROCESO es AUTÓNOMO (el más restrictivo). Solo los puntos de
  entrada interactivos (el endpoint de chat/voz con un humano) DECLARAN
  explícitamente SUPERVISADO por-invocación (ver operating_as). Cualquier
  entrada que NO lo declare -- una tarea programada, una CLI, un loop de fondo,
  un punto de entrada nuevo que alguien agregue en el futuro y se olvide de
  setear el modo -- queda AUTÓNOMA por omisión. Nunca se abre de más "por las
  dudas".
- El modo vive en un ContextVar, no en una global: se setea por-invocación y no
  se filtra entre tareas asyncio concurrentes (dos requests simultáneas, una de
  un humano y otra de un job, no se pisan el modo).

GUARDRAIL ANTI-AUTO-ESCALADA:
- El modo AUTÓNOMO NUNCA puede escalar a SUPERVISADO desde ADENTRO de un turno
  del agente. O sea: Jarvis no puede ampliarse sus propios permisos de
  filesystem en runtime. El único que abre el sandbox es un punto de entrada
  de confianza (código del server), ANTES de arrancar el loop del agente. No
  hay ninguna tool registrada que cambie el modo, y por si acaso operating_as
  rechaza en código todo intento de escalar mientras hay un turno del agente en
  curso (ver _agent_turn_active / operating_as).
"""

import enum
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

logger = logging.getLogger("jarvis.operation_mode")


class OperationMode(enum.Enum):
    """Los dos modos. El valor string es el que se usa en env/logs."""

    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


# Env var que fija el default del PROCESO. A propósito, si está vacía o tiene un
# valor no reconocido, se cae a AUTÓNOMO (el restrictivo) -- nunca a SUPERVISADO
# por accidente de tipeo. En operación normal NO hace falta setearla: el server
# de chat declara SUPERVISADO por-invocación y el resto queda AUTÓNOMO solo.
_ENV_VAR = "JARVIS_OPERATION_MODE"


def _env_default_mode() -> OperationMode:
    raw = (os.getenv(_ENV_VAR) or "").strip().lower()
    if raw in ("supervised", "attended", "supervisado"):
        return OperationMode.SUPERVISED
    if raw and raw not in ("autonomous", "unattended", "autonomo", "autónomo"):
        logger.warning(
            "%s='%s' no reconocido; usando AUTONOMOUS (fail-safe restrictivo).",
            _ENV_VAR,
            raw,
        )
    return OperationMode.AUTONOMOUS


# Modo default del proceso, derivado del env una sola vez. El ContextVar arranca
# con este valor y cada punto de entrada puede sobreescribirlo por-invocación.
_DEFAULT_MODE: OperationMode = _env_default_mode()

_current_mode: ContextVar[OperationMode] = ContextVar("jarvis_operation_mode", default=_DEFAULT_MODE)

# Flag por-contexto que marca "hay un turno del agente corriendo ACÁ". Lo prende
# el wrapper del loop del agente (ver agent._run_agent_turn / agent_turn_active).
# Sirve SOLO para el guardrail anti-auto-escalada de operating_as: si esto está
# en True y algo intenta escalar a SUPERVISADO, se rechaza (sería Jarvis
# ampliándose los permisos a sí mismo).
_agent_turn_active: ContextVar[bool] = ContextVar("jarvis_agent_turn_active", default=False)


def current_mode() -> OperationMode:
    """El modo de operación efectivo en este contexto de ejecución."""
    return _current_mode.get()


def is_supervised() -> bool:
    return current_mode() is OperationMode.SUPERVISED


def is_autonomous() -> bool:
    return current_mode() is OperationMode.AUTONOMOUS


def effective_fs_roots() -> list[str]:
    """Las raíces de filesystem permitidas SEGÚN EL MODO actual. Es el puente
    entre el modo y el sandbox ya existente (app/tools/filesystem.py::_resolve
    lo consume vía _allowed_roots, sin duplicar el choke point):

    - SUPERVISADO -> Settings.fs_supervised_roots (root amplio: HOME o el que
      Damian configure, + las raíces del sandbox chico). Potencia de siempre.
    - AUTÓNOMO    -> Settings.fs_allowed_roots (proyecto + FS_ALLOWED_ROOTS).
      Sandbox acotado.

    Import perezoso de settings para no acoplar el orden de import (config no
    depende de este módulo)."""
    from .config import settings

    if current_mode() is OperationMode.SUPERVISED:
        return settings.fs_supervised_roots
    return settings.fs_allowed_roots


@contextmanager
def operating_as(mode: OperationMode, *, source: str) -> Iterator[OperationMode]:
    """Declara el modo de operación para la duración de este bloque. Lo usan los
    PUNTOS DE ENTRADA (código de confianza), no las tools ni el agente.

    `source` es una etiqueta legible del punto de entrada (ej. "http_chat",
    "scheduler", "cli") -- se loguea, para que quede claro y auditable en qué
    modo arrancó cada invocación y con qué roots efectivos.

    GUARDRAIL: no se puede ESCALAR (AUTÓNOMO -> SUPERVISADO) mientras hay un
    turno del agente en curso (_agent_turn_active=True). Los puntos de entrada
    legítimos declaran el modo ANTES de arrancar el loop del agente, así que no
    los afecta; lo que esto bloquea es que algo DENTRO del loop (una tool, el
    propio modelo por alguna vía) intente ampliar los permisos en runtime. Es
    defensa en profundidad: no hay ninguna tool que cambie el modo, y además
    esto lo rechaza en código."""
    if (
        mode is OperationMode.SUPERVISED
        and _current_mode.get() is OperationMode.AUTONOMOUS
        and _agent_turn_active.get()
    ):
        raise PermissionError(
            "Auto-escalada de modo bloqueada: no se puede pasar de AUTÓNOMO a "
            "SUPERVISADO desde dentro de un turno del agente. El modo lo fija el "
            "punto de entrada, no Jarvis en runtime."
        )

    token = _current_mode.set(mode)
    try:
        # Se loguea SIEMPRE en qué modo arranca y con qué roots efectivos.
        logger.info(
            "Modo de operación: %s (fuente=%s). Roots de filesystem efectivos: %s",
            mode.value,
            source,
            effective_fs_roots(),
        )
        yield mode
    finally:
        _current_mode.reset(token)


@contextmanager
def agent_turn_active() -> Iterator[None]:
    """Marca que un turno del agente está corriendo en este contexto. Lo usa el
    wrapper del loop (agent._run_agent_turn). Habilita el guardrail
    anti-auto-escalada de operating_as. No cambia el modo; solo prende el flag."""
    token = _agent_turn_active.set(True)
    try:
        yield
    finally:
        _agent_turn_active.reset(token)


# Log de arranque: deja registrado el default del proceso apenas se importa el
# módulo (queda en el log del backend al levantar). El modo efectivo real de
# cada invocación lo loguea operating_as / el loop del agente.
logger.info(
    "operation_mode cargado. Default del proceso: %s (env %s=%r).",
    _DEFAULT_MODE.value,
    _ENV_VAR,
    os.getenv(_ENV_VAR),
)
