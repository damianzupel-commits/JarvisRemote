"""Dataclass de una propuesta de auto-fix -- ver app/selfrepair/gate.py y
propose.py. Serializable a dict, sin lógica propia (mismo criterio que
app/testing/models.py)."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class SelfFixProposal:
    proposal_id: str
    file: str  # relativo a gate.JARVIS_OWN_SOURCE_ROOT
    old_snippet: str
    new_snippet: str
    diff: str
    commit_message: str
    rationale: str
    status: str  # "proposed" | "applied"
    created_at: str
    note_id: str | None = None
    applied_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "SelfFixProposal":
        return SelfFixProposal(**data)
