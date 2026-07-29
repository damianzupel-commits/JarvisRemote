"""Tests de pc_run_command (app/tools/pc_command.py). Corre subprocesos reales
e inofensivos (echo, python -c con time.sleep corto) -- no mockeados -- mismo
criterio que test_filesystem_audit.py con git real: lo que hay que verificar
acá es justamente que el subproceso corre/mata/sandboxea de verdad, no que se
llamó a una función mockeada con los argumentos correctos."""

import sys
import time

import pytest

from app.tools import pc_command


@pytest.fixture(autouse=True)
def _sandbox_root(tmp_path, monkeypatch):
    monkeypatch.setattr(pc_command.settings, "fs_allowed_root", str(tmp_path))
    monkeypatch.setattr(pc_command.settings, "pc_shell_enabled", True)
    return tmp_path


def test_pc_run_command_runs_real_command_and_captures_output():
    result = pc_command.pc_run_command("echo hola_pc_run_command", cwd=".", timeout=15)

    assert result["exit_code"] == 0
    assert "hola_pc_run_command" in result["stdout"]
    assert result["timed_out"] is False


def test_pc_run_command_uses_given_cwd(tmp_path):
    sub = tmp_path / "proyecto"
    sub.mkdir()

    result = pc_command.pc_run_command("cd", cwd="proyecto", timeout=15)

    assert result["cwd"] == str(sub)


def test_pc_run_command_disabled_by_flag(monkeypatch):
    monkeypatch.setattr(pc_command.settings, "pc_shell_enabled", False)

    with pytest.raises(pc_command.PcShellDisabled):
        pc_command.pc_run_command("echo no_deberia_correr", cwd=".", timeout=5)


@pytest.mark.parametrize(
    "command",
    [
        "rmdir /s /q C:\\",
        "del /f /s /q C:\\",
        "format C:",
        "diskpart",
        "shutdown /s /t 0",
        "vssadmin delete shadows /all /quiet",
    ],
)
def test_pc_run_command_blocks_obviously_destructive_commands(command):
    with pytest.raises(pc_command.DestructivePcCommandBlockedError):
        pc_command.pc_run_command(command, cwd=".", timeout=5)


def test_pc_run_command_does_not_block_normal_commands_with_similar_words():
    # "pip install" no debe matchear ningún patrón del blocklist -- regresión
    # contra falsos positivos demasiado agresivos.
    result = pc_command.pc_run_command("echo pip install -r requirements.txt", cwd=".", timeout=15)
    assert result["exit_code"] == 0


def test_pc_run_command_rejects_cwd_outside_allowed_root(tmp_path):
    outside = tmp_path.parent / "fuera_del_sandbox"

    with pytest.raises(PermissionError):
        pc_command.pc_run_command("echo nope", cwd=str(outside), timeout=5)


def test_pc_run_command_kills_hung_command_on_timeout():
    sleep_cmd = f'"{sys.executable}" -c "import time; time.sleep(10)"'

    started = time.monotonic()
    result = pc_command.pc_run_command(sleep_cmd, cwd=".", timeout=2)
    elapsed = time.monotonic() - started

    assert result["timed_out"] is True
    assert elapsed < 10  # se mató antes de que el sleep(10) terminara solo


def test_pc_run_command_clamps_timeout_to_hard_max(monkeypatch):
    # No corremos de verdad un comando de 600s+ en la suite -- solo verificamos
    # que el clamp se aplica antes de la primera llamada a communicate() (la
    # que de verdad espera al comando; la eventual segunda llamada, si el
    # proceso ya murió, es solo para drenar los pipes y no nos importa acá).
    captured_timeouts = []
    real_communicate = pc_command.subprocess.Popen.communicate

    def _fake_communicate(self, timeout=None, **kwargs):
        captured_timeouts.append(timeout)
        return real_communicate(self, **kwargs)

    monkeypatch.setattr(pc_command.subprocess.Popen, "communicate", _fake_communicate)

    pc_command.pc_run_command("echo clamp_test", cwd=".", timeout=999999)

    assert captured_timeouts[0] == pc_command._MAX_TIMEOUT_SECONDS


def test_pc_run_command_truncates_large_output(monkeypatch):
    monkeypatch.setattr(pc_command, "_MAX_OUTPUT_CHARS", 10)

    result = pc_command.pc_run_command("echo 0123456789ABCDEF", cwd=".", timeout=15)

    assert result["stdout_truncated"] is True
    assert len(result["stdout"]) == 10


def test_pc_run_command_logs_to_audit_log():
    from app import audit_log

    pc_command.pc_run_command("echo audit_log_marker_pc_command", cwd=".", timeout=15)

    entries = audit_log.read_entries(target="pc", tool="pc_run_command")
    assert entries
    last = entries[-1]
    assert last["ok"] is True
    assert last["arguments"]["command"] == "echo audit_log_marker_pc_command"


@pytest.mark.timeout(90)
def test_pc_run_command_creates_venv_and_installs_isolated_from_global(tmp_path):
    """Flujo real de punta a punta que el system prompt ahora le indica al modelo
    para proyectos Python: crear un venv DENTRO del proyecto con pc_run_command y
    usar el intérprete de ESE venv (nunca el pip/python global) para instalar. No
    mockeado -- corre 'python -m venv' y 'pip install' de verdad (paquete chico,
    'iniconfig', ya en la cache local de pip por ser dependencia de pytest en este
    mismo repo, así que no depende de que la red esté rápida)."""
    proj = tmp_path / "venv_project"
    proj.mkdir()

    created = pc_command.pc_run_command("python -m venv .venv", cwd="venv_project", timeout=90)
    assert created["exit_code"] == 0, created["stderr"]

    venv_python = proj / ".venv" / "Scripts" / "python.exe"
    assert venv_python.is_file(), "el venv no se creó donde el prompt le dice al modelo que lo busque"

    installed = pc_command.pc_run_command(
        ".venv\\Scripts\\python.exe -m pip install --no-input iniconfig",
        cwd="venv_project",
        timeout=90,
    )
    assert installed["exit_code"] == 0, installed["stderr"]

    # Verificación real de aislamiento: el paquete tiene que resolver DENTRO del
    # venv nuevo cuando se importa con SU intérprete -- no alcanza con que
    # 'exit_code' haya sido 0, hay que confirmar que no cayó en algún site-packages
    # global compartido.
    check = pc_command.pc_run_command(
        '.venv\\Scripts\\python.exe -c "import iniconfig, os; print(os.path.abspath(iniconfig.__file__))"',
        cwd="venv_project",
        timeout=30,
    )
    assert check["exit_code"] == 0, check["stderr"]
    installed_path = check["stdout"].strip()
    assert str(proj / ".venv") in installed_path
