"""Genera el ícono de la bandeja al vuelo con Pillow (sin assets binarios en el repo)."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_COLORS = {
    "running": (52, 199, 89, 255),
    "starting": (255, 204, 0, 255),
    "stopped": (142, 142, 147, 255),
    "error": (255, 59, 48, 255),
}

_SIZE = 64
_MARGIN = 2
_BORDER_WIDTH = 5

# Windows reduce esto a 16x16 (o 20x20 con escalado) para la bandeja -- una
# fuente por defecto de Pillow ahí es ilegible. Probamos fuentes bold del
# sistema en orden de preferencia y caemos al default si ninguna existe.
_FONT_CANDIDATES = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"]
_FONT_SIZE = 42


def _load_font() -> ImageFont.ImageFont:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for name in _FONT_CANDIDATES:
        path = windir / "Fonts" / name
        if path.exists():
            return ImageFont.truetype(str(path), _FONT_SIZE)
    return ImageFont.load_default()


_FONT = _load_font()


def build_image(state: str) -> Image.Image:
    color = _COLORS.get(state, _COLORS["stopped"])
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Borde blanco grueso: sin esto el círculo de color se pierde contra
    # fondos de bandeja claros (ej. "stopped" gris sobre taskbar clara) una
    # vez reducido a 16x16. El borde mantiene el círculo legible en ambos
    # temas de Windows.
    draw.ellipse(
        (_MARGIN, _MARGIN, _SIZE - _MARGIN, _SIZE - _MARGIN),
        fill=color,
        outline=(255, 255, 255, 255),
        width=_BORDER_WIDTH,
    )

    text = "J"
    bbox = draw.textbbox((0, 0), text, font=_FONT)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (_SIZE - tw) / 2 - bbox[0]
    y = (_SIZE - th) / 2 - bbox[1]
    draw.text((x, y), text, font=_FONT, fill=(0, 0, 0, 255))

    return img
