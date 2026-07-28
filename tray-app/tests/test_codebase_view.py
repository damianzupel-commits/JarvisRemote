"""Tests de la vista Codebase (ui/codebase_view.py). Los métodos que llaman
al backend (`_start_index`) se prueban invocando directamente los handlers de
resultado (`_on_index_ready`/`_on_graph_ready`/`_on_index_error`) en vez de
arrancar el hilo de red de verdad -- misma filosofía que test_main_window.py:
probar el wiring de la UI, no la red.

`view.graph_view.set_graph` se reemplaza por un espía en vez de dejar que
dibuje el grafo 3D de verdad (QWebEngineView real) -- esta vista solo tiene
que probar que le pasa los datos correctos, el renderizado en sí ya lo cubre
test_graph_view.py.

`requests` se mockea a nivel de módulo -- CodebaseView dispara una carga de
"proyecto reciente" apenas se construye, así que sin el mock cualquier test
intentaría pegarle al backend real (mismo motivo que test_obsidian_view.py)."""

import requests

import config
from ui.codebase_view import CodebaseView, RecentProjectsThread
from ui.colors import color_for_language


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _patch_recent(monkeypatch, projects=None):
    # Cualquier llamada de red real que dispare la vista sin querer (ej. el
    # GraphFetchThread/FileContentFetchThread reales que arrancan
    # _on_index_ready/_on_node_clicked) tiene que devolver algo inofensivo
    # sin importar a qué URL le pegó -- de ahí que la respuesta traiga todas
    # las claves posibles de los distintos endpoints.
    projects = projects if projects is not None else []
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, **kw: _FakeResponse({"projects": projects, "edges": [], "nodes": [], "content": "", "language": None, "path": ""}),
    )


class _GraphSpy:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, nodes, edges, id_key, color_fn, label_fn):
        self.calls.append({"nodes": nodes, "edges": edges, "id_key": id_key, "color_fn": color_fn, "label_fn": label_fn})

    @property
    def last(self) -> dict:
        return self.calls[-1]


def _spy_on_graph(view: CodebaseView) -> _GraphSpy:
    spy = _GraphSpy()
    view.graph_view.set_graph = spy
    return spy


SAMPLE_INDEX = {
    "root": "/tmp/proyecto",
    "indexed_at": "2026-07-27T00:00:00+00:00",
    "file_count": 2,
    "primary_language": "Python",
    "languages": [
        {"language": "Python", "file_count": 1, "line_count": 8},
        {"language": "JavaScript", "file_count": 1, "line_count": 4},
    ],
    "files": [
        {
            "path": "src/main.py",
            "language": "Python",
            "size_bytes": 100,
            "line_count": 8,
            "parsed": True,
            "symbols": [
                {"kind": "class", "name": "Greeter", "line": 3},
                {"kind": "function", "name": "greet", "line": 4},
            ],
        },
        {
            "path": "src/util.js",
            "language": "JavaScript",
            "size_bytes": 50,
            "line_count": 4,
            "parsed": True,
            "symbols": [{"kind": "function", "name": "helper", "line": 1}],
        },
    ],
}

SAMPLE_EDGES = [{"source": "src/main.py", "target": "src/util.js"}]


def test_view_starts_empty(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)

    assert view.status_label.text() == ""


def test_on_index_ready_populates_status_and_language_bar(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)

    view._on_index_ready(SAMPLE_INDEX)

    assert "2 archivos" in view.status_label.text()
    assert "Python" in view.status_label.text()
    assert view.language_bar._layout.count() > 0


