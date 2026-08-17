"""Grabación de pantalla real (ffmpeg) para documentar el trabajo de Jarvis
tal cual pasa -- motivación real de Damian (2026-08-13): quiere contenido
real (auditorías/fixes/tests reales) en vez del contenido de "IA +
ciberseguridad" exagerado/vacío que se ve en redes, y para eso necesita
capturar el flujo COMPLETO de punta a punta (no solo un screenshot del
resultado final). Esta tool SOLO graba y guarda -- edición/publicación las
hace Damian a mano después, nunca acá.

Reusa ffmpeg (ya instalado y confirmado en el PATH de esta máquina, ver
`app/config.py::recording_output_dir`) en vez de sumar una dependencia nueva
de captura de video -- mismo criterio que el resto del proyecto de preferir
un binario real ya presente (nmap, cppcheck, clang-tidy) a una librería
Python nueva para algo que un binario externo ya resuelve mejor.

Estado a nivel de módulo para el proceso ffmpeg activo -- mismo criterio que
`app/phone_link.py` (`_phone_ws`, `_pending`) para estado de un único backend
FastAPI de un solo proceso: no hace falta una clase/singleton, este módulo
YA ES el singleton (se importa una sola vez por proceso).

Sin audio a propósito (simplifica -- capturar audio del sistema en Windows
necesita un dispositivo de audio virtual tipo VB-Cable/Stereo Mix habilitado
a mano, que no podemos asumir que existe en esta máquina; Damian puede narrar
agregando audio después, en edición manual).

Riesgo real, CONFIRMADO y ARREGLADO (testing adversarial 2026-08-13, "kill
duro del proceso backend mientras graba"; fix 2026-08-16): `CREATE_NEW_PROCESS_GROUP`
saca a ffmpeg del árbol de procesos del backend a propósito (para poder
mandarle 'q' por stdin sin que un Ctrl+C al backend también lo alcance a
él) -- pero como efecto secundario, un simple parent/child tree no basta:
si el backend MISMO muere (crash, kill duro, no un `stop_recording()`
normal), ffmpeg no moriría con él por default. Confirmado en vivo con un
proceso hijo real imitando exactamente estos mismos flags de Popen:
sobrevive un `TerminateProcess` del padre sin problema.

Arreglo real: Job Object de Windows (`_get_or_create_job` más abajo) con
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` -- cada ffmpeg que arranca
`start_recording` se asigna a un job creado una sola vez a nivel de
proceso (vive mientras vive el backend). Windows cierra automáticamente el
handle del job cuando el proceso dueño (el backend) termina por CUALQUIER
motivo -- normal, crash, o un kill duro -- y `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
hace que ese cierre mate a todos los procesos todavía asignados al job. No
depende de que el backend llegue a ejecutar código de cleanup (a diferencia
de `stop_recording`, que sigue siendo el camino preferido -- shutdown
prolijo con 'q' por stdin -- para cuando el backend termina normal; el Job
Object es la red de seguridad para cuando NO hay oportunidad de correr ese
código). Validado en vivo 2026-08-16: proceso backend real lanzado en un
subproceso aparte, arranca una grabación real (ffmpeg real, no mockeado),
se mata el subproceso backend con `taskkill /F` (kill duro real, sin
`stop_recording()`) -- el ffmpeg hijo desaparece también, confirmado
consultando el PID después con `tasklist`. Antes de este fix, el mismo
experimento dejaba a ffmpeg corriendo huérfano."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import audit_log
from .config import settings

logger = logging.getLogger("jarvis.recording")

# pywin32 ya es dependencia del proyecto en Windows (ver requirements.txt,
# `pywin32>=306; sys_platform == "win32"`) -- import condicionado a la
# plataforma, mismo criterio que `creationflags` más abajo (este módulo solo
# funciona de verdad en Windows por `gdigrab`, pero se evita romper un
# import en otra plataforma).
if sys.platform == "win32":
    import win32api
    import win32con
    import win32job

# Framerate/preset/codec pensados para un video de demo/tutorial, no para
# gaming ni para archivo de máxima calidad: 15fps alcanza de sobra para
# mostrar terminal/editor/navegador (nada de movimiento rápido tipo juego),
# libx264 + preset "fast" mantiene el uso de CPU razonable en una corrida
# real de auditoría (que puede durar varios minutos y competir por CPU con
# pytest/ruff/mypy corriendo AL MISMO TIEMPO que se graba), y yuv420p es el
# pixel format más compatible para reproducir el .mp4 resultante en
# cualquier reproductor/editor sin conversión extra.
_FRAMERATE = "15"
_PRESET = "fast"

# Segundos entre keyframes -- también define cada cuánto se cierra/flushea un
# fragmento en el mp4 fragmentado (ver `_MOVFLAGS` más abajo): un GOP chico
# acota cuánto de la grabación se puede llegar a perder si el proceso muere
# a mitad de un fragmento sin llegar a cerrarlo (en el peor caso, hasta
# `_GOP_SECONDS` segundos -- razonable para contenido de demo/tutorial, no
# vale la pena bajarlo más y pagar el costo de más keyframes en tamaño de
# archivo para un caso que ya de por sí es el peor caso, no el camino normal).
_GOP_SECONDS = 2

# mp4 "fragmentado" en vez del mp4 clásico (moov al final, con la tabla de
# samples completa del archivo entero) -- riesgo real CONFIRMADO y ARREGLADO
# 2026-08-16 (testing adversarial, "kill duro en pleno grabado, sin pasar
# por stop_recording"): un mp4 clásico necesita terminar de escribir para
# poder escribir el moov atom (requiere saber la tabla de samples completa
# de antemano), así que un kill duro a mitad de grabación siempre dejaba un
# archivo con "moov atom not found", no reproducible por ningún player --
# esto es DISTINTO del riesgo del ffmpeg huérfano (ver Job Object más abajo):
# incluso con el Job Object matando a ffmpeg al toque cuando el backend
# muere, el archivo en sí seguía quedando roto. `+empty_moov` escribe un
# moov "vacío" (sin tabla de samples) al PRINCIPIO del archivo, y
# `+frag_keyframe` cierra un fragmento (moof+mdat) autocontenido en cada
# keyframe -- cada fragmento YA cerrado en disco es reproducible por sí
# solo, sin depender de que el archivo entero termine de escribirse.
# `+default_base_moof` evita offsets absolutos de archivo en la metadata de
# cada fragmento (recomendado para máxima compatibilidad de players, aunque
# acá alcance con reproducir localmente vía ffprobe/VLC).
_MOVFLAGS = "+frag_keyframe+empty_moov+default_base_moof"

# Sin esto, los flags de arriba NO alcanzan en la práctica -- hallazgo real
# de testing adversarial 2026-08-16, no algo documentado de antemano: con
# SOLO `_MOVFLAGS`, un desktop real grabado y matado con `taskkill /F` a los
# ~6-8s seguía dando "moov atom not found" a pesar de que el mp4 ya era
# fragmentado, porque `frag_keyframe` cierra el fragmento a nivel del
# MUXER, pero ffmpeg igual lo retiene en el buffer interno de escritura
# (avio) sin bajarlo a disco hasta acumular ~8-11s de contenido (reproducido
# también con una fuente sintética -re, sin gdigrab de por medio -- descartado
# que sea un tema de gdigrab puntual). `-flush_packets 1` fuerza el flush a
# disco de cada paquete apenas se escribe, en vez de esperar a que el buffer
# interno se llene -- confirmado en vivo: CON este flag, un desktop real
# grabado y matado duro (`taskkill /F`, sin 'q', sin terminate()) a los 6s
# quedó reproducible de punta a punta (ffprobe: duration=8.0s, sin error de
# moov atom); SIN él, el mismo experimento (con `_MOVFLAGS` puesto pero sin
# `flush_packets`) seguía rompiéndose si el kill llegaba antes de ese primer
# flush automático (~8-11s reales en esta máquina). Sin cambios de pipeline
# más allá de este flag adicional de ffmpeg -- sigue siendo un solo proceso,
# un solo archivo de salida, mismo `stop_recording` de siempre para el
# camino feliz.
_FLUSH_PACKETS = "1"

# Cuánto esperar una salida "limpia" (mandando 'q' por stdin, que hace que
# ffmpeg cierre el último fragmento y termine prolijo) antes de escalar a
# terminate()/kill() -- ya no hace falta para que el archivo sea reproducible
# (ver `_MOVFLAGS` arriba, que resuelve eso incluso en un kill duro), pero
# sigue siendo el camino preferido: un cierre prolijo no pierde el fragmento
# que estaba a medio grabar en el momento del stop.
_GRACEFUL_STOP_TIMEOUT_SECONDS = 10.0
_TERMINATE_TIMEOUT_SECONDS = 5.0

_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")

# Proceso ffmpeg activo (o None si no hay ninguna grabación en curso) + la
# ruta de salida que le corresponde -- ambos se setean/limpian juntos, nunca
# uno sin el otro (ver start_recording/stop_recording).
_active_process: subprocess.Popen | None = None
_active_output_path: Path | None = None

# Job Object de Windows (ver docstring del módulo) -- uno solo, creado la
# primera vez que hace falta y reusado para cada grabación siguiente
# mientras viva el proceso backend. No hace falta uno nuevo por grabación:
# `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` actúa sobre el conjunto de procesos
# asignados en el momento en que el handle se cierra, y un ffmpeg que ya
# terminó normalmente (por `stop_recording`) ya no está asignado a nada que
# importe.
_job_handle = None


def _get_or_create_job():
    """Devuelve el Job Object del proceso, creándolo la primera vez.

    Solo se llama en Windows (ver call site en `start_recording`). Si
    `CreateJobObject`/`SetInformationJobObject` fallan (permisos, versión de
    Windows sin soporte), deja `_job_handle` en None y el caller loguea un
    warning y sigue sin la red de seguridad -- no vale la pena que un fallo
    acá tumbe la grabación en sí, que sigue funcionando igual sin esto."""
    global _job_handle
    if _job_handle is not None:
        return _job_handle

    job = win32job.CreateJobObject(None, "")
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)

    _job_handle = job
    return job


def _assign_to_job_for_crash_safety(process: subprocess.Popen) -> None:
    """Mete a `process` (ffmpeg) en el Job Object del backend -- ver
    docstring del módulo. Best-effort: si algo falla, se loguea y la
    grabación sigue igual (mismo criterio de `_get_or_create_job`), porque
    esto es una red de seguridad para el caso de crash, no el camino
    principal (ese sigue siendo `stop_recording`)."""
    if sys.platform != "win32":
        return
    try:
        job = _get_or_create_job()
        # PROCESS_SET_QUOTA + PROCESS_TERMINATE son los access rights que
        # AssignProcessToJobObject necesita sobre el handle del proceso hijo
        # (documentado por la API de Windows) -- no hace falta PROCESS_ALL_ACCESS.
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, process.pid
        )
        try:
            win32job.AssignProcessToJobObject(job, process_handle)
        finally:
            process_handle.Close()
    except Exception:
        logger.warning(
            "recording: no se pudo asignar ffmpeg (pid=%s) al Job Object -- "
            "si el backend crashea, este proceso puede quedar huérfano",
            process.pid,
            exc_info=True,
        )


# Serializa el check-then-act de start_recording/stop_recording -- bug real,
# grave, encontrado en testing adversarial (2026-08-13, "grabación activa
# mientras corre una auditoría pesada"): sin lock, 20 llamadas concurrentes a
# start_recording (simuladas, mismo criterio que los tests de concurrencia de
# case_store/jarvis_reflect -- Popen mockeado para no depender de ffmpeg
# real) arrancaban DOS procesos ffmpeg reales de verdad, no uno -- el chequeo
# `if is_recording(): raise RecordingAlreadyActiveError` es un check-then-act
# real (leer el estado, decidir, recién después escribir `_active_process`),
# exactamente la misma clase de carrera que ya se encontró y arregló en
# `case_store._lock_for`. El módulo solo trackea UN proceso a la vez -- el
# segundo (o los que sean) queda huérfano, grabando indefinidamente sin
# ninguna referencia para pararlo con `stop_recording()`, contradiciendo el
# propósito explícito de `RecordingAlreadyActiveError` (ver su docstring:
# "en la práctica este error es defensivo, no el camino esperado" -- que
# dejaba de ser cierto bajo concurrencia real antes de este fix).
_lock = threading.Lock()


class RecordingAlreadyActiveError(Exception):
    """`start_recording` se llamó mientras ya había una grabación en curso.

    Decisión explícita (no un no-op silencioso): un caller que asume que
    arrancó una grabación nueva y en realidad se suma a una vieja podría
    creer que tiene un clip acotado a SU tarea cuando en realidad el archivo
    en disco contiene además todo lo que se venía grabando antes -- mejor
    fallar fuerte y que el caller decida (ver `call_tool`, que ya chequea
    `is_recording()` antes de llamar para nunca pisar una grabación en
    curso, así que en la práctica este error es defensivo, no el camino
    esperado)."""


def _sanitize_session_name(session_name: str) -> str:
    """Recorta a algo seguro para nombre de archivo en Windows: solo
    alfanumérico/._- , el resto se colapsa a '_'. Nunca vacío (si el nombre
    original era todo caracteres inválidos, cae a 'recording')."""
    cleaned = _SANITIZE_PATTERN.sub("_", session_name).strip("_")
    return cleaned or "recording"


def is_recording() -> bool:
    if _active_process is None:
        return False
    # poll() no bloquea -- si el proceso ya terminó solo (crash de ffmpeg,
    # disco lleno, etc.) sin pasar por stop_recording, no queremos seguir
    # reportando que está grabando.
    return _active_process.poll() is None


def start_recording(session_name: str) -> Path:
    """Arranca una grabación de pantalla completa en background (no
    bloqueante -- lanza el proceso y devuelve enseguida, el archivo se sigue
    escribiendo mientras el caller sigue con lo suyo).

    Levanta RecordingAlreadyActiveError si ya hay una grabación activa (ver
    docstring de esa excepción). Todo el chequeo-y-arranque pasa por
    `_lock` -- bug real encontrado en testing adversarial (2026-08-13, ver
    docstring de `_lock`): sin serializar, dos llamadas concurrentes podían
    arrancar DOS procesos ffmpeg reales, dejando uno huérfano."""
    global _active_process, _active_output_path

    with _lock:
        if is_recording():
            raise RecordingAlreadyActiveError(
                f"Ya hay una grabación en curso ({_active_output_path})."
            )

        output_dir = Path(settings.recording_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = _sanitize_session_name(session_name)
        output_path = output_dir / f"{timestamp}_{safe_name}.mp4"

        # gdigrab es el input device de ffmpeg para capturar el escritorio de
        # Windows (equivalente a x11grab en Linux o avfoundation en macOS) --
        # confirmado correcto para Windows 11, que es lo que corre esta máquina.
        # "-i desktop" captura el escritorio completo (todos los monitores en
        # uno solo si hay más de uno), no una ventana puntual -- a propósito:
        # Damian pidió el flujo de trabajo COMPLETO, y una auditoría real salta
        # entre terminal/editor/navegador, una ventana sola se lo perdería.
        command = [
            "ffmpeg",
            "-f", "gdigrab",
            "-framerate", _FRAMERATE,
            "-i", "desktop",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", _PRESET,
            "-g", str(int(_FRAMERATE) * _GOP_SECONDS),
            "-flush_packets", _FLUSH_PACKETS,
            "-movflags", _MOVFLAGS,
            "-y",
            str(output_path),
        ]

        arguments = {"session_name": session_name, "output_path": str(output_path)}
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        try:
            # Bug real encontrado probando esto en vivo (2026-08-13): ffmpeg
            # manda progreso (frame=/fps=/...) a stderr CONSTANTEMENTE mientras
            # graba. Con stdout=PIPE/stderr=STDOUT y nadie leyendo del otro lado
            # (esta es una grabación de fondo, no nos interesa su output), el
            # buffer del pipe del SO se llena (~64KB en Windows) en segundos, y
            # el write() de ffmpeg se BLOQUEA -- todo el proceso se cuelga sin
            # avisar, sigue "vivo" (poll() sigue en None) pero deja de escribir
            # frames nuevos al mp4 real. Confirmado real: con PIPE sin drenar,
            # una grabación de ~13s reales quedaba en 48 bytes (solo el header);
            # con DEVNULL, una de 3s reales quedó en ~370KB reproducibles de
            # verdad (confirmado con ffprobe). DEVNULL para stdout/stderr (no
            # nos interesa su log) evita el problema de raíz -- stdin sigue
            # siendo PIPE porque ESE sí lo usamos (el 'q' de shutdown prolijo).
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception as exc:
            audit_log.log_tool_call(
                target="pc", tool="recording_start", arguments=arguments, error=str(exc)
            )
            raise

        _assign_to_job_for_crash_safety(process)

        _active_process = process
        _active_output_path = output_path
        logger.info("recording: arrancó ffmpeg pid=%s -> %s", process.pid, output_path)
        # Visible SIEMPRE en el audit trail, arranque manual o automático (ver
        # app/tools/__init__.py::call_tool) -- Damian no debería tener que
        # adivinar "¿esto se estaba grabando?", ver motivación en el docstring
        # del módulo.
        audit_log.log_tool_call(
            target="pc", tool="recording_start", arguments=arguments, result={"pid": process.pid}
        )
        return output_path


def stop_recording() -> Path | None:
    """Para la grabación activa (si hay una) con shutdown prolijo -- 'q' por
    stdin primero (finaliza el moov atom del mp4 correctamente), terminate()
    si no responde a tiempo, kill() como último recurso.

    Devuelve la ruta del archivo grabado, o None si no había ninguna
    grabación activa -- "nada que parar" es un caso normal y esperado (tanto
    para el stop manual como para el try/finally de `agent.py::run_agent`
    que llama esto SIEMPRE al final de cada turno, haya grabado algo ese
    turno o no), nunca levanta por eso.

    Todo pasa por `_lock` (mismo lock que `start_recording`) -- un stop
    concurrente con otro stop, o con un start, se serializa en vez de
    correr una carrera sobre `_active_process`/`_active_output_path`."""
    global _active_process, _active_output_path

    with _lock:
        process = _active_process
        output_path = _active_output_path
        if process is None or output_path is None:
            return None

        arguments = {"output_path": str(output_path)}
        try:
            if process.poll() is None:
                try:
                    if process.stdin:
                        process.stdin.write(b"q")
                        process.stdin.flush()
                    process.wait(timeout=_GRACEFUL_STOP_TIMEOUT_SECONDS)
                except Exception:
                    logger.warning(
                        "recording: 'q' por stdin no cerró ffmpeg a tiempo (pid=%s), escalando a terminate()",
                        process.pid,
                    )
                    process.terminate()
                    try:
                        process.wait(timeout=_TERMINATE_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        logger.warning(
                            "recording: terminate() tampoco cerró ffmpeg a tiempo (pid=%s), kill()", process.pid
                        )
                        process.kill()
                        process.wait(timeout=_TERMINATE_TIMEOUT_SECONDS)
        finally:
            _active_process = None
            _active_output_path = None

        logger.info("recording: paró ffmpeg -> %s", output_path)
        audit_log.log_tool_call(
            target="pc", tool="recording_stop", arguments=arguments, result={"output_path": str(output_path)}
        )
        return output_path
