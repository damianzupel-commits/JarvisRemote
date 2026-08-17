"""Logger de auditoría estructurado (JSON por línea, con rotación por tamaño),
separado del logging general de la app (`logging_config.py`).

El logging general (via `logger.info`/`logger.warning` en `phone_link.py` y
`tools/desktop.py`) es texto libre pensado para diagnosticar en vivo mientras
se mira la consola/tray — mezcla todos los subsistemas y niveles, y no
persiste salvo que se corra vía la tray-app (ver `tray-app/process_manager.py`).

Este módulo es aparte, pensado específicamente para poder responder después
"qué hizo Jarvis mientras no miraba": cada tool call de `target=phone`
(`phone_link.dispatch_to_phone`) y de escritorio (`tools/desktop._audited`)
queda acá, una línea JSON por evento, con timestamp UTC, el tool, sus
argumentos, y el resultado o el error — fácil de grepear/parsear con `jq` o
similar, a diferencia del log de texto libre.

Rota por tamaño (5 MB x 5 archivos = 25 MB tope) para no crecer sin límite.
"""

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent / "audit.log"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5

_audit_logger = logging.getLogger("jarvis.audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False  # no duplicar estas líneas en el log general/consola

if not _audit_logger.handlers:
    _handler = logging.handlers.RotatingFileHandler(
        _AUDIT_LOG_PATH, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(_handler)


def log_tool_call(
    *,
    target: str,
    tool: str,
    arguments: dict[str, Any],
    result: Any = None,
    error: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """Registra un tool call de `target` ("phone", "desktop", "fs", o "agent" --
    ver `agent.py::run_agent`, que loguea acá TODO tool call del loop general,
    bloqueado o no) como una línea JSON.

    `conversation_id` es opcional (solo lo manda `run_agent`, que sí conoce la
    conversación) -- pensado para que `app/introspection/analyzer.py` pueda
    agrupar los tool calls de una misma sesión y detectar patrones de falla
    que solo tienen sentido dentro de una conversación (ej. un archivo
    bloqueado que nunca se reintenta DENTRO de esa misma sesión).

    Nunca lanza: un fallo de auditoría (ej. algo no serializable) no debe romper
    la tool call real — en el peor caso se pierde esa línea de auditoría, se
    loguea el fallo en el logger general, y se sigue.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "tool": tool,
        "arguments": arguments,
        "ok": error is None,
    }
    if conversation_id is not None:
        entry["conversation_id"] = conversation_id
    if error is not None:
        entry["error"] = error
    else:
        entry["result"] = result
    try:
        _audit_logger.info(json.dumps(entry, ensure_ascii=False, default=str))
    except Exception:
        logging.getLogger("jarvis.audit_log_internal").warning(
            "No se pudo escribir la línea de auditoría para tool=%s", tool, exc_info=True
        )


def read_entries(
    target: str | None = None, tool: str | None = None, conversation_id: str | None = None
) -> list[dict]:
    """Lee de vuelta las entradas ya loggeadas (solo el archivo actual, no los
    rotados `.1`/`.2`/...), opcionalmente filtradas por target/tool/conversation_id
    -- usado por `audit_report.generate_report` para saber qué fixes/ediciones ya
    se aplicaron de verdad a un proyecto, y por `app/introspection/analyzer.py`
    para reconstruir la secuencia de tool calls de una sesión puntual. Tolera
    líneas corruptas (las salta): un log parcialmente dañado no debe romper a
    quien lo esté leyendo."""
    if not _AUDIT_LOG_PATH.is_file():
        return []
    entries = []
    for line in _AUDIT_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if target is not None and entry.get("target") != target:
            continue
        if tool is not None and entry.get("tool") != tool:
            continue
        if conversation_id is not None and entry.get("conversation_id") != conversation_id:
            continue
        entries.append(entry)
    return entries
