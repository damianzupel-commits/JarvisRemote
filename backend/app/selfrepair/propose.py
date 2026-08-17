"""Genera una propuesta de auto-fix: SIEMPRE dry-run (nunca escribe nada acá
-- ver `app/codeedit/fixer.py::apply_fix(confirm=False)`), la guarda en
`app/selfrepair/store.py`, y si viene de una nota de diagnóstico de
`app/introspection/` (Opción B), le adjunta el diff propuesto a esa MISMA
nota -- para que la propuesta sea revisable en el vault, no solo texto de
chat que se pierde apenas se cierra la conversación (mismo criterio que
`audit_generate_report`/las notas de B)."""

from __future__ import annotations

from datetime import datetime, timezone

from ..codeedit import fixer
from ..obsidian import vault
from . import gate, store
from .models import SelfFixProposal


def _attach_to_note(note_id: str, proposal: SelfFixProposal) -> None:
    try:
        note = vault.read_note(note_id)
    except FileNotFoundError:
        return
    section = (
        f"\n\n## Propuesta de fix (proposal_id: {proposal.proposal_id})\n"
        f"Archivo: `{proposal.file}`\n\n"
        f"Razón: {proposal.rationale}\n\n"
        f"```diff\n{proposal.diff}\n```\n\n"
        f"Para aplicar de verdad: confirmá '{proposal.proposal_id}' explícitamente en el chat."
    )
    vault.save_note(
        title=note.title,
        content=note.content + section,
        author=note.author,
        tags=note.tags,
        category=note.category,
        note_id=note_id,
    )


def propose_fix(
    *,
    file: str,
    old_snippet: str,
    new_snippet: str,
    rationale: str,
    commit_message: str,
    note_id: str | None = None,
) -> SelfFixProposal:
    result = fixer.apply_fix(
        root=str(gate.JARVIS_OWN_SOURCE_ROOT),
        file=file,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        commit_message=commit_message,
        confirm=False,
    )
    proposal = SelfFixProposal(
        proposal_id=gate.generate_proposal_id(),
        file=result["file"],
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        diff=result["diff"],
        commit_message=commit_message,
        rationale=rationale,
        status="proposed",
        created_at=datetime.now(timezone.utc).isoformat(),
        note_id=note_id,
    )
    store.save_proposal(proposal)
    if note_id:
        _attach_to_note(note_id, proposal)
    return proposal
