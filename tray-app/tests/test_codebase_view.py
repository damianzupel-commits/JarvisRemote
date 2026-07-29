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

    def __call__(self, nodes, edges, id_key, color_fn, label_fn, severity_color_fn=None):
        self.calls.append(
            {
                "nodes": nodes,
                "edges": edges,
                "id_key": id_key,
                "color_fn": color_fn,
                "label_fn": label_fn,
                "severity_color_fn": severity_color_fn,
            }
        )

    @property
    def last(self) -> dict:
        return self.calls[-1]


def _spy_on_graph(view: CodebaseView) -> _GraphSpy:
    spy = _GraphSpy()
    view.graph_view.set_graph = spy
    return spy


class _UpdateSeveritySpy:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, severity_by_id):
        self.calls.append(severity_by_id)

    @property
    def last(self) -> dict:
        return self.calls[-1]


def _spy_on_update_severity(view: CodebaseView) -> _UpdateSeveritySpy:
    spy = _UpdateSeveritySpy()
    view.graph_view.update_severity = spy
    return spy


class _NoOpThread:
    """Reemplazo de los QThread reales (`GraphFetchThread`/
    `FileContentFetchThread`) para tests que disparan varios ciclos de
    índice/click y simulan la respuesta llamando a los handlers directo --
    sin esto, cada ciclo deja un QThread real corriendo de fondo (con
    `requests.get` mockeado igual, pero real en tanto QThread), y con más de
    uno vivo a la vez la señal que entrega al terminar puede llegarle a la
    vista ya en medio del teardown del test, colgando la suite (bug real
    reproducido armando estos mismos tests)."""

    def __init__(self, *a, **k):
        pass

    def start(self):
        pass

    def isRunning(self):
        return False


def _disable_real_threads(monkeypatch) -> None:
    import ui.codebase_view as codebase_view_module

    monkeypatch.setattr(codebase_view_module, "GraphFetchThread", _NoOpThread)
    monkeypatch.setattr(codebase_view_module, "FileContentFetchThread", _NoOpThread)


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


def test_graph_severity_color_fn_looks_up_severity_by_path(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)

    graph = {
        "edges": SAMPLE_EDGES,
        "nodes": [
            {"path": "src/main.py", "language": "Python", "severity": "critical", "finding_count": 1},
            {"path": "src/util.js", "language": "JavaScript", "severity": None, "finding_count": 0},
        ],
        "security_scanned": True,
        "security_scanned_at": "2026-07-29T00:00:00+00:00",
        "quality_scanned": False,
        "quality_scanned_at": None,
    }
    view._on_graph_ready(graph)

    py_file = next(f for f in spy.last["nodes"] if f["path"] == "src/main.py")
    js_file = next(f for f in spy.last["nodes"] if f["path"] == "src/util.js")
    assert spy.last["severity_color_fn"](py_file) == "#ef4444"
    assert spy.last["severity_color_fn"](js_file) is None


def test_graph_severity_color_fn_is_none_for_files_missing_from_graph_nodes(qtbot, monkeypatch):
    # `graph["nodes"]` puede no traer entrada para un path (ej. respuesta
    # vieja mockeada) -- no debería reventar, solo no pintar halo.
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})

    py_file = next(f for f in spy.last["nodes"] if f["path"] == "src/main.py")
    assert spy.last["severity_color_fn"](py_file) is None


def test_first_graph_ready_does_a_full_reload(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    graph_spy = _spy_on_graph(view)
    severity_spy = _spy_on_update_severity(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})

    assert len(graph_spy.calls) == 1
    assert severity_spy.calls == []


def test_second_graph_ready_only_updates_severity_in_place(qtbot, monkeypatch):
    """Regresión del bug real reportado en vivo: un segundo refresco de
    grafo sobre el MISMO índice (típico del polling, ver _on_poll_tick) no
    debe volver a llamar a `set_graph` -- eso reiniciaba el layout de fuerzas
    entero y el grafo "explotaba" reacomodándose cada pocos segundos."""
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    graph_spy = _spy_on_graph(view)
    severity_spy = _spy_on_update_severity(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})  # carga inicial
    view._on_graph_ready(  # refresco posterior (mismo índice)
        {
            "edges": SAMPLE_EDGES,
            "nodes": [{"path": "src/main.py", "language": "Python", "severity": "critical", "finding_count": 1}],
        }
    )

    assert len(graph_spy.calls) == 1  # set_graph NO se llamó de nuevo
    assert len(severity_spy.calls) == 1
    assert severity_spy.last == {"src/main.py": "#ef4444"}


