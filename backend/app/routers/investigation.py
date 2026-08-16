"""Endpoints HTTP que consume la futura pestaña "Investigación" de la
ventana de Jarvis (tray-app/ui/investigation_view.py) -- mismo criterio que
routers/codebase.py: el servidor devuelve datos CRUDOS (nodos/aristas +
centralidad/confianza como floats), la UI decide cómo pintarlos (ver
tray-app/ui/investigation_colors.py) -- ningún color se decide acá."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from ..config import settings
from ..investigation import case_store, graph_metrics, timeline as timeline_module

router = APIRouter(prefix="/api/investigation", tags=["investigation"], dependencies=[Depends(verify_api_key)])


def _load_active_case(case_id: str) -> tuple[list, list]:
    """Compartido entre /graph y /timeline -- ver el comentario en
    get_case_graph sobre por qué hace falta chequear el directorio a mano
    (read_nodes/read_edges no distinguen "caso vacío" de "caso inexistente")."""
    case_dir = case_store.case_dir_for(settings.investigation_cases_dir, case_id)
    if not case_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"El caso '{case_id}' no existe")

    nodes = case_store.read_nodes(settings.investigation_cases_dir, case_id)
    edges = case_store.read_edges(settings.investigation_cases_dir, case_id)
    active_nodes = [n for n in nodes if not n.retracted]
    active_edges = [e for e in edges if not e.retracted]
    return active_nodes, active_edges


@router.get("/cases")
async def list_cases() -> dict:
    cases_root = Path(settings.investigation_cases_dir)
    cases = []
    if cases_root.is_dir():
        for case_dir in sorted(cases_root.iterdir()):
            case_json = case_dir / "case.json"
            if case_json.is_file():
                cases.append(json.loads(case_json.read_text(encoding="utf-8")))
    return {"cases": cases}


@router.get("/{case_id}/graph")
async def get_case_graph(case_id: str) -> dict:
    """Nodos con `centrality` (betweenness real, 0 si el grafo es muy chico
    para que tenga sentido) y `confidence` (promedio de confianza de
    aristas incidentes + campo propio si es Persona -- `null` si no hay
    ningún dato real todavía, nunca inventado). Aristas retractadas y nodos
    retractados NO aparecen -- esto es la vista del caso TAL COMO ESTÁ
    ahora, no el historial completo (para eso está el log, ver
    case_store.rebuild_from_log).

    Bug real evitado acá: case_store.read_nodes/read_edges NO tiran para un
    case_id inexistente -- devuelven listas vacías (mismo comportamiento
    que "caso real sin nodos todavía"), así que hay que chequear
    explícitamente que el directorio del caso exista para poder distinguir
    "caso vacío" de "caso que no existe" (ver _load_active_case)."""
    active_nodes, active_edges = _load_active_case(case_id)

    centrality = graph_metrics.compute_centrality(active_nodes, active_edges)
    confidence = graph_metrics.compute_confidence(active_nodes, active_edges)
    communities = graph_metrics.detect_communities(active_nodes, active_edges)

    return {
        "nodes": [
            {
                "id": n.id,
                "tipo": n.tipo.value,
                "campos": n.campos,
                "centrality": centrality.get(n.id, 0.0),
                "confidence": confidence.get(n.id),
                "community": communities.get(n.id),
            }
            for n in active_nodes
        ],
        "edges": [
            {"id": e.id, "tipo": e.tipo.value, "source": e.origen, "target": e.destino, "confianza": e.confianza}
            for e in active_edges
        ],
    }


@router.get("/{case_id}/timeline")
async def get_case_timeline(case_id: str, entity_id: str | None = None) -> dict:
    """Línea de tiempo cruzada (spec sección 4) -- opcionalmente filtrada a
    un solo `entity_id` (lo que la UI llama cuando seleccionás un nodo del
    grafo). Incluye `contradictions`: pares de aristas donde la misma
    entidad aparece en dos Host distintos demasiado cerca en el tiempo --
    NUNCA resueltas automáticamente, solo señaladas para revisión manual."""
    active_nodes, active_edges = _load_active_case(case_id)

    entries = timeline_module.build_timeline(active_nodes, active_edges)
    if entity_id:
        entries = timeline_module.timeline_for_entity(entries, entity_id)
    contradictions = timeline_module.detect_contradictions(active_nodes, active_edges)

    return {
        "entries": [
            {
                "timestamp_utc": e.timestamp_utc, "kind": e.kind,
                "entity_ids": list(e.entity_ids), "description": e.description, "source_id": e.source_id,
            }
            for e in entries
        ],
        "contradictions": [
            {
                "entity_id": c.entity_id, "edge_a_id": c.edge_a_id, "edge_b_id": c.edge_b_id,
                "timestamp_a": c.timestamp_a, "timestamp_b": c.timestamp_b,
                "delta_seconds": c.delta_seconds, "reason": c.reason,
            }
            for c in contradictions
        ],
    }
