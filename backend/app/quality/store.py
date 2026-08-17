"""Cache en disco del último escaneo de calidad por proyecto -- mismo patrón
que `app/security/store.py` (y `app/codebase/store.py`). Necesario para que
`code_apply_fix` pueda resolver un `finding_id` que el LLM vio en una
respuesta anterior sin tener que volver a correr los analizadores.

Vive en `settings.quality_scan_dir`, fuera del proyecto escaneado.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import settings
from ..findings.models import Finding, ScanResult, candidate_lines, resolve_finding


def _slug_for(root: Path) -> str:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return f"{root.name}-{digest}"


def _cache_path(root: Path) -> Path:
    cache_dir = Path(settings.quality_scan_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{_slug_for(root)}.json"


def save_scan(result: ScanResult) -> None:
    cache_file = _cache_path(Path(result.root))
    cache_file.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_scan(root: str | Path) -> ScanResult | None:
    root_path = Path(root).resolve()
    cache_file = _cache_path(root_path)
    if not cache_file.is_file():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return ScanResult.from_dict(data)


def find_finding(
    root: str | Path,
    finding_id: str | None = None,
    file: str | None = None,
    rule_id: str | None = None,
    line: int | None = None,
) -> Finding | None:
    """Ver `resolve_finding` (app/findings/models.py) para el criterio real de
    búsqueda -- `finding_id` exacto primero, `file`+`rule_id`(+`line`) como
    fallback (más robusto para el LLM que un hash de memoria)."""
    result = load_scan(root)
    if result is None:
        return None
    return resolve_finding(result.findings, finding_id=finding_id, file=file, rule_id=rule_id, line=line)


def find_candidate_lines(root: str | Path, file: str, rule_id: str) -> list[int]:
    """Ver `candidate_lines` (app/findings/models.py) -- líneas reales para un
    mensaje de error accionable cuando `find_finding` no resuelve nada."""
    result = load_scan(root)
    if result is None:
        return []
    return candidate_lines(result.findings, file=file, rule_id=rule_id)