def test_on_graph_ready_passes_one_node_per_file(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready({"edges": SAMPLE_EDGES})

    assert {f["path"] for f in spy.last["nodes"]} == {"src/main.py", "src/util.js"}
    assert spy.last["id_key"] == "path"
    assert "2 archivos" in view.status_label.text()


def test_on_graph_ready_passes_the_resolved_edges(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready({"edges": SAMPLE_EDGES})

    assert spy.last["edges"] == SAMPLE_EDGES


def test_graph_color_fn_colors_by_language(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_graph_ready({"edges": SAMPLE_EDGES})

    py_file = next(f for f in spy.last["nodes"] if f["path"] == "src/main.py")
    assert spy.last["color_fn"](py_file) == color_for_language("Python")


def test_graph_label_fn_uses_just_the_filename(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_graph_ready({"edges": SAMPLE_EDGES})

    py_file = next(f for f in spy.last["nodes"] if f["path"] == "src/main.py")
    assert spy.last["label_fn"](py_file) == "main.py"


def test_clicking_a_node_populates_symbol_list(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("src/main.py")

    texts = [view.symbol_list.item(i).text() for i in range(view.symbol_list.count())]
    assert any("Greeter" in t for t in texts)
    assert any("greet" in t for t in texts)


def test_clicking_an_unknown_node_clears_symbol_list_without_error(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("no/existe.py")

    assert view.symbol_list.count() == 0


def test_clicking_a_node_requests_and_shows_its_file_content(qtbot, monkeypatch):
    def fake_get(url, **kw):
        if url == config.CODEBASE_FILE_URL:
            assert kw["params"] == {"path": "/tmp/proyecto", "file": "src/main.py"}
            return _FakeResponse({"path": "src/main.py", "content": "class Greeter:\n    pass\n", "language": "Python"})
        return _FakeResponse({"projects": [], "edges": [], "nodes": []})

    monkeypatch.setattr(requests, "get", fake_get)

    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("src/main.py")

    qtbot.waitUntil(lambda: view.code_viewer.toPlainText() == "class Greeter:\n    pass\n", timeout=2000)


def test_clicking_a_node_shows_an_error_if_the_file_fetch_fails(qtbot, monkeypatch):
    def fake_get(url, **kw):
        if url == config.CODEBASE_FILE_URL:
            raise requests.ConnectionError("caído")
        return _FakeResponse({"projects": [], "edges": [], "nodes": []})

    monkeypatch.setattr(requests, "get", fake_get)

    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("src/main.py")

    qtbot.waitUntil(lambda: "No pude leer" in view.code_viewer.toPlainText(), timeout=2000)


def test_clicking_an_unknown_node_does_not_fetch_file_content(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("no/existe.py")

    assert view.code_viewer.toPlainText() == ""
    assert view._file_thread is None


def test_on_index_error_shows_message_and_reenables_buttons(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view.index_button.setEnabled(False)
    view.reindex_button.setEnabled(False)

    view._on_index_error("no pude conectarme")

    assert view.status_label.text() == "no pude conectarme"
    assert view.index_button.isEnabled()
    assert view.reindex_button.isEnabled()


def test_browse_button_fills_path_input(qtbot, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    _patch_recent(monkeypatch)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/mi-proyecto"))

    view = CodebaseView()
    qtbot.addWidget(view)

    view._on_browse_clicked()

    assert view.path_input.text() == "/tmp/mi-proyecto"


def test_recent_project_autoloads_path_and_starts_indexing(qtbot, monkeypatch):
    """Al abrir la pestaña sin tocar nada, si el backend ya tiene un proyecto
    indexado en cache, se precarga solo -- así la pestaña no arranca vacía
    para quien la abre después de que alguien ya indexó algo."""

    def fake_get(url, **kw):
        if url == config.CODEBASE_RECENT_URL:
            return _FakeResponse(
                {"projects": [{"root": "/tmp/proyecto", "indexed_at": "t", "file_count": 2, "primary_language": "Python"}]}
            )
        if url == config.CODEBASE_INDEX_URL:
            return _FakeResponse(SAMPLE_INDEX)
        if url == config.CODEBASE_GRAPH_URL:
            return _FakeResponse({"nodes": [], "edges": SAMPLE_EDGES})
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    qtbot.waitUntil(lambda: view.path_input.text() == "/tmp/proyecto", timeout=2000)
    qtbot.waitUntil(lambda: len(spy.calls) == 1, timeout=2000)

    assert len(spy.last["nodes"]) == 2
    assert "2 archivos" in view.status_label.text()


def test_recent_projects_thread_retries_until_the_backend_answers(qtbot, monkeypatch):
    """`tray.py` arranca la ventana y el backend en paralelo -- el primer
    intento del thread puede pegarle a un backend que todavía no levantó el
    puerto. Sin reintento la pestaña queda vacía (bug real, visto en vivo:
    la primera vez que se restarteó la app con esto anduvo, la segunda
    quedó en blanco porque el fetch ganó la carrera contra el arranque del
    backend)."""
    monkeypatch.setattr(RecentProjectsThread, "_RETRY_DELAY_SECONDS", 0.01)

    calls = {"n": 0}

    def fake_get(url, **kw):
        if url == config.CODEBASE_RECENT_URL:
            calls["n"] += 1
            if calls["n"] < 3:
                raise requests.ConnectionError("backend todavía no levantó el puerto")
            return _FakeResponse({"projects": [{"root": "/tmp/proyecto"}]})
        if url == config.CODEBASE_INDEX_URL:
            return _FakeResponse(SAMPLE_INDEX)
        if url == config.CODEBASE_GRAPH_URL:
            return _FakeResponse({"nodes": [], "edges": []})
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    view = CodebaseView()
    qtbot.addWidget(view)

    qtbot.waitUntil(lambda: view.path_input.text() == "/tmp/proyecto", timeout=3000)
    assert calls["n"] == 3


def test_recent_projects_thread_gives_up_silently_after_max_attempts(qtbot, monkeypatch):
    monkeypatch.setattr(RecentProjectsThread, "_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(RecentProjectsThread, "_RETRY_DELAY_SECONDS", 0.01)

    def fake_get(url, **kw):
        raise requests.ConnectionError("el backend nunca levanta en este test")

    monkeypatch.setattr(requests, "get", fake_get)

    view = CodebaseView()
    qtbot.addWidget(view)
    qtbot.wait(200)  # deja correr los 2 intentos (2 x 0.01s) sin que explote nada

    assert view.path_input.text() == ""
    assert view.status_label.text() == ""


def test_recent_project_does_not_override_typed_path(qtbot, monkeypatch):
    """Si el usuario ya escribió algo antes de que la respuesta de /recent
    vuelva, no le pisamos lo que tenía tipeado."""
    import time

    def fake_get(url, **kw):
        time.sleep(0.1)
        return _FakeResponse({"projects": [{"root": "/tmp/otro-proyecto"}]})

    monkeypatch.setattr(requests, "get", fake_get)

    view = CodebaseView()
    qtbot.addWidget(view)
    view.path_input.setText("/tmp/lo-que-tipeo-el-usuario")
    qtbot.wait(300)

    assert view.path_input.text() == "/tmp/lo-que-tipeo-el-usuario"