def test_reindexing_forces_a_full_reload_again(qtbot, monkeypatch):
    """Un reindexado real (el usuario tocó "Reindexar") sí puede cambiar la
    topología del grafo (archivos agregados/borrados) -- tiene que volver a
    ser una carga completa, no una actualización in-place."""
    _patch_recent(monkeypatch)
    _disable_real_threads(monkeypatch)  # este test dispara _on_index_ready dos veces

    view = CodebaseView()
    qtbot.addWidget(view)
    graph_spy = _spy_on_graph(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})  # carga inicial
    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})  # refresco in-place (no cuenta)

    view._on_index_ready(SAMPLE_INDEX)  # reindexado
    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})

    assert len(graph_spy.calls) == 2


def test_risk_legend_shows_not_scanned_when_no_scan_ran(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready({"edges": SAMPLE_EDGES, "nodes": []})

    assert "sin escanear" in view.risk_legend._status_label.text()


def test_risk_legend_shows_scan_timestamps_when_scanned(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_graph_ready(
        {
            "edges": SAMPLE_EDGES,
            "nodes": [],
            "security_scanned": True,
            "security_scanned_at": "2026-07-29T00:00:00+00:00",
            "quality_scanned": False,
            "quality_scanned_at": None,
        }
    )

    text = view.risk_legend._status_label.text()
    assert "sin escanear" not in text
    assert "seguridad" in text


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


# --------------------------------------------------------- panel de hallazgos

_FINDINGS_SAMPLE = [
    {"id": "f-crit", "tool": "bandit", "file": "src/main.py", "line": 10, "end_line": 10, "severity": "critical", "rule_id": "B608", "message": "sqli"},
    {"id": "f-low", "tool": "ruff", "file": "src/main.py", "line": 3, "end_line": 3, "severity": "low", "rule_id": "F401", "message": "unused import"},
]


def test_on_file_ready_renders_findings_list(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_file_ready({"content": "code", "findings": _FINDINGS_SAMPLE})

    assert view.findings_list.count() == 2
    assert "B608" in view.findings_list.item(0).text()
    assert "F401" in view.findings_list.item(1).text()


def test_on_file_ready_with_no_findings_leaves_list_empty(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_file_ready({"content": "code", "findings": []})

    assert view.findings_list.count() == 0


def test_selecting_a_new_node_does_not_show_cascade_toast(qtbot, monkeypatch):
    """Cambiar de archivo no es "arreglar algo" -- no hay base todavía para
    comparar, así que no debe aparecer el toast solo por navegar."""
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("src/main.py")
    view._on_file_ready({"content": "code", "findings": _FINDINGS_SAMPLE})

    # `isVisible()` depende de que toda la cadena de ancestros esté shown()
    # (la ventana de test nunca se muestra de verdad) -- `isHidden()` refleja
    # el último show()/hide() explícito de ESTE widget, que es lo que importa acá.
    assert view.cascade_toast.isHidden() is True


def test_finding_resolved_between_polls_shows_cascade_toast(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    # Primera lectura: los dos hallazgos están presentes (fija la base).
    view._on_node_clicked("src/main.py")
    view._on_file_ready({"content": "code", "findings": _FINDINGS_SAMPLE})
    assert view.cascade_toast.isHidden() is True

    # Un poll posterior (mismo archivo seleccionado) ya no trae el crítico --
    # se resolvió, típico tras aplicar un fix.
    view._on_file_ready({"content": "code", "findings": [_FINDINGS_SAMPLE[1]]})

    assert view.cascade_toast.isHidden() is False
    assert "1 hallazgo" in view.cascade_toast.text()
    assert "crítico" in view.cascade_toast.text()


def test_cascade_toast_summarizes_multiple_resolved_severities(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_node_clicked("src/main.py")
    view._on_file_ready({"content": "code", "findings": _FINDINGS_SAMPLE})
    view._on_file_ready({"content": "code", "findings": []})

    text = view.cascade_toast.text()
    assert "2 hallazgo" in text
    assert "crítico" in text
    assert "bajo" in text


def test_double_clicking_a_finding_moves_cursor_to_its_line(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_node_clicked("src/main.py")
    view._on_file_ready({"content": "\n".join(f"line{i}" for i in range(1, 21)), "findings": _FINDINGS_SAMPLE})

    view._on_finding_double_clicked(view.findings_list.item(0))  # línea 10

    assert view.code_viewer.textCursor().block().text() == "line10"


def test_findings_highlight_their_lines_in_the_code_viewer(qtbot, monkeypatch):
    """Bug real reportado en vivo: el doble click saltaba a la línea pero no
    la marcaba de ninguna forma -- el código se veía plano. Ahora cada línea
    con hallazgo (severidad alta/crítica/media, mismo criterio que el halo
    del grafo) tiene un fondo de color en el visor, sin necesidad de volver a
    mirar la lista de arriba."""
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_node_clicked("src/main.py")

    view._on_file_ready({"content": "\n".join(f"line{i}" for i in range(1, 21)), "findings": _FINDINGS_SAMPLE})

    selections = view.code_viewer.extraSelections()
    # Solo el crítico (línea 10) se resalta -- "low" no lleva halo/marca,
    # mismo criterio que color_for_severity ya usa para el grafo 3D.
    highlighted_lines = {sel.cursor.blockNumber() + 1 for sel in selections}
    assert highlighted_lines == {10}


def test_findings_highlight_updates_when_findings_change(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_node_clicked("src/main.py")
    content = "\n".join(f"line{i}" for i in range(1, 21))
    view._on_file_ready({"content": content, "findings": _FINDINGS_SAMPLE})
    assert len(view.code_viewer.extraSelections()) == 1

    # El hallazgo crítico se resolvió -- el resaltado tiene que desaparecer.
    view._on_file_ready({"content": content, "findings": []})

    assert view.code_viewer.extraSelections() == []


def test_selecting_a_new_node_clears_previous_highlights(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    _disable_real_threads(monkeypatch)  # este test clickea dos nodos distintos

    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_node_clicked("src/main.py")
    view._on_file_ready({"content": "\n".join(f"line{i}" for i in range(1, 21)), "findings": _FINDINGS_SAMPLE})
    assert len(view.code_viewer.extraSelections()) == 1

    view._on_node_clicked("src/util.js")

    assert view.code_viewer.extraSelections() == []


# --------------------------------------------------------------- polling

def test_poll_tick_does_nothing_without_a_loaded_project(qtbot, monkeypatch):
    _patch_recent(monkeypatch)
    view = CodebaseView()
    qtbot.addWidget(view)
    spy = _spy_on_graph(view)

    view._on_poll_tick()

    assert spy.calls == []


def test_poll_tick_refetches_graph_when_project_loaded(qtbot, monkeypatch):
    calls = {"graph": 0}

    def fake_get(url, **kw):
        if url == config.CODEBASE_GRAPH_URL:
            calls["graph"] += 1
        return _FakeResponse({"projects": [], "edges": [], "nodes": [], "content": "", "language": None, "path": ""})

    monkeypatch.setattr(requests, "get", fake_get)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_poll_tick()
    qtbot.waitUntil(lambda: calls["graph"] >= 1, timeout=2000)


def test_poll_tick_refetches_selected_file_findings(qtbot, monkeypatch):
    calls = {"file": 0}

    def fake_get(url, **kw):
        if url == config.CODEBASE_FILE_URL:
            calls["file"] += 1
        return _FakeResponse({"projects": [], "edges": [], "nodes": [], "content": "code", "language": None, "path": "", "findings": []})

    monkeypatch.setattr(requests, "get", fake_get)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)
    view._on_node_clicked("src/main.py")
    qtbot.waitUntil(lambda: calls["file"] >= 1, timeout=2000)

    calls["file"] = 0
    view._on_poll_tick()

    qtbot.waitUntil(lambda: calls["file"] >= 1, timeout=2000)


def test_poll_tick_does_not_refetch_file_when_none_selected(qtbot, monkeypatch):
    calls = {"file": 0}

    def fake_get(url, **kw):
        if url == config.CODEBASE_FILE_URL:
            calls["file"] += 1
        return _FakeResponse({"projects": [], "edges": [], "nodes": [], "content": "", "language": None, "path": ""})

    monkeypatch.setattr(requests, "get", fake_get)
    view = CodebaseView()
    qtbot.addWidget(view)
    view._on_index_ready(SAMPLE_INDEX)

    view._on_poll_tick()
    qtbot.wait(300)

    assert calls["file"] == 0
