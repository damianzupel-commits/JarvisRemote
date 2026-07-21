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
- `phone_run_command`: ejecución de shell REAL en el celular vía Termux (Intent
  RUN_COMMAND) — código arbitrario, no solo interacción con la UI. El nivel más
  invasivo posible del lado del celular; gateado por `PHONE_SHELL_ENABLED` y
  logueado como auditoría en `phone_link.dispatch_to_phone`. Requiere pasos
  manuales del usuario (Termux instalado desde F-Droid, allow-external-apps,
  permiso Android otorgado) — ver docstring de la tool y el README.
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
    description=(
        "Abre una app instalada en el CELULAR del usuario (Android), a partir de su package name "
        "(ej. 'com.whatsapp'). Usar esta tool cuando el usuario pida abrir una app en su teléfono/celular, "
        "aunque no lo diga explícitamente pero quede claro por contexto (ej. WhatsApp, la calculadora, la "
        "cámara). No usar para abrir programas o sitios web en la PC — para eso están las tools browser_*."
    ),
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


@register_tool(
    name="phone_run_command",
    description=(
        "Ejecuta un comando de shell REAL en el celular (como 'bash -c <command>'), delegando en "
        "Termux vía su Intent RUN_COMMAND. Es el nivel más invasivo posible del lado del celular: "
        "código/comandos arbitrarios, no solo interacción con la UI — usarlo para lo que necesite un "
        "intérprete o herramientas de línea de comandos de verdad (scripts, python, git, curl, etc.), "
        "no para tocar la pantalla (para eso están phone_tap/phone_swipe/phone_type_text/"
        "phone_global_action). Requiere que el usuario tenga Termux instalado desde F-Droid (la "
        "versión de Play Store no sirve), 'allow-external-apps=true' en su "
        "~/.termux/termux.properties, y el permiso Android com.termux.permission.RUN_COMMAND "
        "otorgado a la app — si falta algo de eso, la tool falla con un mensaje explicando qué "
        "configurar, avisale eso al usuario en vez de asumir que el comando corrió. Devuelve stdout, "
        "stderr y exit_code."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Comando de shell a ejecutar (se corre como `bash -c \"<command>\"` dentro de Termux).",
            },
            "timeout": {
                "type": "integer",
                "description": "Segundos a esperar el resultado antes de darlo por perdido (default 30).",
            },
        },
        "required": ["command"],
    },
    target="phone",
)
def phone_run_command(command: str, timeout: int = 30) -> dict:
    _not_routed("phone_run_command")
