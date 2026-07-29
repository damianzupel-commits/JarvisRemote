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

from PySide6.QtCore import QObject, QSize, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Bug real visto en vivo: la primera vez que esta vista se hace
        # visible (ej. al entrar a la pestaña Codebase, que arranca oculta
        # detrás de Chat), Chromium a veces nunca sincroniza su viewport real
        # con el tamaño que Qt ya le dio al widget -- `window.innerWidth`
        # queda en 0 del lado de la página aunque `self.web.size()` ya sea
        # correcto, y el grafo entero queda en negro (reproducido con
        # `--disable-gpu-compositing`, el flag de tray.py para el crash de la
        # GPU AMD -- pinta ser una interacción entre ese modo y el mecanismo
        # de "recién visible -> avisale al proceso de render" de QtWebEngine).
        QTimer.singleShot(0, self._nudge_viewport_sync)

    def _nudge_viewport_sync(self) -> None:
        # OJO -- NO llamar a `self.web.resize(...)` acá. Versión anterior de
        # este fix hacía justo eso (achicar/agrandar 1px la geometría real del
        # widget) y funcionaba para destrabar el viewport, pero como `self.web`
        # está dentro de un layout (QSplitter -> CodebaseView -> QMainWindow),
        # ese resize directo sobre un widget administrado por layout dispara una
        # re-evaluación de geometría que termina agrandando la VENTANA
        # PRINCIPAL entera -- y Qt no la vuelve a achicar sola después (no hay
        # "shrink to fit" automático para ventanas top-level), dejando la
        # ventana permanentemente más ancha/alta. Bug real reportado en vivo
        # ("la ventana se ve ultra alargada, no entra en mi pantalla"),
        # reproducido y confirmado: el ancho saltaba de 900 a 1112px apenas se
        # entraba a la pestaña Codebase, exactamente cuando este método corría.
        #
        # La solución es no tocar la geometría real del widget en absoluto --
        # `QApplication.sendEvent` entrega un QResizeEvent sintético
        # directamente al manejador de eventos de QWebEngineView (que sí
        # dispara la sincronización de viewport con Chromium) sin pasar por el
        # sistema de layouts, así que ni la ventana ni ningún widget cambia de
        # tamaño de verdad -- verificado en vivo que el viewport igual queda
        # sincronizado (`window.innerWidth` correcto) sin ningún efecto
        # colateral en la geometría de la ventana.
        size = self.web.size()
        if not size.isValid() or size.width() <= 0 or size.height() <= 0:
            return
        fake_old_size = QSize(max(0, size.width() - 1), size.height())
        QApplication.sendEvent(self.web, QResizeEvent(size, fake_old_size))

    def set_graph(
        self,
        nodes: list[dict],
        edges: list[dict],
        id_key: str,
        color_fn: Callable[[dict], str],
        label_fn: Callable[[dict], str],
        severity_color_fn: Callable[[dict], str | None] | None = None,
    ) -> None:
        def _node_payload(n: dict) -> dict:
            node = {"id": n[id_key], "label": label_fn(n), "color": color_fn(n)}
            severity_color = severity_color_fn(n) if severity_color_fn else None
            # Solo se manda la clave si hay halo -- graph3d.html la trata como
            # "sin marca" cuando falta, así no hace falta pasarle `null` por
            # cada nodo sin hallazgos.
            if severity_color:
                node["severityColor"] = severity_color
            return node

        payload = {
            "nodes": [_node_payload(n) for n in nodes],
            "links": [{"source": e["source"], "target": e["target"]} for e in edges],
        }
        if self._ready:
            self._push(payload)
        else:
            self._pending_payload = payload

    def update_severity(self, severity_by_id: dict[str, str | None]) -> None:
        """Actualiza SOLO el halo de severidad de nodos ya existentes, sin
        recrear el dataset ni tocar el layout de fuerzas -- a diferencia de
        `set_graph`. Pensado para refrescos periódicos sobre un grafo YA
        cargado (ver CodebaseView._on_poll_tick): llamar a `set_graph` de
        nuevo ahí reiniciaba el "calor" de la simulación de d3-force cada vez,
        haciendo que el grafo entero se reacomodara de golpe cada pocos
        segundos -- bug real reportado en vivo. Si la página todavía no
        cargó, no hace nada (no tiene sentido encolar esto: `set_graph` ya se
        habrá encargado de la carga inicial con la data completa)."""
        if not self._ready:
            return
        self.web.page().runJavaScript(f"window.updateNodeSeverity({json.dumps(severity_by_id)});")

    def _on_load_finished(self, ok: bool) -> None:
        self._ready = ok
        if ok and self._pending_payload is not None:
            self._push(self._pending_payload)
            self._pending_payload = None

    def _push(self, payload: dict) -> None:
        self.web.page().runJavaScript(f"window.setGraphData({json.dumps(payload)});")
