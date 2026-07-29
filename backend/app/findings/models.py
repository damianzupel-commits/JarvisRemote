"""Dataclasses de hallazgos, compartidas entre `security/` (vulnerabilidades:
Semgrep/Bandit/Trivy) y `quality/` (bugs generales: Ruff/mypy/ESLint/tsc/detekt).

Cada escáner real devuelve su propio JSON con un esquema distinto; estas
dataclasses son el formato normalizado que ve el resto del sistema, para que el
LLM no tenga que aprender un esquema por herramienta.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field


@dataclass
class Finding:
    id: str
    tool: str  # "semgrep" | "bandit" | "trivy" | "ruff" | "mypy" | "eslint" | "tsc" | "detekt"
    file: str  # relativo a la raíz del proyecto, separadores '/'
    line: int  # 1-indexed
    end_line: int | None
    severity: str  # normalizado: "critical" | "high" | "medium" | "low" | "info"
    rule_id: str
    message: str
    cwe: list[str] = field(default_factory=list)
    owasp: list[str] = field(default_factory=list)
    confidence: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Finding":
        return Finding(**data)


def make_finding_id(tool: str, file: str, line: int, rule_id: str) -> str:
    """ID estable (no aleatorio) -- el mismo hallazgo real produce el mismo id en
    corridas sucesivas, así `code_apply_fix` lo puede referenciar por id entre
    un scan y el siguiente sin depender de mantener el objeto en memoria."""
    digest = hashlib.sha256(f"{tool}:{file}:{line}:{rule_id}".encode("utf-8")).hexdigest()
    return digest[:16]


@dataclass
class ScanResult:
    root: str
    scanned_at: str
    tools_run: list[str]
    tools_skipped: dict[str, str]  # tool -> motivo (no instalado, sin archivos aplicables)
    findings: list[Finding]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "scanned_at": self.scanned_at,
            "tools_run": self.tools_run,
            "tools_skipped": self.tools_skipped,
            "findings": [f.to_dict() for f in self.findings],
        }

    @staticmethod
    def from_dict(data: dict) -> "ScanResult":
        return ScanResult(
            root=data["root"],
            scanned_at=data["scanned_at"],
            tools_run=data["tools_run"],
            tools_skipped=data["tools_skipped"],
            findings=[Finding.from_dict(f) for f in data["findings"]],
        )
