"""Tests del diálogo de permisos/conectores. Los de lectura/escritura de .env
son puros (sin Qt); los de estado de checkboxes necesitan una QApplication
real via el fixture `qtbot` de pytest-qt."""

from PySide6.QtCore import QObject, Signal

import config
from ui import settings_window


def test_read_env_parses_key_value_pairs_and_skips_comments(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n# comentario\nBAZ=1\n\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    assert settings_window._read_env() == {"FOO": "bar", "BAZ": "1"}


def test_read_env_returns_empty_dict_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "no_existe.env")
    assert settings_window._read_env() == {}


def test_write_env_updates_existing_key_in_place_without_touching_others(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\nB=2\nC=3\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    settings_window._write_env({"B": "9"})

    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines == ["A=1", "B=9", "C=3"]


def test_write_env_appends_missing_key(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    settings_window._write_env({"NEW_KEY": "true"})

    assert "NEW_KEY=true" in env_file.read_text(encoding="utf-8")


def test_checkbox_uses_backend_default_when_key_absent_from_env(qtbot, tmp_path, monkeypatch):
    """Regresión del bug real del 26/07: si un flag no está en el .env, el
    checkbox tiene que reflejar el default real de backend/app/config.py, no
    'apagado' a ciegas -- si no, la UI miente sobre qué puede hacer Jarvis."""
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")  # ninguno de los 5 flags está seteado
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    dialog = settings_window.SettingsDialog()
    qtbot.addWidget(dialog)

    checked = {key: box.isChecked() for key, box in dialog._checkboxes.items()}
    assert checked == {
        "DESKTOP_CONTROL_ENABLED": True,
        "PHONE_SHELL_ENABLED": True,
        "PHONE_CAMERA_ENABLED": True,
        "FS_ALLOW_DELETE": False,
        "BROWSER_HEADLESS": False,
    }


def test_checkbox_reflects_env_value_directly_not_inverted(qtbot, tmp_path, monkeypatch):
    """El otro lado del mismo bug: cuando SÍ hay un valor en el .env, el
    checkbox tiene que mostrar ese valor tal cual, sin invertirlo."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DESKTOP_CONTROL_ENABLED=false\n"
        "PHONE_SHELL_ENABLED=false\n"
        "PHONE_CAMERA_ENABLED=false\n"
        "FS_ALLOW_DELETE=true\n"
        "BROWSER_HEADLESS=true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    dialog = settings_window.SettingsDialog()
    qtbot.addWidget(dialog)

    checked = {key: box.isChecked() for key, box in dialog._checkboxes.items()}
    assert checked == {
        "DESKTOP_CONTROL_ENABLED": False,
        "PHONE_SHELL_ENABLED": False,
        "PHONE_CAMERA_ENABLED": False,
        "FS_ALLOW_DELETE": True,
        "BROWSER_HEADLESS": True,
    }


def test_save_writes_checked_state_directly_to_env(qtbot, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    class _FakeRestartThread(QObject):
        """Reemplaza el QThread real que reinicia el backend -- estos tests no
        deben tocar el backend real ni depender de un hilo de verdad."""

        done = Signal()

        def start(self):
            self.done.emit()

    monkeypatch.setattr(settings_window, "_RestartThread", _FakeRestartThread)

    dialog = settings_window.SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._checkboxes["FS_ALLOW_DELETE"].setChecked(True)
    dialog._checkboxes["DESKTOP_CONTROL_ENABLED"].setChecked(False)

    dialog._on_save()

    updated = settings_window._read_env()
    assert updated["FS_ALLOW_DELETE"] == "true"
    assert updated["DESKTOP_CONTROL_ENABLED"] == "false"
    assert dialog._save_button.isEnabled()  # _on_restart_done ya corrió y lo reactivó
