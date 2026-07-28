"""Vault de notas estilo Obsidian: archivos Markdown reales con frontmatter
YAML, organizados en `settings.obsidian_vault_path` -- abribles con Obsidian
de verdad si el usuario quiere, no un formato propietario.

Evolución de `app/tools/reflect.py` (que queda intacto, sigue siendo un log
rápido de una línea vía JSONL -- ver decisión en la sesión que agregó este
módulo): acá cada nota es un archivo propio con título, tags, autor y
contenido largo, y coexisten notas de dos autores distintos sin mezclarse --
la separación es doble a propósito: carpeta (`jarvis/` vs `human/`) *y* campo
`author` en el frontmatter, así un archivo movido a mano entre carpetas sigue
siendo identificable, y un filtro por metadata no depende de en qué carpeta
esté.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from ..config import settings

AUTHORS = ("jarvis", "human")

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


@dataclass
class VaultNote:
    id: str  # "<author>/<slug>", único, también nombre de archivo relativo al vault
    title: str
    author: str
    tags: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    content: str = ""

    @property
    def links(self) -> list[str]:
        return _WIKILINK_RE.findall(self.content)

    def to_summary_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "tags": self.tags,
            "created": self.created,
            "updated": self.updated,
        }

    def to_dict(self) -> dict:
        return {**self.to_summary_dict(), "content": self.content, "links": self.links}


def _vault_root() -> Path:
    root = Path(settings.obsidian_vault_path)
    for author in AUTHORS:
        (root / author).mkdir(parents=True, exist_ok=True)
    return root


def _slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "nota"


def _note_path(note_id: str) -> Path:
    if "/" not in note_id:
        raise ValueError(f"id de nota inválido: '{note_id}'")
    author, slug = note_id.split("/", 1)
    if author not in AUTHORS:
        raise ValueError(f"autor inválido en id de nota: '{note_id}'")
    return _vault_root() / author / f"{slug}.md"


def _note_from_path(path: Path, author: str) -> VaultNote:
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    slug = path.stem
    return VaultNote(
        id=f"{author}/{slug}",
        title=post.get("title", slug),
        author=post.get("author", author),
        tags=list(post.get("tags", []) or []),
        created=post.get("created", ""),
        updated=post.get("updated", ""),
        content=post.content,
    )


def save_note(
    title: str,
    content: str,
    author: str,
    tags: list[str] | None = None,
    note_id: str | None = None,
) -> VaultNote:
    if author not in AUTHORS:
        raise ValueError(f"author debe ser uno de {AUTHORS}, recibido '{author}'")

    now = datetime.now(timezone.utc).isoformat()
    tags = tags or []

    if note_id is not None:
        note_id_author = note_id.split("/", 1)[0]
        if note_id_author != author:
            raise ValueError(f"note_id '{note_id}' pertenece al autor '{note_id_author}', no a '{author}'")
        path = _note_path(note_id)
        created = now
        if path.is_file():
            existing = _note_from_path(path, author)
            created = existing.created or now
    else:
        slug = _slugify(title)
        path = _vault_root() / author / f"{slug}.md"
        # Evita pisar una nota existente con el mismo título -- le agrega un
        # sufijo numérico hasta encontrar un nombre libre.
        counter = 2
        while path.is_file():
            path = _vault_root() / author / f"{slug}-{counter}.md"
            counter += 1
        created = now

    post = frontmatter.Post(content, title=title, author=author, tags=tags, created=created, updated=now)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")

    return VaultNote(id=f"{author}/{path.stem}", title=title, author=author, tags=tags, created=created, updated=now, content=content)


def read_note(note_id: str) -> VaultNote:
    path = _note_path(note_id)
    if not path.is_file():
        raise FileNotFoundError(f"Nota '{note_id}' no existe")
    author = note_id.split("/", 1)[0]
    return _note_from_path(path, author)


def list_notes(author: str | None = None, tag: str | None = None) -> list[VaultNote]:
    root = _vault_root()
    authors = [author] if author else list(AUTHORS)
    notes = []
    for a in authors:
        for path in sorted((root / a).glob("*.md")):
            note = _note_from_path(path, a)
            if tag and tag not in note.tags:
                continue
            notes.append(note)
    notes.sort(key=lambda n: n.updated, reverse=True)
    return notes


def search_notes(query: str, author: str | None = None, limit: int = 10) -> list[VaultNote]:
    query_words = set(query.lower().split())
    scored: list[tuple[int, VaultNote]] = []
    for note in list_notes(author=author):
        haystack = f"{note.title} {note.content} {' '.join(note.tags)}".lower()
        haystack_words = set(haystack.split())
        score = len(query_words & haystack_words)
        if score > 0:
            scored.append((score, note))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for _, note in scored[:limit]]


def delete_note(note_id: str) -> None:
    path = _note_path(note_id)
    if not path.is_file():
        raise FileNotFoundError(f"Nota '{note_id}' no existe")
    path.unlink()


def build_graph() -> dict:
    """Nodos = todas las notas; edges = wikilinks resueltos por título (igual
    que el grafo real de Obsidian). Un link a un título que no existe se
    ignora -- no fabricamos un nodo fantasma para él."""
    notes = list_notes()
    by_title = {note.title.strip().lower(): note.id for note in notes}

    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for note in notes:
        for link_title in note.links:
            target_id = by_title.get(link_title.strip().lower())
            if target_id is None or target_id == note.id:
                continue
            key = tuple(sorted((note.id, target_id)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": note.id, "target": target_id})

    return {"nodes": [n.to_summary_dict() for n in notes], "edges": edges}
