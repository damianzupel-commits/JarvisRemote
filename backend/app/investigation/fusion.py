"""Fusión de identidades (spec sección 3, paso 7 del orden de
implementación: "cuando el sistema sugiere mismo_que, requiere confirmación
tuya. Igual que hoy pedís confirmación antes de aplicar un fix.").

Rol del modelo acotado a "normalización de variantes de una misma cadena"
(spec sección 5, punto 2) -- dados DOS nodos puntuales que Damian (o el
propio modelo, al notar algo sospechoso) señala como candidatos, el modelo
compara sus campos y PROPONE si parecen la misma entidad real, con su
razonamiento -- nunca decide, nunca escribe la arista solo. Mismo patrón
pendiente-de-confirmación que ner.py, con su propio almacén
(`fusion_proposals.jsonl`) porque la forma de una propuesta de fusión (dos
ids de nodo YA EXISTENTES + una arista candidata) no es la de una propuesta
de NER (campos de un nodo nuevo) -- no tiene sentido forzarlas al mismo
esquema.

Decisión de Damian (2026-08-12, re-confirmada acá): los dos nodos
originales NUNCA se combinan en uno solo. `confirm_fusion` crea una arista
`mismo_que` real entre los dos nodos EXISTENTES -- ambos siguen intactos,
con su proveniencia propia, así que retractar la fusión más adelante
(`case_store.retract_edge`) no pierde nada de ninguno de los dos.

`artefacto_origen` de la arista de fusión: una fusión no sale de ingestar
un documento puntual, sale de comparar dos nodos ya confirmados -- no hay
un Archivo real de origen. Se usa el string descriptivo `"fusion_analisis"`
en vez de inventar un id de Archivo que no existe -- mismo criterio que ya
usa el propio test suite del módulo para aristas manuales sin artefacto
real (`artefacto_origen="manual"`, ver test_investigation_case_store.py)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..llm_client import client
from . import case_store
from . import log as log_module
from .models import DerivadaPor, Edge, EdgeType, Node, make_edge

_ARTEFACTO_ORIGEN_FUSION = "fusion_analisis"
_MAX_OUTPUT_TOKENS = 512


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FusionProposal:
    id: str
    node_a_id: str
    node_b_id: str
    confianza: float
    razon: str
    status: str  # "pendiente" | "confirmado" | "rechazado"
    created_at: str
    resolved_at: str | None = None
    resolved_reason: str | None = None
    edge_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "node_a_id": self.node_a_id, "node_b_id": self.node_b_id,
            "confianza": self.confianza, "razon": self.razon, "status": self.status,
            "created_at": self.created_at, "resolved_at": self.resolved_at,
            "resolved_reason": self.resolved_reason, "edge_id": self.edge_id,
        }

    @staticmethod
    def from_dict(data: dict) -> "FusionProposal":
        return FusionProposal(
            id=data["id"], node_a_id=data["node_a_id"], node_b_id=data["node_b_id"],
            confianza=data["confianza"], razon=data["razon"], status=data["status"],
            created_at=data["created_at"], resolved_at=data.get("resolved_at"),
            resolved_reason=data.get("resolved_reason"), edge_id=data.get("edge_id"),
        )


_SYSTEM_PROMPT = (
    "Sos un asistente de normalización de identidades para un caso de investigación. Te dan los campos de "
    "DOS entidades del mismo tipo y tenés que evaluar si parecen ser la MISMA entidad real mencionada de "
    "forma distinta en dos fuentes (ej. el mismo handle escrito distinto, el mismo nombre con una variante), "
    "o si son entidades DISTINTAS que solo se parecen superficialmente (ej. dos personas distintas con el "
    "mismo nombre común). NUNCA concluyas con certeza total -- esto es una propuesta que un humano va a "
    "confirmar o rechazar. Respondé SOLO con JSON: "
    '{"confianza": 0.0 a 1.0, "razon": "explicación breve de qué campos coinciden o no y por qué"}.'
)


def _parse_proposal_response(node_a: Node, node_b: Node, raw: str) -> tuple[float, str]:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"El modelo no devolvió JSON parseable para la propuesta de fusión: {raw[:300]!r}")
    data = json.loads(raw[start : end + 1])
    confianza = float(data.get("confianza", 0.0))
    if not (0.0 <= confianza <= 1.0):
        raise ValueError(f"confianza fuera de rango [0,1]: {confianza!r}")
    return confianza, data.get("razon", "")


async def propose_fusion(node_a: Node, node_b: Node) -> FusionProposal:
    """SOLO propone -- nunca escribe al caso. Los dos nodos tienen que ser
    del MISMO tipo (fusionar una Persona con un Host no tiene sentido
    conceptual -- "misma identidad" solo aplica entre entidades
    comparables)."""
    if node_a.tipo != node_b.tipo:
        raise ValueError(
            f"No se puede proponer fusión entre tipos distintos ({node_a.tipo.value} y {node_b.tipo.value})"
        )

    user_msg = (
        f"Tipo de entidad: {node_a.tipo.value}\n"
        f"Entidad A (id={node_a.id}): {json.dumps(node_a.campos, ensure_ascii=False)}\n"
        f"Entidad B (id={node_b.id}): {json.dumps(node_b.campos, ensure_ascii=False)}"
    )
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user_msg}],
        temperature=0,
        max_tokens=_MAX_OUTPUT_TOKENS,
    )
    raw = response.choices[0].message.content or ""
    confianza, razon = _parse_proposal_response(node_a, node_b, raw)

    return FusionProposal(
        id=uuid.uuid4().hex, node_a_id=node_a.id, node_b_id=node_b.id,
        confianza=confianza, razon=razon, status="pendiente", created_at=_now(),
    )


def _proposals_path(case_dir: Path) -> Path:
    return case_dir / "fusion_proposals.jsonl"


def _write_proposals(case_dir: Path, proposals: list[FusionProposal]) -> None:
    # Mismo criterio que ner.py -- una propuesta pendiente es un borrador de
    # trabajo, no "estado del caso" todavía, así que no se commitea a git.
    _proposals_path(case_dir).write_text(
        "".join(json.dumps(p.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n" for p in proposals),
        encoding="utf-8",
    )


def save_proposal(cases_dir: str | Path, case_id: str, proposal: FusionProposal) -> FusionProposal:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")
    existing = read_proposals(cases_dir, case_id)
    existing.append(proposal)
    _write_proposals(case_dir, existing)
    return proposal


def read_proposals(cases_dir: str | Path, case_id: str, status: str | None = None) -> list[FusionProposal]:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    path = _proposals_path(case_dir)
    if not path.is_file():
        return []
    all_proposals = [
        FusionProposal.from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if status is None:
        return all_proposals
    return [p for p in all_proposals if p.status == status]


def confirm_fusion(cases_dir: str | Path, keys_dir: str | Path, case_id: str, proposal_id: str) -> Edge:
    """Crea la arista `mismo_que` real entre los DOS nodos existentes --
    nunca los combina (ver docstring del módulo)."""
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")
    proposals = read_proposals(cases_dir, case_id)
    target = next((p for p in proposals if p.id == proposal_id), None)
    if target is None:
        raise ValueError(f"No existe la propuesta de fusión '{proposal_id}' en el caso '{case_id}'")
    if target.status != "pendiente":
        raise ValueError(f"La propuesta de fusión '{proposal_id}' ya fue resuelta ({target.status})")

    edge = make_edge(
        tipo=EdgeType.MISMO_QUE, origen=target.node_a_id, destino=target.node_b_id,
        artefacto_origen=_ARTEFACTO_ORIGEN_FUSION, confianza=target.confianza, derivada_por=DerivadaPor.MODELO,
    )
    case_store.add_edge(cases_dir, keys_dir, case_id, edge)

    at = _now()
    target.status = "confirmado"
    target.resolved_at = at
    target.edge_id = edge.id
    log_module.append_entry(
        case_dir / "log.jsonl", keys_dir, op="confirm_fusion",
        payload={"id": proposal_id, "edge_id": edge.id, "at": at},
    )
    _write_proposals(case_dir, proposals)
    return edge


def reject_fusion(cases_dir: str | Path, keys_dir: str | Path, case_id: str, proposal_id: str, reason: str) -> FusionProposal:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")
    proposals = read_proposals(cases_dir, case_id)
    target = next((p for p in proposals if p.id == proposal_id), None)
    if target is None:
        raise ValueError(f"No existe la propuesta de fusión '{proposal_id}' en el caso '{case_id}'")
    if target.status != "pendiente":
        raise ValueError(f"La propuesta de fusión '{proposal_id}' ya fue resuelta ({target.status})")

    at = _now()
    target.status = "rechazado"
    target.resolved_at = at
    target.resolved_reason = reason
    log_module.append_entry(
        case_dir / "log.jsonl", keys_dir, op="reject_fusion",
        payload={"id": proposal_id, "reason": reason, "at": at},
    )
    _write_proposals(case_dir, proposals)
    return target
