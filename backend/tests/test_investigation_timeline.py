"""Tests de app/investigation/timeline.py -- normalización real de
timestamps (dateutil, sin mockear), timeline cruzada filtrable, y detección
de contradicciones sobre topologías de grafo donde el resultado esperado es
claro."""

from __future__ import annotations

from app.investigation import timeline
from app.investigation.models import (
    DerivadaPor, EdgeType, make_cuenta, make_edge, make_evento, make_host, make_persona,
)


def test_normalize_timestamp_with_explicit_offset_converts_to_utc():
    result = timeline.normalize_timestamp("2026-08-12T14:30:00-03:00")

    assert result.utc == "2026-08-12T17:30:00+00:00"
    assert result.original_offset == "-0300"
    assert result.raw == "2026-08-12T14:30:00-03:00"


def test_normalize_timestamp_without_offset_assumes_utc_and_records_no_original_offset():
    result = timeline.normalize_timestamp("2026-08-12T14:30:00")

    assert result.utc == "2026-08-12T14:30:00+00:00"
    assert result.original_offset is None


def test_normalize_timestamp_handles_varied_real_world_formats():
    # Formatos que aparecen de verdad en exports/logs reales, no solo ISO 8601 estricto.
    a = timeline.normalize_timestamp("12-08-2026 14:30:00")
    b = timeline.normalize_timestamp("Aug 12 2026 14:30:00 GMT")
    assert a.utc.startswith("2026-08-12T14:30:00")
    assert b.utc.startswith("2026-08-12T14:30:00")


def test_normalize_timestamp_assumes_day_first_argentine_convention_not_us():
    """Bug real encontrado por este mismo test: dateutil por default asume
    MM/DD/AAAA (EE.UU.) -- '12/08/2026' se leía como 8 de diciembre en vez
    de 12 de agosto. Para una herramienta pensada para uso forense en
    Argentina, mal-interpretar el día y el mes de una evidencia real no es
    un detalle menor."""
    result = timeline.normalize_timestamp("12/08/2026 14:30:00")

    assert result.utc.startswith("2026-08-12T14:30:00")  # 12 de agosto, NO 8 de diciembre


def test_build_timeline_includes_evento_nodes():
    evento = make_evento(timestamp_utc="2026-08-12T10:00:00+00:00", descripcion="Login detectado", fuente="log")

    result = timeline.build_timeline([evento], [])

    assert len(result) == 1
    assert result[0].kind == "evento"
    assert result[0].entity_ids == (evento.id,)


def test_build_timeline_includes_edges():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_cuenta(plataforma="x", handle="@a")
    edge = make_edge(
        tipo=EdgeType.USA, origen=a.id, destino=b.id, artefacto_origen="manual",
        confianza=0.8, derivada_por=DerivadaPor.MANUAL, timestamp="2026-08-12T09:00:00+00:00",
    )

    result = timeline.build_timeline([a, b], [edge])

    assert len(result) == 1
    assert result[0].kind == "arista"
    assert set(result[0].entity_ids) == {a.id, b.id}


def test_build_timeline_is_sorted_chronologically():
    e1 = make_evento(timestamp_utc="2026-08-12T12:00:00+00:00", descripcion="segundo", fuente="x")
    e2 = make_evento(timestamp_utc="2026-08-12T08:00:00+00:00", descripcion="primero", fuente="x")

    result = timeline.build_timeline([e1, e2], [])

    assert [r.description for r in result] == ["primero", "segundo"]


def test_build_timeline_excludes_retracted_nodes_and_edges():
    evento = make_evento(timestamp_utc="2026-08-12T10:00:00+00:00", descripcion="x", fuente="x")
    evento.retract("error de ingesta")

    result = timeline.build_timeline([evento], [])

    assert result == []


