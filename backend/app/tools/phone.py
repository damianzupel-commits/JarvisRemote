"""Tools con `target="phone"`: se despachan al celular conectado por WebSocket
(ver `..phone_link`) en vez de ejecutarse acá. El handler de cada una nunca se
llega a invocar de verdad —`call_tool` intercepta por `target` antes de
llamarlo— pero se define igual por consistencia con el resto del registro y
como red de seguridad si algo llamara al handler directamente.

Equivalentes en el celular a las tools de PC (filesystem, browser/pantalla):
- `phone_open_app`: abre una app por package name.
- `phone_list_dir` / `phone_read_file` / `phone_write_file`: filesystem del
  celular, sandboxeado a la carpeta que el usuario eligió una vez vía Storage
  Access Framework (mismo modelo que `FS_ALLOWED_ROOT` para la PC).
- `phone_tap` / `phone_swipe` / `phone_type_text` / `phone_read_screen` /
  `phone_global_action`: control genérico de pantalla vía el Accessibility
  Service de la app Android — puede leer y accionar sobre cualquier app
  visible en pantalla (incluidas apps de banca, 2FA, WhatsApp, etc.).
"""

from . import register_tool


def _not_routed(name: str):
    raise RuntimeError(
        f"'{name}' es una tool de target=phone: debería haberse despachado por "
        "WebSocket antes de llegar acá. Si ves este error, call_tool no está "
        "enrutando por target correctamente."
    )


@register_tool(
    name="phone_open_app",
    description="Abre una app instalada en el celular a partir de su package name (ej. 'com.whatsapp').",
    parameters={
        "type": "object",
        "properties": {
            "package_name": {
                "type": "string",
                "description": "Package name de la app a abrir (ej. 'com.whatsapp', 'com.android.chrome').",
            }
        },
        "required": ["package_name"],
    },
    target="phone",
)
def phone_open_app(package_name: str) -> dict:
    _not_routed("phone_open_app")


@register_tool(
    name="phone_list_dir",
    description=(
        "Lista archivos y subcarpetas dentro de la carpeta que el usuario eligió en el celular "
        "(vía selector de Storage Access Framework)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta relativa a la carpeta elegida (o '.' para la raíz).",
            }
        },
        "required": [],
    },
    target="phone",
)
def phone_list_dir(path: str = ".") -> dict:
    _not_routed("phone_list_dir")


@register_tool(
    name="phone_read_file",
    description="Lee el contenido de texto de un archivo dentro de la carpeta elegida en el celular.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta relativa a la carpeta elegida."},
            "max_chars": {
                "type": "integer",
                "description": "Máximo de caracteres a devolver (default 20000).",
            },
        },
        "required": ["path"],
    },
    target="phone",
)
def phone_read_file(path: str, max_chars: int = 20000) -> dict:
    _not_routed("phone_read_file")


@register_tool(
    name="phone_write_file",
    description="Crea o sobreescribe un archivo dentro de la carpeta elegida en el celular.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta relativa a la carpeta elegida."},
            "content": {"type": "string", "description": "Contenido de texto a escribir."},
            "append": {
                "type": "boolean",
                "description": "Si es true, agrega al final en vez de sobreescribir. Default false.",
            },
        },
        "required": ["path", "content"],
    },
    target="phone",
)
def phone_write_file(path: str, content: str, append: bool = False) -> dict:
    _not_routed("phone_write_file")


@register_tool(
    name="phone_tap",
    description="Simula un toque en la pantalla del celular en las coordenadas dadas (píxeles).",
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Coordenada X en píxeles."},
            "y": {"type": "integer", "description": "Coordenada Y en píxeles."},
        },
        "required": ["x", "y"],
    },
    target="phone",
)
def phone_tap(x: int, y: int) -> dict:
    _not_routed("phone_tap")


@register_tool(
    name="phone_swipe",
    description="Simula un swipe/arrastre en la pantalla del celular entre dos puntos.",
    parameters={
        "type": "object",
        "properties": {
            "x1": {"type": "integer", "description": "X inicial en píxeles."},
            "y1": {"type": "integer", "description": "Y inicial en píxeles."},
            "x2": {"type": "integer", "description": "X final en píxeles."},
            "y2": {"type": "integer", "description": "Y final en píxeles."},
            "duration_ms": {
                "type": "integer",
                "description": "Duración del gesto en milisegundos (default 300).",
            },
        },
        "required": ["x1", "y1", "x2", "y2"],
    },
    target="phone",
)
def phone_swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> dict:
    _not_routed("phone_swipe")


@register_tool(
    name="phone_type_text",
    description=(
        "Escribe texto en el campo de entrada actualmente enfocado en la pantalla del celular "
        "(tiene que haber un campo de texto con foco; usar phone_tap para enfocarlo primero si hace falta)."
    ),
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Texto a escribir."}},
        "required": ["text"],
    },
    target="phone",
)
def phone_type_text(text: str) -> dict:
    _not_routed("phone_type_text")


@register_tool(
    name="phone_read_screen",
    description=(
        "Devuelve un volcado del contenido de la pantalla actual del celular (texto, descripciones, "
        "posiciones y qué elementos son clickeables), leído vía el Accessibility Service. "
        "Funciona sobre cualquier app en pantalla."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
    target="phone",
)
def phone_read_screen() -> dict:
    _not_routed("phone_read_screen")


@register_tool(
    name="phone_global_action",
    description="Ejecuta una acción global de navegación del celular.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["back", "home", "recents", "notifications"],
                "description": "Acción a ejecutar.",
            }
        },
        "required": ["action"],
    },
    target="phone",
)
def phone_global_action(action: str) -> dict:
    _not_routed("phone_global_action")
