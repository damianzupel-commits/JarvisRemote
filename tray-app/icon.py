"""Genera el ícono de la bandeja al vuelo con Pillow (sin assets binarios en el repo)."""

from PIL import Image, ImageDraw

_COLORS = {
    "running": (52, 199, 89, 255),
    "starting": (255, 204, 0, 255),
    "stopped": (142, 142, 147, 255),
    "error": (255, 59, 48, 255),
}

_SIZE = 64
_MARGIN = 4


def build_image(state: str) -> Image.Image:
    color = _COLORS.get(state, _COLORS["stopped"])
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((_MARGIN, _MARGIN, _SIZE - _MARGIN, _SIZE - _MARGIN), fill=color)
    draw.text((_SIZE / 2 - 4, _SIZE / 2 - 7), "J", fill=(255, 255, 255, 255))
    return img
