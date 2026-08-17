"""Store de propuestas de auto-fix -- a diferencia de app/security/store.py o
app/testing/store.py (un archivo por proyecto escaneado), acá el volumen es
bajo a propósito (cada propuesta es una operación de alto riesgo, no algo que
pase miles de veces) así que un único JSON con todas las propuestas alcanza,
sin necesidad de un archivo por proposal_id.

Vive en `settings.selfrepair_dir`."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from .models import SelfFixProposal


def _store_path() -> Path:
    d = Path(settings.selfrepair_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / "proposals.json"


def _load_all() -> dict[str, dict]:
    path = _store_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_all(data: dict[str, dict]) -> None:
    _store_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_proposal(proposal: SelfFixProposal) -> None:
    data = _load_all()
    data[proposal.proposal_id] = proposal.to_dict()
    _save_all(data)


def load_proposal(proposal_id: str) -> SelfFixProposal | None:
    data = _load_all()
    raw = data.get(proposal_id)
    if raw is None:
        return None
    return SelfFixProposal.from_dict(raw)


def mark_applied(proposal_id: str, applied_at: str) -> None:
    data = _load_all()
    raw = data.get(proposal_id)
    if raw is None:
        return
    raw["status"] = "applied"
    raw["applied_at"] = applied_at
    data[proposal_id] = raw
    _save_all(data)


def list_pending() -> list[SelfFixProposal]:
    return [SelfFixProposal.from_dict(v) for v in _load_all().values() if v.get("status") == "proposed"]
