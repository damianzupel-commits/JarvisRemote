"""Tests de la vista Investigación (ui/investigation_view.py). `requests` se
mockea a nivel de módulo -- InvestigationView dispara una carga de casos
apenas se construye, así que sin el mock cualquier test le pegaría al
backend real. `view.graph_view.set_graph` se reemplaza por un espía --el
renderizado real ya lo cubre test_graph_view.py, acá solo importa que le
pasen los datos/callbacks correctos."""

import requests

from ui.investigation_colors import color_for_node_type
from ui.investigation_view import _CONTRADICTION_BG, CasesFetchThread, InvestigationView


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


CASES = [{"id": "caso-1", "titulo": "Caso Uno", "created_at": "x"}, {"id": "caso-2", "titulo": "Caso Dos", "created_at": "x"}]
GRAPH = {
    "nodes": [
        {"id": "p1", "tipo": "Persona", "campos": {"etiqueta": "Juan"}, "centrality": 0.5, "confidence": 0.8},
        {"id": "c1", "tipo": "Cuenta", "campos": {"handle": "@juan"}, "centrality": 0.0, "confidence": None},
    ],
    "edges": [{"id": "e1", "tipo": "usa", "source": "p1", "target": "c1", "confianza": 0.9}],
}
TIMELINE = {
    "entries": [
        {"timestamp_utc": "2026-08-12T10:00:00+00:00", "kind": "arista", "entity_ids": ["p1", "c1"], "description": "usa", "source_id": "e1"},
    ],
    "contradictions": [],
}


def _patch_requests(monkeypatch, cases=None, graph=None, timeline=None):
    cases = CASES if cases is None else cases
    graph = GRAPH if graph is None else graph
    timeline = TIMELINE if timeline is None else timeline

    def fake_get(url, **kw):
        if "/timeline" in url:
            return _FakeResponse(timeline)
        if "/graph" in url:
            return _FakeResponse(graph)
        return _FakeResponse({"cases": cases})

    monkeypatch.setattr(requests, "get", fake_get)


class _GraphSpy:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, nodes, edges, id_key, color_fn, label_fn, severity_color_fn=None, halo_fn=None):
        self.calls.append(
            {"nodes": nodes, "edges": edges, "id_key": id_key, "color_fn": color_fn, "label_fn": label_fn, "halo_fn": halo_fn}
        )

    @property
    def last(self) -> dict:
        return self.calls[-1]


def _spy_on_graph(view: InvestigationView) -> _GraphSpy:
    spy = _GraphSpy()
    view.graph_view.set_graph = spy
    return spy


def test_view_loads_cases_on_construction(qtbot, monkeypatch):
    _patch_requests(monkeypatch)

    view = InvestigationView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.case_selector.count() == 2, timeout=3000)

    assert view.case_selector.itemText(0) == "Caso Uno"
    assert view.case_selector.itemData(0) == "caso-1"


def test_view_auto_loads_the_graph_of_the_first_case(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = InvestigationView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: view.case_selector.count() == 2, timeout=3000)

    qtbot.waitUntil(lambda: len(spy.calls) >= 1, timeout=3000)
    assert {n["id"] for n in spy.last["nodes"]} == {"p1", "c1"}


def test_view_shows_a_message_when_there_are_no_cases_yet(qtbot, monkeypatch):
    _patch_requests(monkeypatch, cases=[])

    view = InvestigationView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: "ningún caso" in view.status_label.text(), timeout=3000)


def test_selecting_a_different_case_loads_its_graph(qtbot, monkeypatch):
    other_graph = {"nodes": [{"id": "x", "tipo": "Host", "campos": {"ip_o_dominio": "1.2.3.4"}, "centrality": 0.0, "confidence": None}], "edges": []}
    call_count = {"n": 0}

    def fake_get(url, **kw):
        if "/graph" in url:
            call_count["n"] += 1
            return _FakeResponse(GRAPH if call_count["n"] == 1 else other_graph)
        return _FakeResponse({"cases": CASES})

    monkeypatch.setattr(requests, "get", fake_get)

    view = InvestigationView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: view.case_selector.count() == 2, timeout=3000)
    qtbot.waitUntil(lambda: len(spy.calls) >= 1, timeout=3000)

    view.case_selector.setCurrentIndex(1)

    qtbot.waitUntil(lambda: len(spy.calls) >= 2, timeout=3000)
    assert {n["id"] for n in spy.last["nodes"]} == {"x"}


