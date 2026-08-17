"""Tests de app/recording.py (grabación de pantalla real con ffmpeg, pedido
explícito de Damian 2026-08-13, ver docstring del módulo) + del hook
automático en app/tools/__init__.py::call_tool y de la red de seguridad
try/finally en app/agent.py::_run_agent_turn.

Mayoría mockeada (subprocess.Popen) para determinismo/velocidad -- UN test
real al final (`test_start_and_stop_recording_produces_a_real_playable_mp4`)
corre ffmpeg de verdad (confirmado en PATH en esta máquina, ver
app/config.py::recording_output_dir) y verifica con ffprobe que el archivo
resultante es un mp4 real y reproducible, mismo criterio de "sin mocks donde
se pueda evitar" que test_pc_command.py aplica a subprocesos reales."""

from __future__ import annotations

import json
import logging.handlers
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import audit_log as audit_log_module
from app import recording


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Aísla settings.recording_output_dir + el estado global del módulo
    (proceso activo) + el audit log real -- mismo criterio que
    test_agent.py::_isolated_audit_log (el handler real queda atado al
    archivo de verdad en el import del módulo, así que hay que
    reemplazarlo, no solo el path)."""
    from app.config import settings

    monkeypatch.setattr(settings, "recording_output_dir", str(tmp_path / "recordings"))
    monkeypatch.setattr(recording, "_active_process", None)
    monkeypatch.setattr(recording, "_active_output_path", None)

    log_path = tmp_path / "audit.log"
    handler = logging.handlers.RotatingFileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    monkeypatch.setattr(audit_log_module, "_AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr(audit_log_module._audit_logger, "handlers", [handler])
    yield
    handler.close()


class _FakeProcess:
    """Doble de subprocess.Popen -- controla a mano si/cuándo el proceso
    "termina" para poder ejercitar el camino feliz (stdin 'q' alcanza) y los
    caminos de escalado (terminate/kill) sin depender de un ffmpeg real."""

    def __init__(self, pid=4242, exits_on_wait=True, exits_on_terminate=True):
        self.pid = pid
        self.stdin = SimpleNamespace(write=lambda b: None, flush=lambda: None)
        self._exits_on_wait = exits_on_wait
        self._exits_on_terminate = exits_on_terminate
        self._alive = True
        self.terminate_called = False
        self.kill_called = False
        self.wait_calls = 0

    def poll(self):
        return None if self._alive else 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.terminate_called and not self.kill_called:
            if self._exits_on_terminate:
                self._alive = False
                return 0
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout)
        if self.kill_called:
            self._alive = False
            return 0
        if self._exits_on_wait:
            self._alive = False
            return 0
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout)

    def terminate(self):
        self.terminate_called = True

    def kill(self):
        self.kill_called = True
        self._alive = False


def _audit_entries(caplog) -> list[dict]:
    """Filtra caplog a solo las líneas JSON de verdad escritas por
    audit_log.log_tool_call (logger "jarvis.audit") -- necesario porque
    start_recording/stop_recording TAMBIÉN loguean texto libre en
    "jarvis.recording" (ej. "recording: arrancó ffmpeg pid=..."), y
    caplog.at_level(logger="jarvis.audit") solo ajusta el UMBRAL de ESE
    logger puntual, no filtra qué otros loggers también terminan
    propagando hacia el handler que caplog instala en la raíz -- un
    json.loads() ciego sobre TODO caplog.messages rompe apenas aparece
    cualquier línea de texto libre mezclada en el mismo capture."""
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "jarvis.audit"
    ]


def _mock_popen(monkeypatch, fake_process):
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.setattr(recording.subprocess, "Popen", fake_popen)
    return captured


# ---------------------------------------------------------------------------
# start_recording -- construcción del comando + estado
# ---------------------------------------------------------------------------


def test_start_recording_builds_expected_ffmpeg_command(monkeypatch):
    fake_process = _FakeProcess()
    captured = _mock_popen(monkeypatch, fake_process)

    output_path = recording.start_recording("mi sesion de prueba")

    command = captured["command"]
    assert command[0] == "ffmpeg"
    assert "-f" in command and command[command.index("-f") + 1] == "gdigrab"
    assert "-i" in command and command[command.index("-i") + 1] == "desktop"
    assert "-framerate" in command
    assert "-vcodec" in command and command[command.index("-vcodec") + 1] == "libx264"
    assert "-pix_fmt" in command and command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[-1] == str(output_path)
    assert captured["kwargs"]["stdin"] == subprocess.PIPE


def test_start_recording_writes_output_under_configured_dir_with_timestamp_and_session_name(monkeypatch):
    from app.config import settings

    _mock_popen(monkeypatch, _FakeProcess())

    output_path = recording.start_recording("security_scan_project")

    assert output_path.parent == recording.Path(settings.recording_output_dir)
    assert output_path.name.endswith("_security_scan_project.mp4")
    assert output_path.parent.is_dir()  # mkdir(parents=True) real, no mockeado


@pytest.mark.parametrize(
    "raw_name,expected_fragment",
    [
        ("nombre con espacios", "nombre_con_espacios"),
        ("../../etc/passwd", "etc_passwd"),
        ("weird!!chars??", "weird_chars"),
        ("####", "recording"),  # todo inválido -> fallback, nunca vacío
    ],
)
def test_start_recording_sanitizes_session_name_for_filesystem_safety(monkeypatch, raw_name, expected_fragment):
    _mock_popen(monkeypatch, _FakeProcess())

    output_path = recording.start_recording(raw_name)

    assert expected_fragment in output_path.name
    assert "/" not in output_path.name and "\\" not in output_path.name


def test_start_recording_raises_when_already_active(monkeypatch):
    _mock_popen(monkeypatch, _FakeProcess())
    recording.start_recording("primera")

    with pytest.raises(recording.RecordingAlreadyActiveError):
        recording.start_recording("segunda")


def test_is_recording_false_before_start_true_after(monkeypatch):
    assert recording.is_recording() is False
    _mock_popen(monkeypatch, _FakeProcess())
    recording.start_recording("algo")
    assert recording.is_recording() is True


def test_is_recording_false_if_process_already_exited_on_its_own(monkeypatch):
    """Si ffmpeg murió solo (crash, disco lleno) sin pasar por stop_recording,
    is_recording() no debe seguir diciendo que sí -- poll() ya no es None."""
    fake_process = _FakeProcess()
    _mock_popen(monkeypatch, fake_process)
    recording.start_recording("algo")

    fake_process._alive = False

    assert recording.is_recording() is False


def test_start_recording_logs_to_audit_log(monkeypatch, caplog):
    _mock_popen(monkeypatch, _FakeProcess())

    with caplog.at_level("INFO", logger="jarvis.audit"):
        recording.start_recording("auditoria_real")

    entries = _audit_entries(caplog)
    assert any(e["tool"] == "recording_start" and e["ok"] is True for e in entries)


def test_start_recording_assigns_process_to_job_object_for_crash_safety(monkeypatch):
    """Unit test rápido/mockeado (sin win32 real) de que `start_recording`
    efectivamente llama al hook del Job Object -- la prueba de que ESTO
    mata a ffmpeg de verdad en un kill duro real es
    `test_job_object_kills_ffmpeg_when_backend_is_hard_killed`, más abajo."""
    fake_process = _FakeProcess()
    _mock_popen(monkeypatch, fake_process)
    calls = []
    monkeypatch.setattr(recording, "_assign_to_job_for_crash_safety", calls.append)

    recording.start_recording("algo")

    assert calls == [fake_process]


# ---------------------------------------------------------------------------
# stop_recording -- shutdown prolijo + escalado + estado
# ---------------------------------------------------------------------------


def test_stop_recording_returns_none_when_nothing_is_active():
    assert recording.stop_recording() is None


def test_stop_recording_sends_q_over_stdin_for_a_clean_shutdown(monkeypatch):
    fake_process = _FakeProcess(exits_on_wait=True)
    written = []
    fake_process.stdin = SimpleNamespace(write=written.append, flush=lambda: None)
    _mock_popen(monkeypatch, fake_process)
    recording.start_recording("algo")

    result_path = recording.stop_recording()

    assert written == [b"q"]
    assert fake_process.terminate_called is False
    assert fake_process.kill_called is False
    assert result_path is not None
    assert result_path.name.endswith("_algo.mp4")


def test_stop_recording_falls_back_to_terminate_when_q_does_not_close_it(monkeypatch):
    fake_process = _FakeProcess(exits_on_wait=False, exits_on_terminate=True)
    _mock_popen(monkeypatch, fake_process)
    recording.start_recording("algo")

    recording.stop_recording()

    assert fake_process.terminate_called is True
    assert fake_process.kill_called is False


def test_stop_recording_falls_back_to_kill_when_terminate_also_fails(monkeypatch):
    fake_process = _FakeProcess(exits_on_wait=False, exits_on_terminate=False)
    _mock_popen(monkeypatch, fake_process)
    recording.start_recording("algo")

    recording.stop_recording()

    assert fake_process.terminate_called is True
    assert fake_process.kill_called is True


def test_stop_recording_clears_active_state_so_a_new_recording_can_start(monkeypatch):
    _mock_popen(monkeypatch, _FakeProcess())
    recording.start_recording("primera")
    recording.stop_recording()

    assert recording.is_recording() is False
    _mock_popen(monkeypatch, _FakeProcess())
    recording.start_recording("segunda")  # no debe levantar RecordingAlreadyActiveError
    assert recording.is_recording() is True


def test_concurrent_start_recording_spawns_only_one_real_process(monkeypatch):
    """Bug real, grave, encontrado en testing adversarial (2026-08-13,
    "grabación activa mientras corre una auditoría pesada"): sin lock, el
    check-then-act de `is_recording()` -> `raise` -> arrancar el proceso
    tenía una carrera real -- 20 llamadas concurrentes a start_recording
    arrancaban DOS procesos ffmpeg reales (confirmado en vivo), pero el
    módulo solo trackea uno -- el otro queda huérfano, grabando
    indefinidamente sin ninguna referencia para pararlo."""
    import threading

    spawned = []

    def fake_popen(command, **kwargs):
        p = _FakeProcess(pid=1000 + len(spawned))
        spawned.append(p)
        return p

    monkeypatch.setattr(recording.subprocess, "Popen", fake_popen)

    results = {"started": 0, "rejected": 0}
    results_lock = threading.Lock()

    def worker(i):
        try:
            recording.start_recording(f"sesion-{i}")
            with results_lock:
                results["started"] += 1
        except recording.RecordingAlreadyActiveError:
            with results_lock:
                results["rejected"] += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(spawned) == 1
    assert results == {"started": 1, "rejected": 19}


def test_stop_recording_when_process_already_exited_still_returns_path_and_logs(monkeypatch, caplog):
    fake_process = _FakeProcess()
    _mock_popen(monkeypatch, fake_process)
    recording.start_recording("algo")
    fake_process._alive = False  # murió solo antes de que alguien llame stop

    with caplog.at_level("INFO", logger="jarvis.audit"):
        result_path = recording.stop_recording()

    assert result_path is not None
    entries = _audit_entries(caplog)
    assert any(e["tool"] == "recording_stop" and e["ok"] is True for e in entries)


# ---------------------------------------------------------------------------
# Hook automático en call_tool (app/tools/__init__.py)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_call_tool_auto_starts_recording_for_a_recordable_tool(monkeypatch):
    from app import tools as tools_module

    monkeypatch.setattr(tools_module, "_RECORDABLE_TOOL_NAMES", frozenset({"fs_list_dir"}))
    monkeypatch.setattr(recording, "is_recording", lambda: False)
    started = {}
    monkeypatch.setattr(recording, "start_recording", lambda session_name: started.setdefault("name", session_name))

    await tools_module.call_tool("fs_list_dir", {"path": "."})

    assert started.get("name") == "fs_list_dir"


@pytest.mark.anyio
async def test_call_tool_does_not_start_a_second_recording_if_one_is_already_active(monkeypatch):
    """El punto entero de la feature: UNA grabación continua para todo el
    pipeline dentro de un turno, no un clip por tool call (pedido explícito
    de Damian -- 'capturar todo el flujo de punta a punta')."""
    from app import tools as tools_module

    monkeypatch.setattr(tools_module, "_RECORDABLE_TOOL_NAMES", frozenset({"fs_list_dir"}))
    monkeypatch.setattr(recording, "is_recording", lambda: True)
    calls = []
    monkeypatch.setattr(recording, "start_recording", lambda session_name: calls.append(session_name))

    await tools_module.call_tool("fs_list_dir", {"path": "."})

    assert calls == []


@pytest.mark.anyio
async def test_concurrent_call_tool_invocations_for_recordable_tools_start_only_one_recording(monkeypatch):
    """Prueba de integración real (2026-08-13, "grabación activa mientras
    corre una auditoría pesada"): simula varias tool calls recordables
    concurrentes de verdad (asyncio.gather, no secuenciales como los otros
    tests de este hook) a través del punto de entrada REAL (call_tool), sin
    mockear `recording.is_recording`/`start_recording` -- ejercita el lock
    real de recording.py de punta a punta, no solo el guard superficial de
    call_tool. Solo se mockea `subprocess.Popen` (no hace falta ffmpeg
    real) y el handler de la tool en sí (una función síncrona liviana --
    una auditoría pesada real no es necesaria para probar la carrera del
    hook de grabación, que pasa ANTES de tocar el handler)."""
    import asyncio

    from app import tools as tools_module
    from app.config import settings

    monkeypatch.setattr(tools_module, "_RECORDABLE_TOOL_NAMES", frozenset({"fs_list_dir"}))
    monkeypatch.setattr(settings, "screen_recording_enabled", True)

    spawned = []

    def fake_popen(command, **kwargs):
        p = _FakeProcess(pid=1000 + len(spawned))
        spawned.append(p)
        return p

    monkeypatch.setattr(recording.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(tools_module._registry["fs_list_dir"], "handler", lambda **kwargs: {"ok": True})

    await asyncio.gather(*[tools_module.call_tool("fs_list_dir", {"path": "."}) for _ in range(20)])

    assert len(spawned) == 1
    assert recording.is_recording() is True


@pytest.mark.anyio
async def test_call_tool_does_not_start_recording_when_disabled_by_flag(monkeypatch):
    from app import tools as tools_module
    from app.config import settings

    monkeypatch.setattr(tools_module, "_RECORDABLE_TOOL_NAMES", frozenset({"fs_list_dir"}))
    monkeypatch.setattr(settings, "screen_recording_enabled", False)
    monkeypatch.setattr(recording, "is_recording", lambda: False)
    calls = []
    monkeypatch.setattr(recording, "start_recording", lambda session_name: calls.append(session_name))

    await tools_module.call_tool("fs_list_dir", {"path": "."})

    assert calls == []


@pytest.mark.anyio
async def test_call_tool_does_not_touch_recording_for_non_recordable_tools(monkeypatch):
    from app import tools as tools_module

    # _RECORDABLE_TOOL_NAMES real (no mockeado) -- fs_list_dir no está.
    calls = []
    monkeypatch.setattr(recording, "start_recording", lambda session_name: calls.append(session_name))

    await tools_module.call_tool("fs_list_dir", {"path": "."})

    assert calls == []


@pytest.mark.anyio
async def test_call_tool_recordable_names_are_all_real_registered_tools():
    """Que _RECORDABLE_TOOL_NAMES no se desactualice silenciosamente si algún
    día se renombra una de esas tools."""
    from app.tools import get_tools
    from app.tools import _RECORDABLE_TOOL_NAMES

    registered = set(get_tools().keys())
    missing = _RECORDABLE_TOOL_NAMES - registered
    assert not missing, f"_RECORDABLE_TOOL_NAMES referencia tools que no existen: {missing}"


# ---------------------------------------------------------------------------
# Red de seguridad try/finally en app/agent.py::_run_agent_turn
# ---------------------------------------------------------------------------


def _fake_tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    args_json = json.dumps(arguments)
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=args_json),
        model_dump=lambda: {"id": call_id, "function": {"name": name, "arguments": args_json}},
    )


def _fake_response(tool_calls: list | None = None, content: str | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.anyio
async def test_run_agent_stops_recording_on_normal_completion(monkeypatch):
    from app import agent

    stop_calls = []
    monkeypatch.setattr(agent.recording, "is_recording", lambda: False)
    monkeypatch.setattr(agent.recording, "stop_recording", lambda: stop_calls.append(1))

    async def fake_create(**kwargs):
        return _fake_response(content="listo")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    await agent.run_agent("hola", conversation_id="test-recording-normal")

    assert stop_calls == [1]


@pytest.mark.anyio
async def test_run_agent_stops_recording_on_early_return_vision_fallback(monkeypatch):
    """Ver agent.py::_VISION_FALLBACK_MSG -- un return TEMPRANO, no el return
    final de la función. El try/finally tiene que cubrir este camino
    también, no solo el normal."""
    from app import agent

    stop_calls = []
    monkeypatch.setattr(agent.recording, "is_recording", lambda: False)
    monkeypatch.setattr(agent.recording, "stop_recording", lambda: stop_calls.append(1))

    tool_call = _fake_tool_call("call_1", "phone_take_photo", {"camera": "back"})
    responses = [_fake_response(tool_calls=[tool_call])]

    async def fake_create(**kwargs):
        if responses:
            return responses.pop(0)
        raise RuntimeError("el modelo cargado no soporta contenido multimodal")

    async def fake_call_tool(name, args):
        return {"image_base64": "ZmFrZQ==", "mime_type": "image/jpeg"}

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", fake_call_tool)

    conv_id, reply, _ = await agent.run_agent("qué ves?", conversation_id="test-recording-vision")

    assert reply == agent._VISION_FALLBACK_MSG
    assert stop_calls == [1]


@pytest.mark.anyio
async def test_run_agent_stops_recording_even_when_llm_call_raises(monkeypatch):
    """Camino de excepción sin capturar (agent.py línea ~943, `raise` cuando
    NO se estaba esperando una respuesta de visión) -- el finally tiene que
    correr igual, no solo en un return."""
    from app import agent

    stop_calls = []
    monkeypatch.setattr(agent.recording, "is_recording", lambda: False)
    monkeypatch.setattr(agent.recording, "stop_recording", lambda: stop_calls.append(1))

    async def fake_create(**kwargs):
        raise RuntimeError("Context size has been exceeded.")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with pytest.raises(RuntimeError, match="Context size has been exceeded"):
        await agent.run_agent("hola", conversation_id="test-recording-exception")

    assert stop_calls == [1]


@pytest.mark.anyio
async def test_run_agent_logs_a_warning_if_a_recording_was_already_active_at_turn_start(monkeypatch, caplog):
    """Defensivo (no debería pasar en la práctica si el try/finally de
    arriba funciona) -- si por lo que sea ya había una grabación activa al
    EMPEZAR un turno nuevo, se loguea bien visible en vez de arrancar una
    segunda grabación superpuesta silenciosamente."""
    from app import agent

    monkeypatch.setattr(agent.recording, "is_recording", lambda: True)
    monkeypatch.setattr(agent.recording, "stop_recording", lambda: None)

    async def fake_create(**kwargs):
        return _fake_response(content="listo")

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    with caplog.at_level("WARNING", logger="jarvis.agent"):
        await agent.run_agent("hola", conversation_id="test-recording-defensive")

    assert any("ya había una grabación activa" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Integración real -- ffmpeg de verdad, sin mocks (ffmpeg confirmado en PATH)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH de esta máquina")
def test_start_and_stop_recording_produces_a_real_playable_mp4():
    output_path = recording.start_recording("integration test real")
    assert recording.is_recording() is True

    import time

    time.sleep(3)  # unos segundos reales de captura de escritorio

    result_path = recording.stop_recording()

    assert result_path == output_path
    assert recording.is_recording() is False
    assert result_path.is_file()
    assert result_path.stat().st_size > 1000  # bien por encima de un archivo vacío/header solo

    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe no está en el PATH -- se saltea la verificación de reproducibilidad")

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration,format_name",
            "-of", "json", str(result_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, f"ffprobe no pudo leer el archivo: {probe.stderr}"
    probed = json.loads(probe.stdout)
    assert "mp4" in probed["format"]["format_name"]
    assert float(probed["format"]["duration"]) > 0


# ---------------------------------------------------------------------------
# Job Object -- ffmpeg no debe sobrevivir un kill duro del backend (ver
# docstring del módulo, riesgo confirmado 2026-08-13, arreglado 2026-08-16).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object es una feature de Windows")
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH de esta máquina")
def test_job_object_kills_ffmpeg_when_backend_is_hard_killed(tmp_path):
    """El test adversarial real que motivó el fix: un proceso "backend"
    aparte (subprocess de verdad, no un mock) arranca una grabación real,
    y se lo mata DURO desde afuera (`taskkill /F` sin `/T`, sin mandarle
    ninguna señal que un try/finally pueda atrapar -- exactamente el
    escenario de un crash real). Antes del fix del Job Object, ffmpeg
    sobrevivía como huérfano (confirmado en testing adversarial 2026-08-13,
    ver docstring del módulo); con el fix, debe morir junto con el backend
    sin que nadie le mande 'q' ni terminate().

    Mismo experimento también valida el fix del mp4 fragmentado (ver
    `_MOVFLAGS`, 2026-08-16): antes de ESE fix, el .mp4 resultante de este
    mismo kill duro quedaba con "moov atom not found" -- ahora tiene que ser
    reproducible de verdad (ffprobe) a pesar del kill duro. Se espera un
    `_GOP_SECONDS` real de grabación antes de matar para garantizar que haya
    al menos un fragmento ya cerrado en disco (sin esa espera, un kill
    inmediato podría pegarle a mitad del PRIMER fragmento, todavía sin
    cerrar, y el test no probaría lo que dice probar)."""
    import psutil

    helper_script = Path(__file__).resolve().parent / "_recording_job_object_helper.py"
    output_dir = tmp_path / "recordings"
    info_path = tmp_path / "info.json"

    backend_proc = subprocess.Popen(
        [sys.executable, str(helper_script), str(output_dir), str(info_path)],
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not info_path.exists():
            time.sleep(0.25)
        assert info_path.exists(), "el proceso helper nunca escribió info.json (¿no arrancó ffmpeg?)"

        info = json.loads(info_path.read_text())
        ffmpeg_pid = info["ffmpeg_pid"]
        output_path = Path(info["output_path"])

        # Confirma el estado de partida real antes de matar nada -- si esto
        # falla, el test de abajo no probaría lo que dice probar.
        assert psutil.pid_exists(backend_proc.pid)
        assert psutil.pid_exists(ffmpeg_pid)

        # Deja pasar más de un GOP real de grabación (ver docstring de
        # `_GOP_SECONDS`) para que exista al menos un fragmento ya cerrado
        # en disco antes del kill -- margen generoso (no un simple +2s):
        # medido en vivo en esta máquina, gdigrab+libx264 real rinden bastante
        # menos que los `_FRAMERATE` nominales bajo carga (CPU compartida con
        # el resto de lo que corre en la sesión), así que un GOP de
        # `_GOP_SECONDS` a fps nominal puede tardar bastante más en fps real.
        time.sleep(max(recording._GOP_SECONDS * 4, 10))

        subprocess.run(
            ["taskkill", "/F", "/PID", str(backend_proc.pid)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and psutil.pid_exists(ffmpeg_pid):
            time.sleep(0.25)

        assert not psutil.pid_exists(ffmpeg_pid), (
            f"ffmpeg (pid={ffmpeg_pid}) sobrevivió al kill duro del backend -- "
            "el Job Object no lo mató, quedó huérfano."
        )

        assert output_path.is_file() and output_path.stat().st_size > 0

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration,format_name",
                "-of", "json", str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert probe.returncode == 0, (
            f"ffprobe no pudo leer el .mp4 después del kill duro (mp4 fragmentado roto): {probe.stderr}"
        )
        probed = json.loads(probe.stdout)
        assert "mp4" in probed["format"]["format_name"]
        assert float(probed["format"]["duration"]) > 0
    finally:
        if backend_proc.poll() is None:
            backend_proc.kill()
        backend_proc.wait(timeout=10)
