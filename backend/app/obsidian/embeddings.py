"""Embeddings semánticos para el vault de Obsidian (ver `app/obsidian/vault.py`).

Corren 100% local: pegan contra el server OpenAI-compatible de LM Studio
(`settings.embedding_base_url` -- deliberadamente NO el `lmstudio_base_url`
que usa el chat, ver comentario en app/config.py) pidiendo el modelo de
embeddings que el usuario tenga cargado ahí (`settings.embedding_model`,
default `text-embedding-nomic-embed-text-v1.5`). Nada se manda a una nube --
si ese server no está corriendo o no tiene el modelo cargado, `get_embedding`
devuelve `None` y quien llama cae a búsqueda por palabra clave (ver
`vault.search_notes`).

El índice de vectores es un único JSON en `settings.obsidian_embeddings_path`
(por default `backend/data/`, gitignoreado -- mismo criterio que
`codebase_index_dir`/`security_scan_dir`: nunca vive dentro del vault ni del
proyecto indexado). Para ~50 notas esto alcanza de sobra; no se justifica una
base vectorial (Chroma/Pinecone) para este volumen.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from openai import OpenAI, OpenAIError

from ..config import settings
from . import profile as _profile

_REQUEST_TIMEOUT_SECONDS = 10.0


def get_embedding(text: str) -> list[float] | None:
    """Devuelve el vector de embedding de `text`, o `None` si LM Studio no
    está disponible (server caído, modelo no cargado, sin red) -- nunca
    levanta, para que el caller pueda degradar a keyword search sin romper."""
    text = text.strip()
    if not text:
        return None
    try:
        client = OpenAI(base_url=settings.embedding_base_url, api_key="lm-studio", timeout=_REQUEST_TIMEOUT_SECONDS)
        response = client.embeddings.create(model=settings.embedding_model, input=text)
        return list(response.data[0].embedding)
    except (OpenAIError, OSError, ValueError):
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _index_path() -> Path:
    # Mismo override de perfil que vault.py::_vault_root() -- ver
    # app/obsidian/profile.py. Sin perfil activo, el índice de siempre.
    path = Path(_profile.current_embeddings_path(settings.obsidian_embeddings_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_index() -> dict[str, list[float]]:
    path = _index_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_index(index: dict[str, list[float]]) -> None:
    _index_path().write_text(json.dumps(index), encoding="utf-8")


def update_note_embedding(note_id: str, text: str) -> None:
    """Calcula y persiste el embedding de una nota. No-op silencioso si LM
    Studio no responde -- la nota se guarda igual, solo queda sin vector
    hasta el próximo reindex (ver `reindex_all`)."""
    vector = get_embedding(text)
    if vector is None:
        return
    index = load_index()
    index[note_id] = vector
    save_index(index)


def remove_note_embedding(note_id: str) -> None:
    index = load_index()
    if index.pop(note_id, None) is not None:
        save_index(index)


def reindex_all(notes: list[tuple[str, str]]) -> dict[str, int]:
    """Recalcula el embedding de cada nota en `notes` (lista de `(note_id,
    texto_a_embeder)`) y reemplaza el índice completo. Usado para backfill de
    notas que ya existían antes de que este módulo existiera. Devuelve un
    resumen {"indexed": N, "skipped": M} -- `skipped` cuenta notas donde LM
    Studio no devolvió embedding (server caído a mitad de reindex, por
    ejemplo), que quedan afuera del índice hasta el próximo intento."""
    index: dict[str, list[float]] = {}
    skipped = 0
    for note_id, text in notes:
        vector = get_embedding(text)
        if vector is None:
            skipped += 1
            continue
        index[note_id] = vector
    save_index(index)
    return {"indexed": len(index), "skipped": skipped}
