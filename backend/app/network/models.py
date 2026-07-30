"""Dataclasses del resultado de un escaneo nmap -- mismo espíritu que
`app/findings/models.py::Finding` (formato normalizado, no el JSON/XML crudo
de cada herramienta), pero con el esquema propio de un hallazgo de RED
(host/puerto/servicio) en vez de uno de código (archivo/línea)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class PortFinding:
    host: str  # IP real del host (ya resuelta, no el hostname pedido por el usuario)
    hostname: str | None
    port: int
    protocol: str  # "tcp" | "udp"
    state: str  # "open" | "closed" | "filtered" | ...
    service: str | None
    product: str | None
    version: str | None
    # Severidad derivada de scripts NSE `--script vuln` (ver `scanner._vuln_severity`)
    # -- None si scan_type no corrió esos scripts o ninguno marcó el puerto como
    # vulnerable. nmap NO expone una severidad propia como Semgrep/Bandit/Trivy;
    # esto es una heurística sobre el texto "State: VULNERABLE"/"LIKELY VULNERABLE"
    # que sí es una convención real de las NSE vuln scripts.
    severity: str | None
    # Salida cruda de cada script NSE corrido sobre este puerto (id + output tal
    # cual lo imprime nmap) -- se conserva completa para que el LLM la lea, en vez
    # de resumirla acá y perder detalle.
    scripts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NetworkScanResult:
    target: str
    scan_type: str
    command: list[str]
    started_at: str
    finished_at: str
    hosts_up: int
    findings: list[PortFinding]
    raw_summary: str  # línea final "Nmap done: ..." tal cual la imprime nmap

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "scan_type": self.scan_type,
            "command": self.command,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "hosts_up": self.hosts_up,
            "findings": [f.to_dict() for f in self.findings],
            "raw_summary": self.raw_summary,
        }
