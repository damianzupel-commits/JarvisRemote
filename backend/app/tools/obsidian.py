"""Tools del vault de notas estilo Obsidian (ver `app/obsidian/vault.py`).

El LLM solo puede *guardar* notas como autor "jarvis" -- las notas de autoría
humana se cargan desde la pestaña Obsidian de la UI (`POST /api/obsidian/notes`
en `app/routers/obsidian.py`), nunca a través de esta tool. Es la forma en que
se garantiza que las dos autorías no se mezclen sin distinción: el único
camino de escritura que ve el modelo está atado a un autor fijo.
"""

from __future__ import annotations

from ..obsidian import vault
from . import register_tool


@register_tool(
    name="obsidian_save_note",
    description=(
        "Guarda una nota propia en el vault de conocimiento (Obsidian) -- para ideas, decisiones o "
        "hallazgos que merecen más que una línea (si es una sola idea corta y abstracta, usar mejor "
        "jarvis_reflect). La nota queda firmada como tuya (autor 'jarvis'), separada de las notas del "
        "programador humano."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Título de la nota."},
            "content": {"type": "string", "description": "Contenido en Markdown. Podés usar [[wikilinks]] a otras notas."},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags opcionales para categorizar la nota."},
        },
        "required": ["title", "content"],
    },
)
def obsidian_save_note(title: str, content: str, tags: list[str] | None = None) -> dict:
    note = vault.save_note(title=title, content=content, author="jarvis", tags=tags)
    return note.to_summary_dict()


@register_tool(
    name="obsidian_search_notes",
    description=(
        "Busca notas relevantes en el vault de conocimiento por palabras clave (título, contenido y "
        "tags). Por default busca en notas de ambos autores; se puede filtrar a uno solo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Palabras clave a buscar."},
            "author": {"type": "string", "enum": ["jarvis", "human"], "description": "Filtrar por autor (opcional)."},
            "limit": {"type": "integer", "description": "Máximo de resultados (default 5)."},
        },
        "required": ["query"],
    },
)
def obsidian_search_notes(query: str, author: str | None = None, limit: int = 5) -> dict:
    notes = vault.search_notes(query, author=author, limit=limit)
    return {"query": query, "results": [n.to_dict() for n in notes]}


@register_tool(
    name="obsidian_list_notes",
    description="Lista las notas del vault de conocimiento, opcionalmente filtradas por autor y/o tag.",
    parameters={
        "type": "object",
        "properties": {
            "author": {"type": "string", "enum": ["jarvis", "human"], "description": "Filtrar por autor (opcional)."},
            "tag": {"type": "string", "description": "Filtrar por tag (opcional)."},
        },
        "required": [],
    },
)
def obsidian_list_notes(author: str | None = None, tag: str | None = None) -> dict:
    notes = vault.list_notes(author=author, tag=tag)
    return {"notes": [n.to_summary_dict() for n in notes]}
