import logging
import logging.handlers
from pathlib import Path

# Bug real 2026-08-10 (informe de arquitectura de esa sesión, confirmado
# leyendo el docstring de audit_log.py): basicConfig sin `filename=` manda
# TODO el logging general (jarvis.main, jarvis.phone_link, etc.) solo a
# stderr -- no persiste en ningún archivo salvo que quien lo arranque
# redirija stdout a mano, que es justo lo que hace tray-app/process_manager.py
# (y por eso "andaba" en la práctica, pero solo cuando se arranca vía tray).
# Arrancado de cualquier otra forma (terminal manual, tarea programada,
# systemd-equivalent), ese log se pierde. Mismo patrón que audit_log.py
# (RotatingFileHandler, 5MB x 5 = 25MB tope) pero SIN el propagate=False de
# ese módulo -- acá sí queremos que además siga saliendo por consola cuando
# se corre interactivo, la novedad es que TAMBIÉN quede en un archivo,
# siempre, sin importar cómo se arrancó el proceso.
_LOG_PATH = Path(__file__).resolve().parent.parent / "general.log"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5


def configure_logging() -> None:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=[stream_handler, file_handler])
