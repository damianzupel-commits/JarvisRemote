"""Helper de proceso separado para
test_recording.py::test_job_object_kills_ffmpeg_when_backend_is_hard_killed.

Simula al backend real: arranca una grabación real (ffmpeg real, vía
app.recording.start_recording) y escribe su propio PID + el de ffmpeg a un
archivo JSON para que el test (que lo mata DURO desde afuera, sin darle
chance de correr ningún cleanup) pueda leerlos antes de matarlo.

No es un test en sí -- no lo recolecta pytest (no matchea test_*.py) --, es
un script standalone que el test lanza como subprocess.Popen real."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app import recording


def main() -> None:
    output_dir, info_path = sys.argv[1], sys.argv[2]
    settings.recording_output_dir = output_dir

    output_path = recording.start_recording("job_object_hard_kill_test")
    ffmpeg_pid = recording._active_process.pid

    Path(info_path).write_text(
        json.dumps(
            {
                "backend_pid": os.getpid(),
                "ffmpeg_pid": ffmpeg_pid,
                "output_path": str(output_path),
            }
        )
    )

    # Nunca llega a stop_recording() -- el test lo mata a la fuerza desde
    # afuera (taskkill /F sin /T, sin señal que un try/finally pueda atrapar).
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
