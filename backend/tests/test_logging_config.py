"""Tests de app/logging_config.py -- bug real (informe de arquitectura
2026-08-10, corregido vía Opción C 2026-08-11): logging.basicConfig sin
filename= no persistía el log general en ningún archivo salvo que quien
arrancara el proceso redirigiera stdout a mano (lo que hacía tray-app,
por eso "andaba" solo así). Ahora agrega un RotatingFileHandler real."""

from __future__ import annotations

import logging
import logging.handlers

import pytest

from app import logging_config


@pytest.fixture(autouse=True)
def _reset_root_logger():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    for h in original_handlers:
        root.addHandler(h)
    root.setLevel(original_level)


def test_configure_logging_adds_a_file_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "_LOG_PATH", tmp_path / "general.log")

    logging_config.configure_logging()

    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(file_handlers) == 1


def test_configure_logging_keeps_a_stream_handler_too(tmp_path, monkeypatch):
    """No debe perderse la salida por consola -- solo se agrega persistencia,
    no se reemplaza el comportamiento interactivo existente."""
    monkeypatch.setattr(logging_config, "_LOG_PATH", tmp_path / "general.log")

    logging_config.configure_logging()

    root = logging.getLogger()
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(stream_handlers) == 1


def test_configure_logging_actually_persists_a_log_line_to_disk(tmp_path, monkeypatch):
    log_path = tmp_path / "general.log"
    monkeypatch.setattr(logging_config, "_LOG_PATH", log_path)

    logging_config.configure_logging()
    logging.getLogger("jarvis.main").info("mensaje de prueba real")

    assert log_path.is_file()
    assert "mensaje de prueba real" in log_path.read_text(encoding="utf-8")


def test_configure_logging_rotation_settings_bound_file_growth(tmp_path, monkeypatch):
    log_path = tmp_path / "general.log"
    monkeypatch.setattr(logging_config, "_LOG_PATH", log_path)
    monkeypatch.setattr(logging_config, "_MAX_BYTES", 200)
    monkeypatch.setattr(logging_config, "_BACKUP_COUNT", 2)

    logging_config.configure_logging()
    logger = logging.getLogger("jarvis.main")
    for i in range(200):
        logger.info("linea de log numero %d para forzar rotacion real", i)

    rotated = list(tmp_path.glob("general.log*"))
    assert len(rotated) > 1  # el archivo activo + al menos un backup rotado
