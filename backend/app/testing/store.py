"""Cache en disco de la ÚLTIMA corrida de tests reales por proyecto -- mismo
patrón que `app/security/store.py`/`app/quality/store.py`. Es lo que lee
`audit_report.generate_report` para marcar explícitamente si hubo (o no) una
corrida de tests real en verde después de los fixes aplicados, sin tener que
volver a correr la suite entera solo para armar el reporte.

Vive en `settings.test_run_dir`, fuera del proyecto testeado."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import settings
from .models import RunOutcome


def _slug_for(root: Path) -> str:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return f"{root.name}-{digest}"


def _cache_path(root: Path) -> Path:
    cache_dir = Path(settings.test_run_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{_slug_for(root)}.json"


def save_last_run(result: RunOutcome) -> None:
    cache_file = _cache_path(Path(result.root))
    cache_file.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_last_run(root: str | Path) -> RunOutcome | None:
    root_path = Path(root).resolve()
    cache_file = _cache_path(root_path)
    if not cache_file.is_file():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return RunOutcome.from_dict(data)
