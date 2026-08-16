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


def _severity_color(node):
    return "#ef4444" if node["id"] == "a" else None


def test_severity_color_fn_adds_halo_color_only_for_flagged_nodes(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label, severity_color_fn=_severity_color)

    data = _read_graph_data(qtbot, view)
    by_id = {n["id"]: n for n in data["nodes"]}
    assert by_id["a"]["severityColor"] == "#ef4444"
    assert "severityColor" not in by_id["b"]
    # el color de relleno por lenguaje sigue intacto -- el halo es una capa
    # aparte, no lo reemplaza.
    assert by_id["a"]["color"] == "#ff0000"


def _investigation_halo(node):
    if node["id"] != "a":
        return None
    return {"color": "#3b82f6", "radiusScale": 1.4, "opacity": 0.5}


def test_halo_fn_sends_both_severity_color_and_explicit_halo_style(qtbot):
    """El halo de investigación (centralidad+confianza, ver
    ui/investigation_colors.py) manda un estilo CONTINUO explícito, a
    diferencia del halo de severidad (3 colores fijos, estilo resuelto por
    lookup del lado de graph3d.html) -- graph_view.py tiene que mandar
    'haloStyle' además de 'severityColor' cuando viene de halo_fn."""
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label, halo_fn=_investigation_halo)

    data = _read_graph_data(qtbot, view)
    by_id = {n["id"]: n for n in data["nodes"]}
    assert by_id["a"]["severityColor"] == "#3b82f6"
    assert by_id["a"]["haloStyle"] == {"radiusScale": 1.4, "opacity": 0.5}
    assert "severityColor" not in by_id["b"]
    assert "haloStyle" not in by_id["b"]


def test_halo_fn_takes_precedence_over_severity_color_fn_if_both_given(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph(
        NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label,
        severity_color_fn=_severity_color, halo_fn=_investigation_halo,
    )

    data = _read_graph_data(qtbot, view)
    # halo_fn devuelve #3b82f6 para "a" -- gana sobre severity_color_fn
    # (#ef4444), que también aplicaba a "a".
    assert data and next(n for n in data["nodes"] if n["id"] == "a")["severityColor"] == "#3b82f6"


def test_no_severity_color_fn_means_no_severity_color_key(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)

    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)

    data = _read_graph_data(qtbot, view)
    assert all("severityColor" not in n for n in data["nodes"])


def test_update_severity_sets_severity_color_on_existing_node(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)
    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)
    _read_graph_data(qtbot, view)

    view.update_severity({"a": "#ef4444"})

    data = _read_graph_data(qtbot, view)
    by_id = {n["id"]: n for n in data["nodes"]}
    assert by_id["a"]["severityColor"] == "#ef4444"
    # el resto del grafo no se toca -- mismos nodos, mismos links, nada
    # "recreado" por este llamado.
    assert {n["id"] for n in data["nodes"]} == {"a", "b", "c"}
    assert len(data["links"]) == 1


def test_update_severity_removes_halo_color_when_resolved(qtbot):
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)
    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label, severity_color_fn=_severity_color)
    _read_graph_data(qtbot, view)  # confirma que "a" ya tiene severityColor

    view.update_severity({"a": None, "b": None, "c": None})

    data = _read_graph_data(qtbot, view)
    by_id = {n["id"]: n for n in data["nodes"]}
    assert not by_id["a"].get("severityColor")


def test_update_severity_before_ready_does_nothing(qtbot):
    """No tiene sentido encolar esto como `set_graph` -- si la página todavía
    no cargó, `set_graph` ya se va a encargar de la carga inicial completa
    apenas esté lista, con la data de severidad correcta desde el arranque."""
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)

    view.update_severity({"a": "#ef4444"})  # no debería tirar

    assert view._ready is False


def test_update_severity_does_not_reset_node_positions(qtbot):
    """Regresión del bug real reportado en vivo: llamar a `set_graph` de
    nuevo en cada refresco de polling reiniciaba el layout de fuerzas entero
    (el grafo "explotaba" reacomodándose). `update_severity` NO debe tocar
    `Graph.graphData()` -- se verifica que las posiciones x/y/z de los nodos
    quedan exactamente iguales antes y después de llamarlo, incluso para
    nodos cuya severidad SÍ cambió."""
    from ui.graph_view import GraphView

    view = GraphView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._ready is True, timeout=8000)
    view.set_graph(NODES, EDGES, id_key="id", color_fn=_color, label_fn=_label)
    _read_graph_data(qtbot, view)

    # Deja que la simulación de fuerzas se asiente antes de la primera foto.
    qtbot.wait(1500)
    before = _read_graph_data(qtbot, view)
    positions_before = {n["id"]: (n["x"], n["y"], n["z"]) for n in before["nodes"]}

    view.update_severity({"a": "#ef4444", "b": "#eab308"})
    qtbot.wait(500)  # un par de frames de animación

    after = _read_graph_data(qtbot, view)
    positions_after = {n["id"]: (n["x"], n["y"], n["z"]) for n in after["nodes"]}

    assert positions_after == positions_before


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
