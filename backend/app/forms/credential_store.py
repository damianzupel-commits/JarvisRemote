"""Store de credenciales generadas por Jarvis al completar formularios/
registros web (ver `app/tools/web_forms.py`) -- protegido con DPAPI, MISMO
mecanismo que `app/investigation/keys.py` ya usa para la clave de firma
Ed25519 (ver ese módulo para el razonamiento completo de por qué DPAPI y no
texto plano: atado a la cuenta de Windows actual, nadie puede desencriptar el
archivo copiándolo a otra máquina o leyéndolo con otra cuenta).

## Decisión de diseño (ronda de preguntas de "formularios web", Damian, 2026-08-16)

1. **Contraseñas**: Jarvis las genera al azar (nunca las elige con criterio
   propio, nunca reutiliza una), completa el registro solo, y las muestra en
   el chat en el momento -- pero Damian pidió explícitamente que TAMBIÉN
   queden guardadas en un archivo (no solo mostradas una vez). Texto plano
   fue descartado a propósito: es el mismo antipatrón ya señalado sobre
   `backend/.env` (API keys en claro) durante la investigación de
   auto-protección del módulo de malware -- acá se evita reusando DPAPI en
   vez de reinventar otro mecanismo nuevo.
2. **Formato**: un único archivo, con TODO el JSON de credenciales cifrado
   como un solo blob DPAPI (no una entrada por archivo aparte) -- más simple
   que fragmentar, y no hay necesidad real de descifrar una sola entrada sin
   poder ver las demás (Damian es el único lector).

**Limitación real, misma que `investigation/keys.py`**: DPAPI ata el cifrado
a esta cuenta de Windows en esta máquina -- si el disco se mueve o Windows se
reinstala, las credenciales viejas no se pueden recuperar del blob (hace
falta que Damian las haya usado/guardado aparte mientras tanto).
"""

from __future__ import annotations

import json
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import win32crypt

_DPAPI_DESCRIPTION = "jarvis web form credentials"

# Charset amplio (letras + dígitos + puntuación común) pero sin comillas,
# backslash ni backtick -- esos caracteres rompen con frecuencia real inputs
# HTML/JS mal escapados en sitios de terceros que no controlamos, y no
# aportan entropía real que las ~90 opciones restantes ya no den.
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.?"

_MIN_LENGTH = 12
_DEFAULT_LENGTH = 20


def generate_strong_password(length: int = _DEFAULT_LENGTH) -> str:
    """Contraseña aleatoria fuerte vía `secrets` (CSPRNG, no `random`) --
    nunca elegida ni "inventada" por el LLM, solo generada acá de forma
    determinística en entropía."""
    length = max(_MIN_LENGTH, int(length))
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def _load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    protected = path.read_bytes()
    _description, raw = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
    return json.loads(raw.decode("utf-8"))


def _save_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(entries, ensure_ascii=False).encode("utf-8")
    protected = win32crypt.CryptProtectData(raw, _DPAPI_DESCRIPTION, None, None, None, 0)
    path.write_bytes(protected)


def save_credential(*, path: str | Path, site: str, username: str, password: str) -> None:
    path = Path(path)
    entries = _load_entries(path)
    entries.append(
        {
            "site": site,
            "username": username,
            "password": password,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_entries(path, entries)


def list_credentials(path: str | Path) -> list[dict[str, Any]]:
    """Metadata sin la contraseña -- para que Jarvis pueda listar qué sitios
    tienen una credencial guardada sin exponer los secretos de todos de una."""
    entries = _load_entries(Path(path))
    return [
        {"site": e["site"], "username": e["username"], "created_at": e["created_at"]}
        for e in entries
    ]


def get_credential(path: str | Path, site: str, username: str = "") -> dict[str, Any] | None:
    """Busca por `site` (y `username` si se pasa, para desambiguar más de una
    cuenta en el mismo sitio). Si hay varias coincidencias devuelve la más
    reciente."""
    entries = _load_entries(Path(path))
    matches = [
        e for e in entries if e["site"] == site and (not username or e["username"] == username)
    ]
    if not matches:
        return None
    return matches[-1]
