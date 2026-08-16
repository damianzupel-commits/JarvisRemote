"""Métricas de grafo para el halo del visor 3D (spec sección 3: "cambiar la
semántica del halo: en vez de severidad, centralidad + confianza. Nodo con
alta centralidad de intermediación = candidato a pivote").

Centralidad: betweenness centrality real (networkx) sobre el grafo NO
dirigido de nodos/aristas VIGENTES (retractados excluidos) -- mide cuántos
caminos más cortos entre otros dos nodos pasan por este, que es justo "qué
tan intermediario/pivote" es una entidad. A propósito NO es degree
centrality (cuántas conexiones tiene) -- esa es una medida más simple que no
captura "está en el medio de dos grupos que si no, no se conectarían entre
sí", que es exactamente lo que la spec pide.

Confianza por nodo: de los 8 tipos de entidad, solo Persona tiene un campo
`confianza` propio (ver models.REQUIRED_NODE_FIELDS) -- Cuenta, Host,
Archivo, etc. no. Así que la confianza que alimenta el halo es el PROMEDIO
de la confianza de las aristas (TODAS las aristas tienen confianza
obligatoria, sin excepción) incidentes a ese nodo -- una Persona con aristas
Y campo propio promedia los dos; cualquier otro tipo, o un nodo sin ninguna
arista todavía, usa lo que haya disponible. Un nodo sin aristas Y sin campo
propio (recién creado, aislado) queda con confianza=None -- nunca se
inventa un valor por default, mismo principio que ya usa
colors.py::color_for_severity en Codebase (sin hallazgos != sin escanear,
acá sin aristas != confianza cero)."""

from __future__ import annotations

import networkx as nx

from .models import Edge, Node, NodeType

_MIN_NODES_FOR_MEANINGFUL_BETWEENNESS = 3


def build_graph(nodes: list[Node], edges: list[Edge]) -> nx.Graph:
    """Solo nodos/aristas VIGENTES -- un nodo o arista retractado no debería
    inflar ni la centralidad ni la confianza de nada a su alrededor."""
    g = nx.Graph()
    for n in nodes:
        if not n.retracted:
            g.add_node(n.id)
    for e in edges:
        if not e.retracted and e.origen in g and e.destino in g:
            g.add_edge(e.origen, e.destino)
    return g


def compute_centrality(nodes: list[Node], edges: list[Edge]) -> dict[str, float]:
    g = build_graph(nodes, edges)
    if g.number_of_nodes() < _MIN_NODES_FOR_MEANINGFUL_BETWEENNESS:
        # Betweenness no tiene un significado real con menos de 3 nodos (no
        # hay "entre quién" pasar) -- 0.0 explícito para todos en vez de
        # dejar que networkx devuelva un resultado degenerado sin avisar.
        return {n.id: 0.0 for n in nodes if not n.retracted}
    return nx.betweenness_centrality(g)


def compute_confidence(nodes: list[Node], edges: list[Edge]) -> dict[str, float | None]:
    incident: dict[str, list[float]] = {n.id: [] for n in nodes if not n.retracted}
    for e in edges:
        if e.retracted:
            continue
        if e.origen in incident:
            incident[e.origen].append(e.confianza)
        if e.destino in incident:
            incident[e.destino].append(e.confianza)

    result: dict[str, float | None] = {}
    for n in nodes:
        if n.retracted:
            continue
        values = list(incident[n.id])
        if n.tipo == NodeType.PERSONA:
            own = n.campos.get("confianza")
            if own is not None:
                values.append(own)
        result[n.id] = (sum(values) / len(values)) if values else None
    return result


def detect_communities(nodes: list[Node], edges: list[Edge], seed: int = 42) -> dict[str, int]:
    """Louvain (spec sección 3: "Agrupamiento por comunidad -- Louvain o
    label propagation -- para separar clusters"), paso 7 del orden de
    implementación. `networkx.algorithms.community.louvain_communities` ya
    viene con la librería (>=3.6 acá) -- no hace falta sumar una dependencia
    nueva solo para esto.

    Devuelve, por nodo, un ÍNDICE de comunidad (la posición del nodo dentro
    de la partición que devuelve Louvain) -- ese índice NO es estable entre
    corridas de un grafo que cambió (agregar un nodo puede reordenar la
    partición entera), así que no sirve como id persistente de nada, solo
    para agrupar visualmente "estos nodos están en el mismo cluster ahora".
    Louvain es no-determinístico por diseño (heurístico, depende del orden
    en que evalúa los nodos) salvo que se fije `seed` -- se fija acá para
    que la misma llamada sobre el mismo grafo dé siempre la misma partición
    (necesario para poder testear esto de verdad, no solo "corre sin
    tirar").

    Nodos aislados (sin ninguna arista vigente) terminan cada uno en su
    propia comunidad -- resultado correcto y esperado de Louvain, no un
    caso especial que haga falta manejar a mano."""
    g = build_graph(nodes, edges)
    if g.number_of_nodes() == 0:
        return {}
    communities = nx.community.louvain_communities(g, seed=seed)
    return {node_id: idx for idx, community in enumerate(communities) for node_id in community}
