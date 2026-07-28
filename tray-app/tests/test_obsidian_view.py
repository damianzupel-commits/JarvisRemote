"""Tests de la vista Obsidian (ui/obsidian_view.py). `requests` se mockea a
nivel de módulo -- ObsidianView dispara una carga del grafo apenas se
construye (refresh_notes() en __init__), así que sin el mock cualquier test
intentaría pegarle al backend real.

`view.graph_view.set_graph` se reemplaza por un espía en vez de dejar que
dibuje el grafo 3D de verdad (QWebEngineView real) -- esta vista solo tiene
que probar que le pasa los datos correctos (filtrados por autor, coloreados
por autor), el renderizado en sí ya lo cubre test_graph_view.py."""

import requests

from ui.colors import color_for_author
from ui.obsidian_view import GraphFetchThread, NoteEditorDialog, ObsidianView


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _patch_requests(monkeypatch, nodes=None, edges=None, get_note=None):
    nodes = nodes if nodes is not None else []
    edges = edges if edges is not None else []

    def fake_get(url, **kw):
        if "/notes/" in url:
            return _FakeResponse(get_note)
        return _FakeResponse({"nodes": nodes, "edges": edges})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", lambda url, **kw: _FakeResponse({}))
    monkeypatch.setattr(requests, "delete", lambda url, **kw: _FakeResponse({}))


class _GraphSpy:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, nodes, edges, id_key, color_fn, label_fn):
        self.calls.append({"nodes": nodes, "edges": edges, "id_key": id_key, "color_fn": color_fn, "label_fn": label_fn})

    @property
    def last(self) -> dict:
        return self.calls[-1]


def _spy_on_graph(view: ObsidianView) -> _GraphSpy:
    spy = _GraphSpy()
    view.graph_view.set_graph = spy
    return spy


def test_view_loads_notes_on_construction(qtbot, monkeypatch):
    _patch_requests(monkeypatch, nodes=[{"id": "jarvis/n1", "title": "N1", "author": "jarvis", "tags": [], "updated": "t"}])

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    assert [n["id"] for n in spy.last["nodes"]] == ["jarvis/n1"]
    assert spy.last["label_fn"](spy.last["nodes"][0]) == "N1"


def test_graph_color_fn_colors_by_author(qtbot, monkeypatch):
    _patch_requests(
        monkeypatch,
        nodes=[
            {"id": "jarvis/n1", "title": "De Jarvis", "author": "jarvis", "tags": [], "updated": "t"},
            {"id": "human/n2", "title": "De Damian", "author": "human", "tags": [], "updated": "t"},
        ],
    )

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    by_id = {n["id"]: n for n in spy.last["nodes"]}
    assert spy.last["color_fn"](by_id["jarvis/n1"]) == color_for_author("jarvis")
    assert spy.last["color_fn"](by_id["human/n2"]) == color_for_author("human")


def test_graph_passes_edges_for_linked_notes(qtbot, monkeypatch):
    edges = [{"source": "jarvis/a", "target": "human/b"}]
    _patch_requests(
        monkeypatch,
        nodes=[
            {"id": "jarvis/a", "title": "A", "author": "jarvis", "tags": [], "updated": "t"},
            {"id": "human/b", "title": "B", "author": "human", "tags": [], "updated": "t"},
        ],
        edges=edges,
    )

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    assert spy.last["edges"] == edges


def test_author_filter_hides_notes_from_the_other_author(qtbot, monkeypatch):
    _patch_requests(
        monkeypatch,
        nodes=[
            {"id": "jarvis/n1", "title": "De Jarvis", "author": "jarvis", "tags": [], "updated": "t"},
            {"id": "human/n2", "title": "De Damian", "author": "human", "tags": [], "updated": "t"},
        ],
    )

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    view.author_filter.setCurrentIndex(view.author_filter.findData("jarvis"))
    qtbot.waitUntil(lambda: len(spy.calls) == 2, timeout=2000)

    assert [n["id"] for n in spy.last["nodes"]] == ["jarvis/n1"]


def test_author_filter_drops_edges_to_notes_that_got_filtered_out(qtbot, monkeypatch):
    _patch_requests(
        monkeypatch,
        nodes=[
            {"id": "jarvis/a", "title": "A", "author": "jarvis", "tags": [], "updated": "t"},
            {"id": "human/b", "title": "B", "author": "human", "tags": [], "updated": "t"},
        ],
        edges=[{"source": "jarvis/a", "target": "human/b"}],
    )

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    view.author_filter.setCurrentIndex(view.author_filter.findData("jarvis"))
    qtbot.waitUntil(lambda: len(spy.calls) == 2, timeout=2000)

    assert spy.last["edges"] == []


