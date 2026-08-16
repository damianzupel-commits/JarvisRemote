"""Color y estilo del halo del grafo de investigación -- centralidad +
confianza, ver app/investigation/graph_metrics.py (backend) para cómo se
calculan esos dos números reales por nodo. Este archivo solo hace la
traducción número -> visual, mismo criterio de separación que colors.py
(el backend nunca decide un color, solo números; la vista nunca calcula un
número, solo colores/estilos a partir de lo que ya le mandaron).

## Decisión de diseño (dejada a mi criterio, documentada como pidió Damian)

**Centralidad (betweenness, 0-1) -> TAMAÑO y OPACIDAD del halo**: un nodo
con alta centralidad de intermediación (candidato a pivote, spec sección 3)
se ve MÁS GRANDE y MÁS OPACO. Mismo principio multicanal que ya usa el halo
de severidad de Codebase (ver graph3d.html: "la severidad ahora se codifica
también en tamaño y opacidad, no solo en color" -- ya validado en vivo que
codificar solo en color no alcanza para una jerarquía visual correcta, y acá
la centralidad es un valor CONTINUO, no categórico como severidad, así que
hace todavía más falta).

**Confianza (0-1, o None) -> COLOR/HUE del halo**: interpola desde gris
neutro (`#6b7280`, el mismo que `colors.py` ya usa para "lenguaje
desconocido" -- reusado a propósito, no un color nuevo) en confianza 0,
hasta el azul de autoría de Jarvis (`#3b82f6`, `AUTHOR_COLORS['jarvis']` de
este mismo módulo -- misma razón) en confianza 1.

**Por qué esta combinación y no otra**: un halo GRANDE y GRIS es un pivote
real del grafo (mucha centralidad) sobre el que la evidencia todavía es
floja (poca confianza) -- exactamente lo primero que un investigador
necesita revisar. Un halo GRANDE y AZUL es un pivote ya bien respaldado por
evidencia. Un nodo con confianza=None (sin ninguna arista todavía, sin
campo propio) NO tiene halo -- mismo principio que `color_for_severity`:
nunca fabricar una señal visual para "no hay dato todavía".

Este mapeo es autocontenido y no toca el resto de la arquitectura --
graph_view.py/graph3d.html quedan genéricos, reciben el color+estilo ya
calculado, no conocen esta lógica. Si no convence, se cambia acá sin tocar
nada más."""

from __future__ import annotations

from .colors import AUTHOR_COLORS

_LOW_CONFIDENCE_RGB = (0x6B, 0x72, 0x80)  # #6b7280 -- mismo gris que color_for_language usa de fallback
_HIGH_CONFIDENCE_HEX = AUTHOR_COLORS["jarvis"]  # #3b82f6
_HIGH_CONFIDENCE_RGB = (
    int(_HIGH_CONFIDENCE_HEX[1:3], 16), int(_HIGH_CONFIDENCE_HEX[3:5], 16), int(_HIGH_CONFIDENCE_HEX[5:7], 16),
)

# Por debajo de esto no se muestra halo -- evita ruido visual (un halo
# apenas perceptible en CADA nodo de un grafo grande no ayuda a nadie a
# encontrar el pivote real).
_MIN_CENTRALITY_FOR_HALO = 0.05

_MIN_RADIUS_SCALE = 1.0
_MAX_RADIUS_SCALE = 1.6
_MIN_OPACITY = 0.22
_MAX_OPACITY = 0.60


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _lerp_channel(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def color_for_confidence(confidence: float | None) -> str | None:
    if confidence is None:
        return None
    t = _clamp01(confidence)
    r = _lerp_channel(_LOW_CONFIDENCE_RGB[0], _HIGH_CONFIDENCE_RGB[0], t)
    g = _lerp_channel(_LOW_CONFIDENCE_RGB[1], _HIGH_CONFIDENCE_RGB[1], t)
    b = _lerp_channel(_LOW_CONFIDENCE_RGB[2], _HIGH_CONFIDENCE_RGB[2], t)
    return f"#{r:02x}{g:02x}{b:02x}"


def halo_style_for_centrality(centrality: float) -> dict | None:
    if centrality < _MIN_CENTRALITY_FOR_HALO:
        return None
    t = _clamp01(centrality)
    return {
        "radiusScale": round(_MIN_RADIUS_SCALE + (_MAX_RADIUS_SCALE - _MIN_RADIUS_SCALE) * t, 3),
        "opacity": round(_MIN_OPACITY + (_MAX_OPACITY - _MIN_OPACITY) * t, 3),
    }


# Color de RELLENO por tipo de entidad -- capa aparte del halo (que ya
# codifica centralidad/confianza), mismo criterio que Codebase (relleno por
# lenguaje) y Obsidian (relleno por autor): el halo nunca reemplaza el
# relleno, se agrega encima. Paleta fija (8 tipos conocidos, spec sección 1)
# en vez de un hash como color_for_language -- acá SÍ conviene que el mismo
# tipo siempre tenga el mismo color reconocible de un vistazo, no hace falta
# la extensibilidad de "cualquier lenguaje nuevo que aparezca".
_NODE_TYPE_COLORS: dict[str, str] = {
    "Persona": "#f97316",
    "Cuenta": "#22c55e",
    "Dispositivo": "#a855f7",
    "Host": "#06b6d4",
    "Archivo": "#8b8f9c",
    "Transacción": "#eab308",
    "Evento": "#ec4899",
    "Organización": "#14b8a6",
}


def color_for_node_type(tipo: str) -> str:
    return _NODE_TYPE_COLORS.get(tipo, "#9aa0ab")


def investigation_halo(centrality: float, confidence: float | None) -> dict | None:
    """Combina las dos dimensiones en el payload que graph_view.py le manda
    a graph3d.html -- None (sin halo) si CUALQUIERA de las dos no da pie a
    mostrar uno (centralidad despreciable, o confianza desconocida)."""
    color = color_for_confidence(confidence)
    style = halo_style_for_centrality(centrality)
    if color is None or style is None:
        return None
    return {"color": color, **style}
