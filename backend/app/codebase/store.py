"""Cache en disco de índices ya construidos (`build_index` es lento en
proyectos grandes -- no tiene sentido re-parsear todo el árbol en cada
consulta de la UI o del LLM). Un índice por proyecto, identificado por su
ruta absoluta; `get_or_build` reusa el cacheado salvo `refresh=True`.

Vive en `settings.codebase_index_dir`, fuera del proyecto indexado -- nunca
escribimos nada dentro del repo del usuario.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import settings
from .indexer import build_index
from .models import CodebaseIndex


def _slug_for(root: Path) -> str:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return f"{root.name}-{digest}"


def _cache_path(root: Path) -> Path:
    cache_dir = Path(settings.codebase_index_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{_slug_for(root)}.json"


def load_cached(root: str | Path) -> CodebaseIndex | None:
    root_path = Path(root).resolve()
    cache_file = _cache_path(root_path)
    if not cache_file.is_file():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return CodebaseIndex.from_dict(data)


def save_cache(index: CodebaseIndex) -> None:
    cache_file = _cache_path(Path(index.root))
    cache_file.write_text(json.dumps(index.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def get_or_build(root: str | Path, refresh: bool = False) -> CodebaseIndex:
    root_path = Path(root).resolve()
    if not refresh:
        cached = load_cached(root_path)
        if cached is not None:
            return cached
    index = build_index(root_path)
    save_cache(index)
    return index


def list_cached_projects() -> list[dict]:
    cache_dir = Path(settings.codebase_index_dir)
    if not cache_dir.is_dir():
        return []
    results = []
    for f in sorted(cache_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        results.append(
            {
                "root": data.get("root"),
                "indexed_at": data.get("indexed_at"),
                "file_count": data.get("file_count"),
                "primary_language": data.get("primary_language"),
            }
        )
    return results