def test_clicking_a_node_fetches_and_shows_the_note(qtbot, monkeypatch):
    _patch_requests(
        monkeypatch,
        get_note={"id": "jarvis/n1", "title": "N1", "author": "jarvis", "tags": [], "content": "contenido"},
    )

    view = ObsidianView()
    qtbot.addWidget(view)

    view._on_node_clicked("jarvis/n1")

    qtbot.waitUntil(lambda: view.detail_title.text() == "N1", timeout=2000)
    assert view.detail_content.toPlainText() == "contenido"


def test_initial_load_retries_until_the_backend_answers(qtbot, monkeypatch):
    """Mismo bug real que tenía CodebaseView (ver RecentProjectsThread):
    `tray.py` arranca la ventana y el subproceso del backend en paralelo, así
    que la carga inicial de notas puede pegarle a un backend que todavía no
    levantó el puerto."""
    monkeypatch.setattr(GraphFetchThread, "_RETRY_DELAY_SECONDS", 0.01)

    calls = {"n": 0}

    def fake_get(url, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ConnectionError("backend todavía no levantó el puerto")
        return _FakeResponse({"nodes": [{"id": "jarvis/n1", "title": "N1", "author": "jarvis"}], "edges": []})

    monkeypatch.setattr(requests, "get", fake_get)

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)

    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=3000)
    assert calls["n"] == 3


def test_user_triggered_refresh_does_not_retry(qtbot, monkeypatch):
    """A diferencia de la carga inicial, un refresh disparado por el usuario
    (acá, el filtro de autor) no reintenta -- si el backend ya respondió una
    vez en esta sesión, un fallo puntual no es la carrera de arranque."""
    _patch_requests(monkeypatch, nodes=[{"id": "jarvis/n1", "title": "N1", "author": "jarvis", "tags": [], "updated": "t"}])

    view = ObsidianView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    monkeypatch.setattr(requests, "get", lambda url, **kw: (_ for _ in ()).throw(requests.ConnectionError("caído")))
    view.author_filter.setCurrentIndex(view.author_filter.findData("jarvis"))

    qtbot.waitUntil(lambda: view.status_label.text() == "No pude cargar las notas: caído", timeout=2000)


def test_on_note_ready_shows_detail_and_enables_edit_only_for_human(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = ObsidianView()
    qtbot.addWidget(view)

    view._on_note_ready({"id": "jarvis/n1", "title": "De Jarvis", "author": "jarvis", "tags": ["a"], "content": "texto"})
    assert view.detail_title.text() == "De Jarvis"
    assert not view.edit_button.isEnabled()
    assert not view.delete_button.isEnabled()

    view._on_note_ready({"id": "human/n2", "title": "De Damian", "author": "human", "tags": [], "content": "texto2"})
    assert view.edit_button.isEnabled()
    assert view.delete_button.isEnabled()


def test_on_deleted_clears_detail_panel(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = ObsidianView()
    qtbot.addWidget(view)
    view._on_note_ready({"id": "human/n2", "title": "De Damian", "author": "human", "tags": [], "content": "texto2"})

    view._on_deleted()

    assert view.detail_title.text() == ""
    assert not view.edit_button.isEnabled()
    assert not view.delete_button.isEnabled()


def test_on_error_sets_status_label(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = ObsidianView()
    qtbot.addWidget(view)

    view._on_error("no pude conectarme")

    assert view.status_label.text() == "no pude conectarme"


def test_author_filter_has_three_options(qtbot, monkeypatch):
    _patch_requests(monkeypatch)
    view = ObsidianView()
    qtbot.addWidget(view)

    labels = [view.author_filter.itemText(i) for i in range(view.author_filter.count())]
    assert labels == ["Todos", "Jarvis", "Humano"]


def test_note_editor_dialog_prefills_from_existing_note(qtbot):
    note = {"id": "human/n1", "title": "Título", "content": "contenido", "tags": ["a", "b"]}
    dialog = NoteEditorDialog(note=note)
    qtbot.addWidget(dialog)

    assert dialog.title_input.text() == "Título"
    assert dialog.content_input.toPlainText() == "contenido"
    assert dialog.data() == {"title": "Título", "content": "contenido", "tags": ["a", "b"], "note_id": "human/n1"}


def test_note_editor_dialog_blank_for_new_note(qtbot):
    dialog = NoteEditorDialog()
    qtbot.addWidget(dialog)

    assert dialog.note_id is None
    assert dialog.data()["title"] == ""
