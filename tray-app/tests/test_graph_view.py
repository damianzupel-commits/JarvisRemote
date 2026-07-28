"""Tests de la vista de grafo 3D reutilizable (ui/graph_view.py). A
diferencia de las otras vistas, esto carga una página real (QWebEngineView +
3d-force-graph vendorizado) -- no hay forma honesta de mockear eso sin perder
la cobertura real, así que los tests dejan que la página cargue de verdad y
verifican los datos ida y vuelta vía `runJavaScript` (JS -> Python) además del
wiring del lado Python (`node_clicked`). Cada test espera a `loadFinished`
antes de asertar nada -- la carga es asincrónica."""

import json

NODES = [
    {"id": "a", "language": "Python"},
    {"id": "b", "language": "Python"},
    {"id": "c", "language": "JavaScript"},
]
EDGES = [{"source": "a", "target": "b"}]


def _color(node):
    return "#ff0000" if node["language"] == "Python" else "#00ff00"


def _label(node):
    return node["id"]


def _read_graph_data(qtbot, view):
    result = {}

    def on_result(raw):
        result["value"] = json.loads(raw)

    view.web.page().runJavaScript("JSON.stringify(Graph.graphData())", on_result)
    qtbot.waitUntil(lambda: "value" in result, timeout=5000)
    return result["value"]


def test_set_graph_before_load_is_queued_and_applied_once_ready(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)

    # Llamado antes de que la página termine de cargar -- no debería tirar,
    # y tiene que aplicarse solo apenas esté lista.
    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)
    assert view._ready is False

    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)
    data = _read_graph_data(qtbot, view)

    assert {n["id"] for n in data["nodes"]} == {"a", "b", "c"}
    assert len(data["links"]) == 1


def test_set_graph_after_ready_pushes_immediately(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)

    data = _read_graph_data(qtbot, view)
    assert {n["id"] for n in data["nodes"]} == {"a", "b", "c"}


def test_node_color_and_label_are_forwarded_to_the_page(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)
    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)

    data = _read_graph_data(qtbot, view)
    by_id = {n["id"]: n for n in data["nodes"]}

    assert by_id["a"]["color"] == "#ff0000"
    assert by_id["c"]["color"] == "#00ff00"
    assert by_id["a"]["label"] == "a"


def test_links_reference_source_and_target_ids(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)
    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)

    data = _read_graph_data(qtbot, view)
    link = data["links"][0]
    # three-force-graph reescribe source/target de string a objeto de nodo
    # una vez que arma el grafo -- de ahí que se compare el id del objeto.
    source_id = link["source"]["id"] if isinstance(link["source"], dict) else link["source"]
    target_id = link["target"]["id"] if isinstance(link["target"], dict) else link["target"]
    assert {source_id, target_id} == {"a", "b"}


def test_empty_graph_does_not_crash(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph([], [], id_key="id", color_fn=_color, label_fn=_label)

    data = _read_graph_data(qtbot, view)
    assert data["nodes"] == []
    assert data["links"] == []


def test_bridge_node_click_emits_node_clicked_signal(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)

    with qtbot.waitSignal(view.node_clicked, timeout=2000) as blocker:
        view._bridge.onNodeClick("b")

    assert blocker.args == ["b"]


def test_second_set_graph_call_replaces_the_first(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)
    _read_graph_data(qtbot, view)  # espera a que el primer push se procese

    other_nodes = [{"id": "x", "language": "Python"}]
    view.set_graph(other_nodes, [], id_key="id", color_fn=_color, label_fn=_label)

    data = _read_graph_data(qtbot, view)
    assert {n["id"] for n in data["nodes"]} == {"x"}