def test_color_fn_uses_node_type_colors(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = InvestigationView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) >= 1, timeout=3000)

    color_fn = spy.last["color_fn"]
    assert color_fn({"tipo": "Persona"}) == color_for_node_type("Persona")


def test_label_fn_falls_back_across_known_field_names(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = InvestigationView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) >= 1, timeout=3000)

    label_fn = spy.last["label_fn"]
    assert label_fn({"id": "x", "campos": {"etiqueta": "Juan"}}) == "Juan"
    assert label_fn({"id": "x", "campos": {"handle": "@juan"}}) == "@juan"
    assert label_fn({"id": "fallback-id", "campos": {}}) == "fallback-id"


def test_halo_fn_reads_centrality_and_confidence_from_the_node(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = InvestigationView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) >= 1, timeout=3000)

    halo_fn = spy.last["halo_fn"]
    assert halo_fn({"centrality": 0.0, "confidence": None}) is None
    result = halo_fn({"centrality": 0.9, "confidence": 0.9})
    assert result is not None
    assert "color" in result


def test_timeline_loads_automatically_alongside_the_graph(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = InvestigationView()
    qtbot.addWidget(view)

    qtbot.waitUntil(lambda: view.timeline_list.count() >= 1, timeout=3000)
    assert "usa" in view.timeline_list.item(0).text()


def test_clicking_a_node_reloads_the_timeline_filtered_to_that_entity(qtbot, monkeypatch):
    filtered_timeline = {
        "entries": [{"timestamp_utc": "2026-08-12T11:00:00+00:00", "kind": "evento", "entity_ids": ["p1"], "description": "solo p1", "source_id": "ev1"}],
        "contradictions": [],
    }
    calls = {"entity_ids": []}

    def fake_get(url, **kw):
        if "/timeline" in url:
            entity_id = kw.get("params", {}).get("entity_id")
            calls["entity_ids"].append(entity_id)
            return _FakeResponse(filtered_timeline if entity_id else TIMELINE)
        if "/graph" in url:
            return _FakeResponse(GRAPH)
        return _FakeResponse({"cases": CASES})

    monkeypatch.setattr(requests, "get", fake_get)

    view = InvestigationView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.timeline_list.count() >= 1, timeout=3000)

    view.graph_view.node_clicked.emit("p1")

    qtbot.waitUntil(lambda: "p1" in calls["entity_ids"], timeout=3000)
    qtbot.waitUntil(lambda: view.timeline_list.count() == 1 and "solo p1" in view.timeline_list.item(0).text(), timeout=3000)


def test_contradictions_are_shown_first_with_a_warning_style(qtbot, monkeypatch):
    timeline_with_contradiction = {
        "entries": [{"timestamp_utc": "2026-08-12T10:00:00+00:00", "kind": "arista", "entity_ids": ["p1", "c1"], "description": "usa", "source_id": "e1"}],
        "contradictions": [{
            "entity_id": "p1", "edge_a_id": "e1", "edge_b_id": "e2",
            "timestamp_a": "2026-08-12T10:00:00+00:00", "timestamp_b": "2026-08-12T10:01:00+00:00",
            "delta_seconds": 60.0, "reason": "misma entidad en dos hosts distintos",
        }],
    }
    _patch_requests(monkeypatch, timeline=timeline_with_contradiction)

    view = InvestigationView()
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.timeline_list.count() >= 2, timeout=3000)

    first_item = view.timeline_list.item(0)
    assert "misma entidad en dos hosts distintos" in first_item.text()
    assert first_item.background().color() == _CONTRADICTION_BG


def test_cases_fetch_thread_retries_before_giving_up(qtbot, monkeypatch):
    attempts = {"n": 0}

    def flaky_get(url, **kw):
        attempts["n"] += 1
        raise requests.RequestException("backend todavía no levantó")

    monkeypatch.setattr(requests, "get", flaky_get)
    monkeypatch.setattr(CasesFetchThread, "_RETRY_DELAY_SECONDS", 0.01)
    monkeypatch.setattr(CasesFetchThread, "_MAX_ATTEMPTS", 3)

    from ui.investigation_view import InvestigationBridge

    bridge = InvestigationBridge()
    errors = []
    bridge.error.connect(errors.append)

    thread = CasesFetchThread(bridge, retry=True)
    thread.start()
    qtbot.waitUntil(lambda: len(errors) == 1, timeout=3000)

    assert attempts["n"] == 3
