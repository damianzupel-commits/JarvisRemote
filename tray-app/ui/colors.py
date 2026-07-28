"""Colores determinísticos por lenguaje (pestaña Codebase) y por autor
(pestaña Obsidian) -- compartido entre las dos vistas para no duplicar la
lógica de asignación de color.

Los lenguajes más comunes tienen un color fijo (los mismos que usa GitHub
para su barra de lenguajes, así resultan reconocibles); cualquier otro cae a
un color determinístico por hash (mismo lenguaje -> siempre mismo color dentro
de una sesión y entre sesiones), en vez de asignar colores al azar por orden
de aparición.
"""

import colorsys
import hashlib

_KNOWN_LANGUAGE_COLORS: dict[str, str] = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "JavaScript (JSX)": "#f1e05a",
    "TypeScript": "#3178c6",
    "TypeScript (TSX)": "#3178c6",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#F05138",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "SCSS": "#c6538c",
    "Vue": "#41b883",
    "Shell": "#89e051",
    "PowerShell": "#012456",
    "SQL": "#e38c00",
    "Dart": "#00B4AB",
    "Markdown": "#8b8f9c",
    "JSON": "#8b8f9c",
    "YAML": "#8b8f9c",
    "TOML": "#8b8f9c",
    "XML": "#8b8f9c",
}

AUTHOR_COLORS: dict[str, str] = {
    "jarvis": "#3b82f6",
    "human": "#22c55e",
}


def color_for_language(language: str | None) -> str:
    if not language:
        return "#6b7280"
    if language in _KNOWN_LANGUAGE_COLORS:
        return _KNOWN_LANGUAGE_COLORS[language]
    # Devuelve siempre hex (#rrggbb), no la sintaxis funcional "hsl(...)" --
    # QColor de Qt no la entiende (queda inválida/negra en QTreeWidgetItem.
    # setForeground), aunque sí la acepta dentro de una QSS stylesheet.
    digest = hashlib.sha256(language.encode("utf-8")).hexdigest()
    hue = (int(digest[:4], 16) % 360) / 360
    r, g, b = colorsys.hls_to_rgb(hue, 0.6, 0.6)  # (h, l, s) -- ojo, no es (h, s, l)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def color_for_author(author: str) -> str:
    return AUTHOR_COLORS.get(author, "#9aa0ab")
