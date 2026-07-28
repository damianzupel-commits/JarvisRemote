"""Tests de process_manager sin tocar procesos reales -- todo lo que llama a
netstat/Popen/taskkill va mockeado. Correr esto NO debe arrancar ni matar el
backend real de la PC donde se ejecute."""

import subprocess

import pytest

import config
import process_manager


@pytest.fixture(autouse=True)
def _reset_module_state():
    # `_process` es un global del módulo -- sin resetearlo, el orden de los
    # tests podría filtrar estado de uno a otro.
    process_manager._process = None
    yield
    process_manager._process = None


NETSTAT_OUTPUT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       4242
  TCP    127.0.0.1:5000         0.0.0.0:0              LISTENING       9999
  TCP    0.0.0.0:8000           0.0.0.0:0              TIME_WAIT       1234
"""


def test_find_listening_pid_matches_port_and_state(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: NETSTAT_OUTPUT)
    assert process_manager._find_listening_pid(8000) == 4242


def test_find_listening_pid_returns_none_when_port_not_found(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: NETSTAT_OUTPUT)
    assert process_manager._find_listening_pid(9999999) is None


def test_find_listening_pid_returns_none_on_netstat_failure(monkeypatch):
    def _raise(*a, **k):
        raise OSError("netstat no disponible")

    monkeypatch.setattr(subprocess, "check_output", _raise)
    assert process_manager._find_listening_pid(8000) is None


def test_is_running_true_when_real_port_is_listening_even_without_tracked_process(monkeypatch):
    # Este es el escenario real que motivó el fix: el backend fue reiniciado a
    # mano (fuera de esta tray) y `_process` nunca se enteró.
    monkeypatch.setattr(process_manager, "_find_listening_pid", lambda port: 4242)
    assert process_manager.is_running() is True


def test_is_running_false_when_nothing_listening(monkeypatch):
    monkeypatch.setattr(process_manager, "_find_listening_pid", lambda port: None)
    assert process_manager.is_running() is False


def test_start_does_not_spawn_a_second_backend_if_port_already_listening(monkeypatch):
    monkeypatch.setattr(process_manager, "_find_listening_pid", lambda port: 4242)
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: popen_calls.append((a, k)))

    msg = process_manager.start()

    assert popen_calls == []
    assert "ya está corriendo" in msg


def test_start_spawns_backend_when_nothing_listening(monkeypatch, tmp_path):
    monkeypatch.setattr(process_manager, "_find_listening_pid", lambda port: None)
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "backend.log")

    class _FakePopen:
        def __init__(self, *a, **k):
            self.pid = 4321

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)

    msg = process_manager.start()

    assert "4321" in msg
    assert process_manager._process.pid == 4321


def test_stop_kills_externally_started_backend_by_real_port(monkeypatch):
    # `_process` es None (no lo lanzó esta tray) pero el puerto sigue en uso --
    # antes del fix de _find_listening_pid, esto reportaba "no estaba
    # corriendo" sin matar nada.
    monkeypatch.setattr(process_manager, "_find_listening_pid", lambda port: 4242)
    taskkill_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: taskkill_calls.append(a))

    msg = process_manager.stop()

    assert taskkill_calls
    assert "4242" in taskkill_calls[0][0]
    assert "4242" in msg


def test_stop_reports_not_running_when_nothing_to_kill(monkeypatch):
    monkeypatch.setattr(process_manager, "_find_listening_pid", lambda port: None)
    msg = process_manager.stop()
    assert "no estaba corriendo" in msg


def test_set_active_model_rewrites_existing_key(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HOST=0.0.0.0\nLMSTUDIO_MODEL=jarvis-text-v2\nPORT=8000\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.setattr(process_manager, "stop", lambda: "stopped")
    monkeypatch.setattr(process_manager, "start", lambda: "started")

    result = process_manager.set_active_model("jarvis-text-lite")

    text = env_file.read_text(encoding="utf-8")
    assert "LMSTUDIO_MODEL=jarvis-text-lite" in text
    assert text.count("LMSTUDIO_MODEL=") == 1
    assert "HOST=0.0.0.0" in text  # no se pisan las otras líneas
    assert result == "started"


def test_set_active_model_appends_key_when_missing(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HOST=0.0.0.0\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.setattr(process_manager, "stop", lambda: "stopped")
    monkeypatch.setattr(process_manager, "start", lambda: "started")

    process_manager.set_active_model("jarvis-text-hard")

    assert "LMSTUDIO_MODEL=jarvis-text-hard" in env_file.read_text(encoding="utf-8")
