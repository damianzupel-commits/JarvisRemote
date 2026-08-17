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

# Mismo env var que usa el backend para su propio presupuesto de espera al LLM
# (`app/config.py::llm_request_timeout_seconds`, default 1800s) -- un turno de
# chat puede incluir un tool lento (nmap_scan admite hasta 1200s) más una o más
# idas y vueltas al LLM local, así que el timeout HTTP de este cliente tiene
# que ser al menos tan largo como lo que el backend mismo está dispuesto a
# esperar. Antes esto estaba hardcodeado en 600s acá y en voice_listener.py,
# bug real confirmado 2026-08-15: con un modelo local lento (30B parcialmente
# en CPU) el backend seguía trabajando de verdad bien pasados los 600s, pero
# el cliente ya había mostrado un error de timeout y descartado la respuesta.
CHAT_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "1800"))

# Para pegarle al backend desde la tray, "0.0.0.0" (bind-all) no sirve como
# destino: si el backend bindea ahi, igual hay que pegarle por localhost.
_target_host = "127.0.0.1" if HOST in ("0.0.0.0", "") else HOST

BASE_URL = f"http://{_target_host}:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"
DOCS_URL = f"{BASE_URL}/docs"
CHAT_URL = f"{BASE_URL}/api/chat"
CODEBASE_INDEX_URL = f"{BASE_URL}/api/codebase/index"
CODEBASE_RECENT_URL = f"{BASE_URL}/api/codebase/recent"
CODEBASE_GRAPH_URL = f"{BASE_URL}/api/codebase/graph"
CODEBASE_FILE_URL = f"{BASE_URL}/api/codebase/file"
OBSIDIAN_NOTES_URL = f"{BASE_URL}/api/obsidian/notes"
OBSIDIAN_GRAPH_URL = f"{BASE_URL}/api/obsidian/graph"
INVESTIGATION_CASES_URL = f"{BASE_URL}/api/investigation/cases"
INVESTIGATION_GRAPH_URL = f"{BASE_URL}/api/investigation"  # + /{case_id}/graph

# Preferimos el intérprete del venv del backend (ahi están instaladas sus
# dependencias). Si no existe, caemos a "python" del PATH.
_venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
BACKEND_PYTHON = str(_venv_python) if _venv_python.exists() else "python"

LOG_PATH = TRAY_DIR / "backend.log"

POLL_INTERVAL_SECONDS = 3

# Los 3 tiers del proyecto, mostrados en el selector con nombres simples --
# el id real (nombre de Ollama) queda oculto de la UI. "Hard" corta al mismo
# modelo que "Medio" (jarvis-text-hard es un alias de Ollama de jarvis-text-v2,
# ver `ollama cp`) porque lo que lo distingue no es el modelo de texto sino que
# ese tier es el pensado para tareas más pesadas (ej. generación de video, ya
# disponible como tool para el agente sin importar el tier activo). Usar un id
# de Ollama propio para Hard en vez de reusar "jarvis-text-v2" es necesario
# para que el selector pueda recordar cuál de los dos eligió el usuario.
AVAILABLE_MODELS = [
    {"id": "jarvis-text-lite", "label": "Lite"},
    {"id": "jarvis-text-v2", "label": "Medio"},
    {"id": "jarvis-text-hard", "label": "Hard"},
]
