"""Tools `recording_start`/`recording_stop` -- control MANUAL de la grabación
de pantalla (ver `app/recording.py` para el módulo real y su motivación).

La mayor parte del tiempo la grabación arranca/para SOLA (ver
`app/tools/__init__.py::call_tool` + `_RECORDABLE_TOOL_NAMES`, y el
try/finally de `app/agent.py::_run_agent_turn`) alrededor de cualquier tool
de auditoría/fix/test -- estas dos tools acá son para el resto de los casos:
Damian pidiendo explícitamente grabar algo que NO es una de esas tools
automáticas (ej. un demo de varios pasos de control de escritorio/celular),
o queriendo cortar antes de que termine el turno."""

from __future__ import annotations

from .. import audit_log
from .. import recording
from . import register_tool


@register_tool(
    name="recording_start",
    description=(
        "Arranca a grabar la pantalla completa (video, sin audio) a un archivo .mp4 en "
        "content/recordings/ (raíz del repo), con nombre timestamp_<session_name>.mp4. Uso manual -- la "
        "mayoría de las auditorías/fixes/tests ya se graban solas (ver docstring del módulo), usá esto "
        "solo si Damian pidió explícitamente grabar algo que no dispara eso solo, o quiere una grabación "
        "que arranque ANTES de la primera tool call del flujo. Si ya hay una grabación en curso, esto "
        "falla en vez de arrancar una segunda -- pará la actual con recording_stop primero si hace falta "
        "una nueva. Respeta SCREEN_RECORDING_ENABLED=false (si está apagado, tira error explicando por "
        "qué en vez de grabar igual)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "session_name": {
                "type": "string",
                "description": "Nombre corto y descriptivo de lo que se está grabando (ej. 'demo_control_escritorio'). Se sanitiza para nombre de archivo.",
            },
        },
        "required": ["session_name"],
    },
)
def recording_start(session_name: str) -> dict:
    from ..config import settings

    arguments = {"session_name": session_name}
    if not settings.screen_recording_enabled:
        error = "Grabación de pantalla deshabilitada (SCREEN_RECORDING_ENABLED=false en backend/.env)."
        audit_log.log_tool_call(target="pc", tool="recording_start", arguments=arguments, error=error)
        return {"error": error}
    try:
        output_path = recording.start_recording(session_name)
    except recording.RecordingAlreadyActiveError as exc:
        return {"error": str(exc)}
    return {"recording": True, "output_path": str(output_path)}


@register_tool(
    name="recording_stop",
    description=(
        "Para la grabación de pantalla activa (si hay una), cerrando el .mp4 de forma prolija. Devuelve "
        "la ruta del archivo grabado, o 'recording: false' si no había ninguna grabación en curso (caso "
        "normal, no es un error) -- avisale a Damian dónde quedó el archivo."
    ),
    parameters={"type": "object", "properties": {}},
)
def recording_stop() -> dict:
    output_path = recording.stop_recording()
    if output_path is None:
        return {"recording": False}
    return {"recording": False, "output_path": str(output_path)}
