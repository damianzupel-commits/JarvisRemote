"""Dataclasses del paso de 'testear real' -- mismo criterio que
`app/security/models.py`/`app/codebase/models.py`: simples, serializables a
dict, sin lógica propia."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class DetectedCommand:
    command: str
    language: str
    reason: str  # qué marcador se usó para detectarlo, en criollo

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunOutcome:
    root: str
    ran_at: str
    detected: bool  # False si no se encontró ningún comando de test real -- no confundir con "pasó"/"falló"
    command: str | None
    language: str | None
    detect_reason: str | None
    exit_code: int | None
    passed: bool
    timed_out: bool
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "RunOutcome":
        return RunOutcome(**data)
