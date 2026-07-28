"""Endpoints HTTP que consume la pestaña "Obsidian" de la ventana de Jarvis
(tray-app/ui/obsidian_view.py). El POST de creación/edición está fijado a
author="human" -- es el único punto de entrada de escritura que tiene la UI,
así que estructuralmente no puede crear una nota "jarvis" (esas solo las crea
la tool `obsidian_save_note`, ver `app/tools/obsidian.py`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import verify_api_key
from ..obsidian import vault

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"], dependencies=[Depends(verify_api_key)])


class NoteIn(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    note_id: str | None = None  # si se manda, edita esa nota humana existente


@router.get("/notes")
async def list_notes(author: str | None = None, tag: str | None = None) -> dict:
    notes = vault.list_notes(author=author, tag=tag)
    return {"notes": [n.to_summary_dict() for n in notes]}


@router.get("/graph")
async def get_graph() -> dict:
    return vault.build_graph()


@router.get("/notes/{author}/{slug}")
async def get_note(author: str, slug: str) -> dict:
    try:
        note = vault.read_note(f"{author}/{slug}")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return note.to_dict()


@router.post("/notes")
async def create_or_update_note(body: NoteIn) -> dict:
    note = vault.save_note(title=body.title, content=body.content, author="human", tags=body.tags, note_id=body.note_id)
    return note.to_summary_dict()


@router.delete("/notes/{author}/{slug}")
async def remove_note(author: str, slug: str) -> dict:
    if author != "human":
        raise HTTPException(status_code=403, detail="Solo se pueden borrar notas humanas desde la UI")
    try:
        vault.delete_note(f"{author}/{slug}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"deleted": f"{author}/{slug}"}
