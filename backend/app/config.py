import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    api_key: str = os.getenv("API_KEY") or secrets.token_urlsafe(32)
    _api_key_was_generated: bool = not os.getenv("API_KEY")

    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "local-model")

    fs_allowed_root: str = os.getenv("FS_ALLOWED_ROOT", str(Path.home()))
    fs_allow_delete: bool = _bool(os.getenv("FS_ALLOW_DELETE"), False)

    browser_headless: bool = _bool(os.getenv("BROWSER_HEADLESS"), False)

    # Control de escritorio (mouse/teclado/ventanas de cualquier app, ver
    # app/tools/desktop.py) es tan invasivo como el Accessibility Service del
    # celular. Prendido por default porque el usuario pidió explícitamente la
    # versión sin fricción, pero queda como flag real para poder apagarlo.
    desktop_control_enabled: bool = _bool(os.getenv("DESKTOP_CONTROL_ENABLED"), True)

    max_agent_iterations: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))

    # Tope de mensajes que se guardan por conversación en memoria (ver
    # app/agent.py::_trim_history). Sin esto, `_conversations` crece para
    # siempre mientras el proceso esté vivo y termina superando el contexto
    # del modelo (pasó de verdad: "Context size has been exceeded" de LM
    # Studio, todo /api/chat empezó a tirar 500). El corte es simple —por
    # cantidad de mensajes, no por tokens reales— y siempre cae en el próximo
    # mensaje 'user' para no partir un tool_call de su respuesta.
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))

    phone_tool_timeout: float = float(os.getenv("PHONE_TOOL_TIMEOUT", "30"))

    # Ejecución de comandos de shell reales en el celular vía Termux
    # (ver app/tools/phone.py::phone_run_command). Es el nivel más invasivo
    # posible del lado del celular: código arbitrario, no solo interacción con
    # la UI. Prendido por default (mismo criterio que DESKTOP_CONTROL_ENABLED:
    # el usuario ya pidió explícitamente la versión sin fricción), pero queda
    # como flag real para poder apagarlo sin tocar código.
    phone_shell_enabled: bool = _bool(os.getenv("PHONE_SHELL_ENABLED"), True)

    # Uso de la cámara del celular (ver app/tools/phone.py::phone_take_photo). Captura
    # silenciosa (sin abrir la app de Cámara), en la misma categoría de invasividad que
    # el resto de las tools de celular. Prendido por default (mismo criterio que
    # DESKTOP_CONTROL_ENABLED/PHONE_SHELL_ENABLED), pero queda como flag real para
    # poder apagarlo sin tocar código.
    phone_camera_enabled: bool = _bool(os.getenv("PHONE_CAMERA_ENABLED"), True)

    # Extracción de frames de video (ver app/video_frames.py y app/tools/phone.py::
    # phone_record_video) — no depende de PHONE_CAMERA_ENABLED por separado, la tool
    # de video usa la misma cámara y el mismo flag que la foto.
    video_frame_interval_seconds: float = float(os.getenv("VIDEO_FRAME_INTERVAL_SECONDS", "1.5"))
    video_max_frames: int = int(os.getenv("VIDEO_MAX_FRAMES", "8"))

    # TLS para servir wss:// en vez de ws:// (la conexión hoy viaja en texto
    # plano — ver sección de seguridad de README.md). Preparado pero apagado
    # por default a propósito: activarlo cambia la URL que espera la app del
    # celular (https:// en vez de http://) y requiere que Android confíe en el
    # certificado self-signed (ver `certs/README.md`) — un corte que hay que
    # coordinar con el usuario presente, no activar solo. Generar el cert con
    # `certs/generate_cert.sh` (o el comando equivalente documentado ahí).
    tls_enabled: bool = _bool(os.getenv("TLS_ENABLED"), False)
    tls_cert_path: str = os.getenv("TLS_CERT_PATH", str(Path(__file__).resolve().parent.parent / "certs" / "cert.pem"))
    tls_key_path: str = os.getenv("TLS_KEY_PATH", str(Path(__file__).resolve().parent.parent / "certs" / "key.pem"))


settings = Settings()

if settings._api_key_was_generated:
    print(
        "[jarvis-backend] No API_KEY set in .env — generated one for this run:\n"
        f"  {settings.api_key}\n"
        "  Set API_KEY in backend/.env to keep it stable across restarts."
    )
