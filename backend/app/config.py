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

    max_agent_iterations: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))

    phone_tool_timeout: float = float(os.getenv("PHONE_TOOL_TIMEOUT", "30"))


settings = Settings()

if settings._api_key_was_generated:
    print(
        "[jarvis-backend] No API_KEY set in .env — generated one for this run:\n"
        f"  {settings.api_key}\n"
        "  Set API_KEY in backend/.env to keep it stable across restarts."
    )
