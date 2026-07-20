"""Tools de filesystem: listar, leer, escribir, crear y mover archivos/carpetas.

Todas las rutas se resuelven relativas (o absolutas, si caen adentro) a
`settings.fs_allowed_root`. Cualquier intento de salir de esa carpeta falla.
Borrar está deshabilitado salvo que `FS_ALLOW_DELETE=true` en el .env.
"""

from pathlib import Path

from ..config import settings
from . import register_tool


def _resolve(path: str) -> Path:
    root = Path(settings.fs_allowed_root).resolve()
    candidate = Path(path)
    target = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"Path '{path}' está fuera de la carpeta permitida ({root})")
    return target


@register_tool(
    name="fs_list_dir",
    description="Lista archivos y subcarpetas de un directorio.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta relativa a la raíz permitida (o '.' para la raíz).",
            }
        },
        "required": [],
    },
)
def fs_list_dir(path: str = ".") -> dict:
    target = _resolve(path)
    if not target.exists():
        raise FileNotFoundError(str(target))
    if not target.is_dir():
        raise NotADirectoryError(str(target))
    entries = []
    for entry in sorted(target.iterdir()):
        entries.append(
            {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size_bytes": entry.stat().st_size if entry.is_file() else None,
            }
        )
    return {"path": str(target), "entries": entries}


@register_tool(
    name="fs_read_file",
    description="Lee el contenido de texto de un archivo.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta relativa a la raíz permitida."},
            "max_chars": {
                "type": "integer",
                "description": "Máximo de caracteres a devolver (default 20000).",
            },
        },
        "required": ["path"],
    },
)
def fs_read_file(path: str, max_chars: int = 20000) -> dict:
    target = _resolve(path)
    if not target.is_file():
        raise FileNotFoundError(str(target))
    content = target.read_text(encoding="utf-8", errors="replace")
    truncated = len(content) > max_chars
    return {
        "path": str(target),
        "content": content[:max_chars],
        "truncated": truncated,
    }


@register_tool(
    name="fs_write_file",
    description="Crea o sobreescribe un archivo con el contenido dado (crea carpetas intermedias si hace falta).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta relativa a la raíz permitida."},
            "content": {"type": "string", "description": "Contenido de texto a escribir."},
            "append": {
                "type": "boolean",
                "description": "Si es true, agrega al final en vez de sobreescribir. Default false.",
            },
        },
        "required": ["path", "content"],
    },
)
def fs_write_file(path: str, content: str, append: bool = False) -> dict:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with target.open(mode, encoding="utf-8") as f:
        f.write(content)
    return {"path": str(target), "bytes_written": len(content.encode("utf-8")), "append": append}


@register_tool(
    name="fs_create_dir",
    description="Crea una carpeta (y las intermedias que hagan falta).",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Ruta relativa a la raíz permitida."}},
        "required": ["path"],
    },
)
def fs_create_dir(path: str) -> dict:
    target = _resolve(path)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": str(target)}


@register_tool(
    name="fs_move_path",
    description="Mueve o renombra un archivo o carpeta dentro de la raíz permitida.",
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Ruta actual, relativa a la raíz permitida."},
            "destination": {"type": "string", "description": "Ruta destino, relativa a la raíz permitida."},
        },
        "required": ["source", "destination"],
    },
)
def fs_move_path(source: str, destination: str) -> dict:
    src = _resolve(source)
    dst = _resolve(destination)
    if not src.exists():
        raise FileNotFoundError(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return {"from": str(src), "to": str(dst)}


@register_tool(
    name="fs_delete_path",
    description=(
        "Borra un archivo o carpeta (recursivamente). Deshabilitado por default: "
        "requiere FS_ALLOW_DELETE=true en el .env del backend."
    ),
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Ruta relativa a la raíz permitida."}},
        "required": ["path"],
    },
)
def fs_delete_path(path: str) -> dict:
    if not settings.fs_allow_delete:
        raise PermissionError(
            "Borrado deshabilitado. Setear FS_ALLOW_DELETE=true en backend/.env para habilitarlo."
        )
    target = _resolve(path)
    if not target.exists():
        raise FileNotFoundError(str(target))
    if target.is_dir():
        import shutil

        shutil.rmtree(target)
    else:
        target.unlink()
    return {"deleted": str(target)}
