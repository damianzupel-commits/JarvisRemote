"""Tests de app/investigation/graph_metrics.py -- centralidad de
intermediación real (networkx, sin mockear) sobre topologías de grafo
conocidas donde el resultado esperado es matemáticamente claro, y agregación
de confianza real desde nodos/aristas reales."""

from __future__ import annotations

from app.investigation import graph_metrics
from app.investigation.models import DerivadaPor, EdgeType, make_cuenta, make_edge, make_persona


def _edge(origen, destino, confianza=0.8):
    return make_edge(
        tipo=EdgeType.USA, origen=origen, destino=destino, artefacto_origen="manual",
        confianza=confianza, derivada_por=DerivadaPor.MANUAL,
    )


def test_centrality_is_zero_for_small_graphs_below_the_meaningful_threshold():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    edge = _edge(a.id, b.id)

    result = graph_metrics.compute_centrality([a, b], [edge])

    assert result == {a.id: 0.0, b.id: 0.0}


def test_centrality_identifies_the_real_bridge_node_in_a_path_graph():
    """Topología conocida: A-B-C (una línea). B es el ÚNICO camino entre A y
    C -- su betweenness tiene que ser mayor que la de A y C (que es 0, no
    son intermediarios de nada)."""
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    edges = [_edge(a.id, b.id), _edge(b.id, c.id)]

    result = graph_metrics.compute_centrality([a, b, c], edges)

    assert result[b.id] > result[a.id]
    assert result[b.id] > result[c.id]
    assert result[a.id] == 0.0
    assert result[c.id] == 0.0


def test_centrality_of_a_fully_connected_triangle_is_zero_for_everyone():
    """A-B-C-A (triángulo completo): nadie es 'intermediario' de nadie --
    cualquier par ya está conectado directo, betweenness real = 0 para los
    tres."""
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    edges = [_edge(a.id, b.id), _edge(b.id, c.id), _edge(a.id, c.id)]

    result = graph_metrics.compute_centrality([a, b, c], edges)

    assert result[a.id] == 0.0
    assert result[b.id] == 0.0
    assert result[c.id] == 0.0


def test_centrality_ignores_retracted_edges():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    bridge = _edge(b.id, c.id)
    bridge.retract("arista incorrecta")
    edges = [_edge(a.id, b.id), bridge]

    result = graph_metrics.compute_centrality([a, b, c], edges)

    # Sin la arista b-c vigente, b ya no conecta con c -- b no puede ser
    # intermediario de un camino que ya no existe.
    assert result[b.id] == 0.0


def test_centrality_ignores_retracted_nodes():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    b.retract("nodo incorrecto")
    edges = [_edge(a.id, b.id), _edge(b.id, c.id)]

    result = graph_metrics.compute_centrality([a, b, c], edges)

    assert b.id not in result


def test_confidence_for_persona_averages_own_field_and_incident_edges():
    persona = make_persona(etiqueta="a", confianza=0.9)
    cuenta = make_cuenta(plataforma="x", handle="@a")
    edge = _edge(persona.id, cuenta.id, confianza=0.5)

    result = graph_metrics.compute_confidence([persona, cuenta], [edge])

    assert result[persona.id] == (0.9 + 0.5) / 2


def test_confidence_for_a_node_type_without_its_own_field_uses_only_edges():
    """Cuenta no tiene campo 'confianza' propio (ver
    models.REQUIRED_NODE_FIELDS) -- su confianza de halo sale SOLO de las
    aristas incidentes."""
    persona = make_persona(etiqueta="a", confianza=0.9)
    cuenta = make_cuenta(plataforma="x", handle="@a")
    edge = _edge(persona.id, cuenta.id, confianza=0.6)

    result = graph_metrics.compute_confidence([persona, cuenta], [edge])

    assert result[cuenta.id] == 0.6


def test_confidence_averages_multiple_incident_edges():
    persona = make_persona(etiqueta="a", confianza=0.5)
    cuenta_x = make_cuenta(plataforma="x", handle="@a")
    cuenta_y = make_cuenta(plataforma="y", handle="@a")
    edges = [_edge(persona.id, cuenta_x.id, confianza=0.4), _edge(persona.id, cuenta_y.id, confianza=0.8)]

    result = graph_metrics.compute_confidence([persona, cuenta_x, cuenta_y], edges)

    assert result[persona.id] == (0.5 + 0.4 + 0.8) / 3


def test_confidence_is_none_for_an_isolated_node_without_edges_or_own_field():
    cuenta = make_cuenta(plataforma="x", handle="@aislada")

    result = graph_metrics.compute_confidence([cuenta], [])

    assert result[cuenta.id] is None


def test_detect_communities_separates_two_disconnected_clusters():
    """Topología garantizada: A-B conectados entre sí, C-D conectados entre
    sí, SIN ninguna arista entre los dos pares -- dos componentes
    desconectados NUNCA pueden terminar en la misma comunidad, sin importar
    heurística/semilla, así que este resultado es 100% predecible (a
    diferencia de casos más sutiles de modularidad, que dependerían de la
    implementación exacta)."""
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    d = make_persona(etiqueta="d", confianza=0.5)
    edges = [_edge(a.id, b.id), _edge(c.id, d.id)]

    result = graph_metrics.detect_communities([a, b, c, d], edges)

    assert result[a.id] == result[b.id]
    assert result[c.id] == result[d.id]
    assert result[a.id] != result[c.id]


def test_detect_communities_gives_an_isolated_node_its_own_community():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    aislado = make_persona(etiqueta="aislado", confianza=0.5)

    result = graph_metrics.detect_communities([a, b, aislado], [_edge(a.id, b.id)])

    assert result[aislado.id] != result[a.id]


def test_detect_communities_ignores_retracted_nodes_and_edges():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    b.retract("nodo incorrecto")

    result = graph_metrics.detect_communities([a, b], [_edge(a.id, b.id)])

    assert b.id not in result
    assert a.id in result


def test_detect_communities_returns_empty_dict_for_an_empty_graph():
    assert graph_metrics.detect_communities([], []) == {}


def test_detect_communities_is_deterministic_with_the_same_seed():
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    edges = [_edge(a.id, b.id), _edge(b.id, c.id)]

    first = graph_metrics.detect_communities([a, b, c], edges, seed=7)
    second = graph_metrics.detect_communities([a, b, c], edges, seed=7)

    assert first == second


def test_confidence_ignores_retracted_edges():
    persona = make_persona(etiqueta="a", confianza=0.5)
    cuenta = make_cuenta(plataforma="x", handle="@a")
    edge = _edge(persona.id, cuenta.id, confianza=0.9)
    edge.retract("arista incorrecta")

    result = graph_metrics.compute_confidence([persona, cuenta], [edge])

    # Sin la arista vigente, cuenta no tiene ninguna fuente real de confianza.
    assert result[cuenta.id] is None
    # persona todavia tiene su propio campo, asi que no queda en None.
    assert result[persona.id] == 0.5
