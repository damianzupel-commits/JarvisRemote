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
    # Triage con LLM (ver app/security/triage.py, agregado 2026-08-11 para
    # bajar el 44% de falso positivo medido contra OWASP Benchmark, ver
    # docs/owasp_benchmark/) -- None = todavía sin revisar (comportamiento
    # de siempre, todos los hallazgos cuentan como reales). "real" |
    # "false_positive" cuando sí se revisó; la razón del modelo queda en
    # triage_reasoning para que sea auditable, nunca una reclasificación
    # silenciosa. Campos opcionales con default None -- los ScanResult
    # cacheados ANTES de este cambio siguen deserializando bien.
    triage_status: str | None = None
    triage_reasoning: str | None = None

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


def resolve_finding(
    findings: list[Finding],
    finding_id: str | None = None,
    file: str | None = None,
    rule_id: str | None = None,
    line: int | None = None,
) -> Finding | None:
    """Busca un hallazgo por `finding_id` exacto, o -- si no se pasa o no
    matchea -- por (`file`, `rule_id`[, `line`]).

    Bug real 2026-08-09: `finding_id` es un hash interno opaco (ver
    `make_finding_id`) que el modelo tiene que citar de memoria entre un
    tool call y el siguiente para poder pedir un hallazgo puntual -- en un
    caso real (B608 en pygoat) lo alucinó dos veces seguidas, pidiendo un id
    que no existía. `file`+`rule_id`(+`line`) en cambio son texto que el
    modelo YA VIO tal cual en la respuesta de `security_scan_project`/
    `quality_scan_project` -- no hace falta memorizarlos, se citan.

    Si hay más de un hallazgo con el mismo (`file`, `rule_id`) y no se pasa
    `line`, NO se adivina cuál es -- se devuelve `None` (igual que si no
    matcheara nada), para no arriesgarse a aplicar un fix sobre el hallazgo
    equivocado cuando hay ambigüedad real (pasó en pygoat: dos B608 en el
    mismo archivo, líneas distintas).

    Si se pasa `line` pero NO matchea ningún hallazgo real -- bug real
    2026-08-09 (round 2): en las 3 corridas del caso B608 en pygoat, el
    modelo erró la línea (la inventó: 42, 100, 142...) en 2-3 de cada 3
    intentos antes de acertar, porque `security_get_finding` fallaba seco y
    lo mandaba a adivinar de nuevo a ciegas -- SI a pesar de la línea
    equivocada queda un único candidato real por (`file`, `rule_id`), se
    devuelve igual (tolerante: la línea probablemente vino mal recordada,
    el resto del pedido está bien). Si en cambio hay más de un candidato
    real (como los dos B608), la ambigüedad genuina sigue sin resolverse
    adivinando -- eso lo maneja el caller mostrando las líneas reales
    disponibles (ver `candidate_lines`) en vez de fallar en silencio otra
    vez con el mismo mensaje genérico."""
    if finding_id:
        by_id = next((f for f in findings if f.id == finding_id), None)
        if by_id is not None:
            return by_id
    if not file or not rule_id:
        return None
    candidates = [f for f in findings if f.file == file and f.rule_id == rule_id]
    if line is not None:
        exact = [f for f in candidates if f.line == line]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return None
        # la línea no matcheó ningún candidato real -- tolerante solo si de
        # todos modos hay un único candidato posible por (file, rule_id).
        if len(candidates) == 1:
            return candidates[0]
        return None
    if len(candidates) == 1:
        return candidates[0]
    return None


def candidate_lines(findings: list[Finding], file: str, rule_id: str) -> list[int]:
    """Líneas reales de los hallazgos que matchean (`file`, `rule_id`) --
    para armar un mensaje de error ACCIONABLE cuando `resolve_finding` no
    encuentra nada por ambigüedad o línea equivocada: en vez de "puede haber
    más de uno, agregá line" a secas (que no dice CUÁLES son las líneas
    válidas, forzando al modelo a seguir adivinando a ciegas), el caller
    puede mostrar la lista real."""
    return sorted({f.line for f in findings if f.file == file and f.rule_id == rule_id})


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
