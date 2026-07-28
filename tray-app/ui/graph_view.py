"""Vista de grafo de nodos reutilizable -- la usan tanto la pestaña Codebase
(nodos = archivos, coloreados por lenguaje) como Obsidian (nodos = notas,
coloreadas por autor), en vez del árbol/lista plana que tenían antes. Cada
dominio le pasa sus propios nodos/edges/función de color/función de label --
este widget no sabe nada de archivos ni notas.

Es un grafo 3D real (cámara orbitable con el mouse, física de resorte en
vivo), no una vista 2D estática -- se probó primero con `QGraphicsView` +
`networkx.spring_layout` (ver historial de este archivo) pero el resultado no
se sentía como un "grafo de nodos" de verdad. Reimplementar eso a mano en
Qt3D (entidades, transforms, cámara orbital, picking, physics) hubiese sido
mucho más trabajo y mucho más fresco de bugs que embeber una librería JS ya
hecha y probada para exactamente este caso -- de ahí `QWebEngineView` +
`3d-force-graph` (three.js, vendorizado en `web_assets/`, no depende de
internet en runtime). `web_assets/graph3d.html` es la página que arma el
grafo; este módulo solo le manda datos (`window.setGraphData`) y escucha
clicks de nodo de vuelta vía `QWebChannel`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

_HTML_PATH = Path(__file__).resolve().parent / "web_assets" / "graph3d.html"


class _Bridge(QObject):
    node_clicked = Signal(str)

    @Slot(str)
    def onNodeClick(self, node_id: str) -> None:
        self.node_clicked.emit(node_id)


class GraphView(QWidget):
    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("graphView")

        self._ready = False
        self._pending_payload: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._bridge = _Bridge()
        self._bridge.node_clicked.connect(self.node_clicked)

        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)

        self.web = QWebEngineView()
        self.web.page().setWebChannel(self._channel)
        self.web.loadFinished.connect(self._on_load_finished)
        self.web.load(QUrl.fromLocalFile(str(_HTML_PATH)))
        layout.addWidget(self.web, stretch=1)

    def set_graph(
        self,
        nodes: list[dict],
        edges: list[dict],
        id_key: str,
        color_fn: Callable[[dict], str],
        label_fn: Callable[[dict], str],
    ) -> None:
        payload = {
            "nodes": [{"id": n[id_key], "label": label_fn(n), "color": color_fn(n)} for n in nodes],
            "links": [{"source": e["source"], "target": e["target"]} for e in edges],
        }
        if self._ready:
            self._push(payload)
        else:
            self._pending_payload = payload

    def _on_load_finished(self, ok: bool) -> None:
        self._ready = ok
        if ok and self._pending_payload is not None:
            self._push(self._pending_payload)
            self._pending_payload = None

    def _push(self, payload: dict) -> None:
        self.web.page().runJavaScript(f"window.setGraphData({json.dumps(payload)});")
