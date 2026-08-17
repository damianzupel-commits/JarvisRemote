"""Tests de opencode_run_task (app/tools/opencode.py). El proceso real de
OpenCode se mockea a propósito (mismo criterio que test_security_triage.py/
test_llm_client.py mockeando la llamada al modelo): correrlo de verdad
dispara una generación real en Ollama contra jarvis-text-v2, que en esta
máquina compite por GPU con lo que sea que esté corriendo en paralelo (ver
docs/owasp_benchmark/), y no es determinístico -- lo que hay que probar acá
es la lógica propia de la tool (gate, sandbox de cwd, timeout, diff de
archivos creados/modificados, audit log), no el resultado real de OpenCode."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from app import audit_log
from app.tools import opencode


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(opencode.settings, "fs_allowed_root", str(tmp_path))
    monkeypatch.setattr(opencode.settings, "pc_shell_enabled", True)
    monkeypatch.setattr(opencode.settings, "opencode_bin_path", str(tmp_path / "fake_opencode.exe"))
    monkeypatch.setattr(opencode.settings, "opencode_default_model", "jarvis-ollama/jarvis-text-v2")
    (tmp_path / "fake_opencode.exe").write_bytes(b"")
    return tmp_path


class _FakePopen:
    """Doble de subprocess.Popen que no lanza ningún proceso real -- solo
    registra el comando y, opcionalmente, escribe/modifica archivos en el cwd
    para poder probar el diff de _snapshot/_diff_snapshots contra un cambio
    real en disco."""

    calls: list[list[str]] = []

    def __init__(self, command, cwd=None, on_run=None, **kwargs):
        _FakePopen.calls.append(command)
        self.pid = 12345
        self.returncode = 0
        self._cwd = cwd
        self._on_run = on_run

    def communicate(self, timeout=None):
        if self._on_run:
            self._on_run(self._cwd)
        return "ok stdout\n", ""


def _patch_popen(monkeypatch, on_run=None):
    _FakePopen.calls = []

    def _factory(command, **kwargs):
        return _FakePopen(command, on_run=on_run, **kwargs)

    monkeypatch.setattr(opencode.subprocess, "Popen", _factory)


def test_opencode_run_task_disabled_by_flag(monkeypatch):
    monkeypatch.setattr(opencode.settings, "pc_shell_enabled", False)

    with pytest.raises(opencode.PcShellDisabled):
        opencode.opencode_run_task("crea un archivo", cwd="proj")


def test_opencode_run_task_raises_if_binary_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(opencode.settings, "opencode_bin_path", str(tmp_path / "no_existe.exe"))

    with pytest.raises(opencode.OpenCodeNotInstalled):
        opencode.opencode_run_task("crea un archivo", cwd="proj")


def test_opencode_run_task_rejects_cwd_outside_allowed_root(tmp_path):
    outside = tmp_path.parent / "fuera_del_sandbox"

    with pytest.raises(PermissionError):
        opencode.opencode_run_task("crea un archivo", cwd=str(outside))


def test_opencode_run_task_creates_missing_cwd(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)

    result = opencode.opencode_run_task("crea un archivo", cwd="proyecto-nuevo")

    assert (tmp_path / "proyecto-nuevo").is_dir()
    assert result["cwd"] == str(tmp_path / "proyecto-nuevo")


def test_opencode_run_task_builds_expected_command(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)

    opencode.opencode_run_task("crea un mod de fabric", cwd="proj", model="jarvis-ollama/jarvis-text-v2")

    [command] = _FakePopen.calls
    assert command[0] == str(tmp_path / "fake_opencode.exe")
    assert command[1] == "run"
    assert command[2] == "crea un mod de fabric"
    assert "--dir" in command and command[command.index("--dir") + 1] == str(tmp_path / "proj")
    assert "--auto" in command
    assert "-m" in command and command[command.index("-m") + 1] == "jarvis-ollama/jarvis-text-v2"


def test_opencode_run_task_without_fabric_reference_sends_task_unmodified(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)

    opencode.opencode_run_task("crea un mod de fabric", cwd="proj")

    [command] = _FakePopen.calls
    assert command[2] == "crea un mod de fabric"


def test_opencode_run_task_with_fabric_reference_prepends_curated_reference(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)

    opencode.opencode_run_task("crea un mod de fabric", cwd="proj", fabric_reference=True)

    [command] = _FakePopen.calls
    # 'task' va PRIMERO -- el mensaje no puede EMPEZAR con "-"/"--" (bug real
    # de parseo del CLI de OpenCode, ver comentario en opencode.py) y
    # FABRIC_MOD_REFERENCE arranca con "---", así que va después, no antes.
    assert command[2].startswith("crea un mod de fabric")
    assert not command[2].startswith("-")
    assert "AttackEntityCallback" in command[2]


def test_opencode_run_task_message_never_starts_with_a_dash(monkeypatch, tmp_path):
    """Bug real 2026-08-12: el CLI de OpenCode (yargs) trata un mensaje que
    empieza con '-'/'--' como un flag desconocido y sale con exit_code=1 sin
    procesar nada -- verificado con un binary-search real contra el binario.
    FABRIC_MOD_REFERENCE arranca con '---', así que 'task' tiene que ir
    siempre primero en el mensaje combinado, sin importar el orden en que se
    edite el texto de la referencia en el futuro."""
    _patch_popen(monkeypatch)

    opencode.opencode_run_task("cualquier tarea", cwd="proj", fabric_reference=True)

    [command] = _FakePopen.calls
    assert not command[2].lstrip().startswith("-")


def test_opencode_run_task_result_keeps_original_short_task_not_the_reference(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)

    result = opencode.opencode_run_task("crea un mod de fabric", cwd="proj", fabric_reference=True)

    assert result["task"] == "crea un mod de fabric"


def test_opencode_run_task_defaults_model_from_settings(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)
    monkeypatch.setattr(opencode.settings, "opencode_default_model", "jarvis-ollama/jarvis-text-hard")

    result = opencode.opencode_run_task("tarea", cwd="proj")

    assert result["model"] == "jarvis-ollama/jarvis-text-hard"


def test_opencode_run_task_reports_created_and_modified_files(monkeypatch, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "existing.txt").write_text("v1", encoding="utf-8")

    def _write_files(cwd):
        import time

        time.sleep(0.02)  # asegurar mtime distinto del archivo modificado
        (proj / "existing.txt").write_text("v2 - modificado", encoding="utf-8")
        (proj / "nuevo.py").write_text("print('hola')", encoding="utf-8")

    _patch_popen(monkeypatch, on_run=_write_files)

    result = opencode.opencode_run_task("modifica y crea archivos", cwd="proj")

    assert result["files"]["created"] == ["nuevo.py"]
    assert result["files"]["modified"] == ["existing.txt"]


def test_opencode_run_task_kills_on_timeout(monkeypatch, tmp_path):
    killed = []
    monkeypatch.setattr(opencode, "kill_process_tree", lambda pid: killed.append(pid))

    class _HangingPopen(_FakePopen):
        def communicate(self, timeout=None):
            if not killed:
                raise subprocess.TimeoutExpired(cmd="opencode", timeout=timeout)
            return "salida parcial", ""

    def _factory(command, **kwargs):
        return _HangingPopen(command, **kwargs)

    monkeypatch.setattr(opencode.subprocess, "Popen", _factory)

    result = opencode.opencode_run_task("tarea larga", cwd="proj", timeout=1)

    assert result["timed_out"] is True
    assert killed == [12345]


def test_opencode_run_task_clamps_timeout_to_hard_max(monkeypatch, tmp_path):
    captured = {}

    class _CapturingPopen(_FakePopen):
        def communicate(self, timeout=None):
            captured["timeout"] = timeout
            return "ok", ""

    monkeypatch.setattr(opencode.subprocess, "Popen", lambda command, **kwargs: _CapturingPopen(command, **kwargs))

    opencode.opencode_run_task("tarea", cwd="proj", timeout=999999)

    assert captured["timeout"] == opencode._MAX_TIMEOUT_SECONDS


def test_opencode_run_task_truncates_large_output(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)
    monkeypatch.setattr(opencode, "truncate_output", lambda text: (text[:5], True))

    result = opencode.opencode_run_task("tarea", cwd="proj")

    assert result["stdout_truncated"] is True
    assert result["stdout"] == "ok st"


def test_opencode_run_task_logs_to_audit_log(monkeypatch, tmp_path):
    _patch_popen(monkeypatch)

    opencode.opencode_run_task("tarea auditada", cwd="proj")

    entries = audit_log.read_entries(target="pc", tool="opencode_run_task")
    assert entries
    last = entries[-1]
    assert last["ok"] is True
    assert last["arguments"]["task"] == "tarea auditada"
