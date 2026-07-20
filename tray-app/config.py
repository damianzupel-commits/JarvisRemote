import os
from pathlib import Path

from dotenv import load_dotenv

TRAY_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TRAY_DIR.parent / "backend"
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(ENV_PATH)

HOST = os.getenv("HOST", "127.0.0.1")
PORT = os.getenv("PORT", "8000")
API_KEY = os.getenv("API_KEY", "")

# Para pegarle al backend desde la tray, "0.0.0.0" (bind-all) no sirve como
# destino: si el backend bindea ahi, igual hay que pegarle por localhost.
_target_host = "127.0.0.1" if HOST in ("0.0.0.0", "") else HOST

BASE_URL = f"http://{_target_host}:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"
DOCS_URL = f"{BASE_URL}/docs"
CHAT_URL = f"{BASE_URL}/api/chat"

# Preferimos el intérprete del venv del backend (ahi están instaladas sus
# dependencias). Si no existe, caemos a "python" del PATH.
_venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
BACKEND_PYTHON = str(_venv_python) if _venv_python.exists() else "python"

LOG_PATH = TRAY_DIR / "backend.log"

POLL_INTERVAL_SECONDS = 3
