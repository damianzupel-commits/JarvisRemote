"""Timeline forense (spec sección 4): normalización de timestamps a UTC
preservando el offset original, línea de tiempo cruzada filtrable por
entidad, y detección de contradicciones (misma entidad en dos lugares
incompatibles a la vez, marcada para revisión manual -- nunca resuelta
sola)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser

from .models import Edge, Node, NodeType

_DEFAULT_CONTRADICTION_WINDOW_SECONDS = 300.0  # 5 minutos


@dataclass(frozen=True)
class NormalizedTimestamp:
    utc: str  # ISO 8601 en UTC, siempre con offset +00:00 explícito
    original_offset: str | None  # el offset tal como venía en el dato crudo (None si el dato no traía ninguno)
    raw: str


def normalize_timestamp(raw: str) -> NormalizedTimestamp:
    """Sin timezone explícita en el dato crudo, se asume que YA está en UTC
    -- default conservador: asumir una zona horaria local arbitraria (ej.
    "-03:00" porque Damian está en Argentina) sería inventar información que
    el dato no tiene, y podría estar directamente mal para un log de un
    servidor en otro país/proveedor cloud.

    Dos bugs reales encontrados por los tests, en cadena:
    1. dateutil por default asume MM/DD/AAAA (EE.UU.) para fechas
       ambiguas -- "12/08/2026" se leía como 8 de diciembre en vez de 12 de
       agosto. Para una herramienta forense pensada para Argentina (DD/MM/
       AAAA), mal-interpretar el día y el mes de una evidencia real no es
       cosmético.
    2. Pero pasarle `dayfirst=True` a TODO rompía fechas ISO 8601 sin
       ambigüedad real ("2026-08-12", año-mes-día clarísimo) -- dateutil
       igual reordenaba mes/día en el resto de la cadena. La fecha
       ISO 8601 estricta (con año de 4 dígitos primero) nunca es ambigua,
       así que se intenta parsear como tal PRIMERO (`datetime.fromisoformat`,
       sin heurística de ningún tipo) -- `dayfirst=True` con dateutil queda
       solo como fallback para formatos realmente ambiguos (DD/MM/AAAA vs.
       MM/DD/AAAA en texto libre)."""
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = dateutil_parser.parse(raw, dayfirst=True)
    if dt.tzinfo is not None:
        original_offset = dt.strftime("%z")
        dt_utc = dt.astimezone(timezone.utc)
    else:
        original_offset = None
        dt_utc = dt.replace(tzinfo=timezone.utc)
    return NormalizedTimestamp(utc=dt_utc.isoformat(), original_offset=original_offset, raw=raw)


def _parse_utc(iso_utc: str) -> datetime:
    dt = dateutil_parser.parse(iso_utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass(frozen=True)
class TimelineEntry:
    timestamp_utc: str
    kind: str  # "evento" | "transaccion" | "arista"
    entity_ids: tuple[str, ...]  # entidades involucradas -- lo que permite filtrar por nodo
    description: str
    source_id: str  # id del Node o Edge de origen, para trazabilidad real


def build_timeline(nodes: list[Node], edges: list[Edge]) -> list[TimelineEntry]:
    """Solo nodos/aristas VIGENTES -- algo retractado no debería aparecer en
    la línea de tiempo activa (sigue existiendo en el log para quien
    reconstruya el historial completo, ver case_store.rebuild_from_log)."""
    entries: list[TimelineEntry] = []
    for n in nodes:
        if n.retracted:
            continue
        if n.tipo == NodeType.EVENTO:
            entries.append(TimelineEntry(
                timestamp_utc=n.campos["timestamp_utc"], kind="evento",
                entity_ids=(n.id,), description=n.campos.get("descripcion") or "", source_id=n.id,
            ))
        elif n.tipo == NodeType.TRANSACCION:
            entries.append(TimelineEntry(
                timestamp_utc=n.campos["timestamp"], kind="transaccion",
                entity_ids=(n.id,), description=f"Transacción: {n.campos.get('tipo_transaccion') or ''}", source_id=n.id,
            ))

    for e in edges:
        if e.retracted:
            continue
        entries.append(TimelineEntry(
            timestamp_utc=e.timestamp, kind="arista",
            entity_ids=(e.origen, e.destino), description=e.tipo.value, source_id=e.id,
        ))

    entries.sort(key=lambda item: item.timestamp_utc)
    return entries


def timeline_for_entity(timeline: list[TimelineEntry], entity_id: str) -> list[TimelineEntry]:
    """Spec sección 4: "seleccionás un nodo y la timeline se filtra a los
    eventos donde participa"."""
    return [entry for entry in timeline if entity_id in entry.entity_ids]


@dataclass(frozen=True)
class Contradiction:
    entity_id: str
    edge_a_id: str
    edge_b_id: str
    timestamp_a: str
    timestamp_b: str
    delta_seconds: float
    reason: str


def detect_contradictions(
    nodes: list[Node], edges: list[Edge], window_seconds: float = _DEFAULT_CONTRADICTION_WINDOW_SECONDS,
) -> list[Contradiction]:
    """Contradicción real y concreta (spec: "dos eventos incompatibles para
    la misma entidad, marcados para revisión manual"): la MISMA entidad
    conectada a dos nodos Host DISTINTOS (sistemas/ubicaciones digitales
    distinguibles) con timestamps demasiado cerca entre sí -- el patrón
    forense clásico de "no puede estar en dos lugares a la vez". Solo mira
    aristas hacia Host -- una arista hacia un Archivo o una Cuenta no
    representa "estar en un lugar", así que no participa de esta detección.

    Esto NUNCA decide quién tiene razón ni resuelve la contradicción sola
    -- solo la señala. Resolverla (¿un error de ingesta? ¿dos dispositivos
    reales? ¿un desfasaje de reloj?) es trabajo humano."""
    host_ids = {n.id for n in nodes if n.tipo == NodeType.HOST and not n.retracted}

    by_entity: dict[str, list[Edge]] = {}
    for e in edges:
        if e.retracted or e.destino not in host_ids:
            continue
        by_entity.setdefault(e.origen, []).append(e)

    contradictions: list[Contradiction] = []
    for entity_id, entity_edges in by_entity.items():
        ordered = sorted(entity_edges, key=lambda e: e.timestamp)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                a, b = ordered[i], ordered[j]
                if a.destino == b.destino:
                    continue  # mismo host -- no hay nada incompatible
                delta = abs((_parse_utc(b.timestamp) - _parse_utc(a.timestamp)).total_seconds())
                if delta <= window_seconds:
                    contradictions.append(Contradiction(
                        entity_id=entity_id, edge_a_id=a.id, edge_b_id=b.id,
                        timestamp_a=a.timestamp, timestamp_b=b.timestamp, delta_seconds=delta,
                        reason=(
                            f"La misma entidad aparece conectada a dos Host distintos "
                            f"({a.destino} y {b.destino}) con solo {delta:.0f}s de diferencia -- "
                            "revisar manualmente (posible error de ingesta, desfasaje de reloj, "
                            "o dos entidades que en realidad no son la misma)."
                        ),
                    ))
    return contradictions
