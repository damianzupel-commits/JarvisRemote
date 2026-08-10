"""Widgets chicos compartidos entre pestañas -- por ahora solo `NoMinWidthLabel`.

Separado en su propio módulo (en vez de vivir en cada vista) porque el mismo
bug lo pisan varias vistas a la vez (chat, Codebase, Obsidian) y conviene un
solo lugar para el fix en vez de reescribirlo tres veces.
"""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel


class NoMinWidthLabel(QLabel):
    """QLabel con word-wrap cuyo ancho MÍNIMO nunca fuerza el crecimiento de la
    ventana principal, ni siquiera con un token sin espacios larguísimo.

    Bug real reportado en vivo más de una vez ("la ventana se ve ultra
    alargada, no entra en mi pantalla"): `QLabel.setWordWrap(True)` sólo puede
    cortar línea en espacios -- si el texto trae UN SOLO token sin espacios
    muy largo (una URL, un path largo, el repr de un objeto Python tipo
    `<urllib3.connection.HTTPConnection object at 0x...>` dentro de un mensaje
    de excepción, un hash), `minimumSizeHint()` termina siendo el ancho
    completo de ESE token -- porque el label literalmente no puede achicarse
    más sin cortarlo. Ese mínimo se propaga hacia arriba por el layout hasta
    forzar el ancho de la ventana top-level, que Qt después nunca vuelve a
    achicar sola. Encontrado primero en `CodebaseView.status_label` (mensajes
    de error de conexión al backend, que traen justamente URLs largas y reprs
    de excepción sin espacios) pero el mismo riesgo existe en cualquier label
    que muestre texto dinámico (mensajes de chat, título/tags de notas de
    Obsidian) -- de ahí que valga la pena resolverlo acá una sola vez.

    Devolver ancho 0 en `minimumSizeHint()` sacar por completo el ancho de la
    ecuación del layout: el texto que no entra se corta visualmente (clip) en
    vez de romper la geometría de la ventana. El alto lo sigue calculando
    Qt normalmente (heightForWidth ya hace lo suyo aparte, esto no lo toca)."""

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())