def test_timeline_for_entity_filters_correctly():
    e1 = make_evento(timestamp_utc="2026-08-12T10:00:00+00:00", descripcion="a", fuente="x")
    a = make_persona(etiqueta="p", confianza=0.5)
    b = make_cuenta(plataforma="x", handle="@p")
    edge = make_edge(
        tipo=EdgeType.USA, origen=a.id, destino=b.id, artefacto_origen="manual",
        confianza=0.8, derivada_por=DerivadaPor.MANUAL, timestamp="2026-08-12T11:00:00+00:00",
    )
    full = timeline.build_timeline([e1, a, b], [edge])

    filtered = timeline.timeline_for_entity(full, a.id)

    assert len(filtered) == 1
    assert filtered[0].kind == "arista"


def test_detect_contradictions_finds_the_same_entity_at_two_hosts_close_in_time():
    persona = make_persona(etiqueta="p", confianza=0.5)
    host_a = make_host(ip_o_dominio="10.0.0.1")
    host_b = make_host(ip_o_dominio="10.0.0.2")
    edge_a = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_a.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00",
    )
    edge_b = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_b.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:02:00+00:00",  # 2 min despues
    )

    result = timeline.detect_contradictions([persona, host_a, host_b], [edge_a, edge_b])

    assert len(result) == 1
    assert result[0].entity_id == persona.id
    assert result[0].delta_seconds == 120.0


def test_detect_contradictions_ignores_the_same_host_visited_twice():
    persona = make_persona(etiqueta="p", confianza=0.5)
    host = make_host(ip_o_dominio="10.0.0.1")
    edge_a = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00",
    )
    edge_b = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:01:00+00:00",
    )

    result = timeline.detect_contradictions([persona, host], [edge_a, edge_b])

    assert result == []


def test_detect_contradictions_ignores_events_far_apart_in_time():
    persona = make_persona(etiqueta="p", confianza=0.5)
    host_a = make_host(ip_o_dominio="10.0.0.1")
    host_b = make_host(ip_o_dominio="10.0.0.2")
    edge_a = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_a.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00",
    )
    edge_b = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_b.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T18:00:00+00:00",  # 8hs despues
    )

    result = timeline.detect_contradictions([persona, host_a, host_b], [edge_a, edge_b])

    assert result == []


def test_detect_contradictions_ignores_edges_to_non_host_nodes():
    """Usar dos Cuentas distintas casi al mismo tiempo NO es una
    contradicción forense (no representa "estar en dos lugares") -- solo
    Host cuenta para esta detección."""
    persona = make_persona(etiqueta="p", confianza=0.5)
    cuenta_a = make_cuenta(plataforma="x", handle="@a")
    cuenta_b = make_cuenta(plataforma="y", handle="@b")
    edge_a = make_edge(
        tipo=EdgeType.USA, origen=persona.id, destino=cuenta_a.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00",
    )
    edge_b = make_edge(
        tipo=EdgeType.USA, origen=persona.id, destino=cuenta_b.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:30+00:00",
    )

    result = timeline.detect_contradictions([persona, cuenta_a, cuenta_b], [edge_a, edge_b])

    assert result == []


def test_detect_contradictions_respects_a_custom_window():
    persona = make_persona(etiqueta="p", confianza=0.5)
    host_a = make_host(ip_o_dominio="10.0.0.1")
    host_b = make_host(ip_o_dominio="10.0.0.2")
    edge_a = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_a.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00",
    )
    edge_b = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_b.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:04:00+00:00",  # 4 min
    )

    assert timeline.detect_contradictions([persona, host_a, host_b], [edge_a, edge_b], window_seconds=60) == []
    assert len(timeline.detect_contradictions([persona, host_a, host_b], [edge_a, edge_b], window_seconds=300)) == 1


def test_detect_contradictions_ignores_retracted_edges():
    persona = make_persona(etiqueta="p", confianza=0.5)
    host_a = make_host(ip_o_dominio="10.0.0.1")
    host_b = make_host(ip_o_dominio="10.0.0.2")
    edge_a = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_a.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00",
    )
    edge_b = make_edge(
        tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_b.id, artefacto_origen="manual",
        confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:01:00+00:00",
    )
    edge_b.retract("arista incorrecta")

    result = timeline.detect_contradictions([persona, host_a, host_b], [edge_a, edge_b])

    assert result == []
