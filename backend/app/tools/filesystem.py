"""Tools de filesystem: listar, leer, escribir, crear y mover archivos/carpetas.

Todas las rutas se resuelven relativas (o absolutas, si caen adentro) a
`settings.fs_allowed_root`. Cualquier intento de salir de esa carpeta falla.
Borrar está deshabilitado salvo que `FS_ALLOW_DELETE=true` en el .env.
"""

from pathlib import Path

from .. import audit_log
from ..codebase import store as codebase_store
from ..codeedit import fixer
from ..config import settings
from . import register_tool


def _resolve(path: str) -> Path:
    root = Path(settings.fs_allowed_root).resolve()
    candidate = Path(path)
    target = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"Path '{path}' está fuera de la carpeta permitida ({root})")
    return target


def _find_indexed_git_project(target: Path) -> Path | None:
    """Si `target` cae dentro de un repo git que ya fue indexado con
    codebase_index_project, devuelve la raíz de ese repo -- usado por
    fs_write_file para decidir si la escritura tiene que pasar por el circuito
    auditado/reversible de app/codeedit (ver la nota de Obsidian de auditoría),
    en vez de ser una escritura silenciosa como cualquier otro archivo bajo
    FS_ALLOWED_ROOT.

    Se detiene en el primer '.git' que encuentra subiendo desde el archivo --
    ese es el repo real de ese archivo. Si ese repo puntual no está indexado,
    no sigue subiendo a buscar un ancestro más arriba que sí lo esté: un
    ancestro indexado no sería "el proyecto" al que pertenece este archivo."""
    for ancestor in target.parents:
        if (ancestor / ".git").exists():
            return ancestor if codebase_store.load_cached(ancestor) is not None else None
    return None


@register_tool(
    name="fs_list_dir",
    description="Lista archivos y subcarpetas de un directorio en la PC del usuario.",
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
    description="Lee el contenido de texto de un archivo en la PC del usuario.",
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
    description=(
        "Crea o sobreescribe un archivo en la PC del usuario con el contenido dado "
        "(crea carpetas intermedias si hace falta). Si el archivo cae dentro de un proyecto ya indexado con "
        "codebase_index_project y que además es un repo git, la escritura queda commiteada aparte de forma "
        "reversible (git revert) -- ver el campo 'commit' del resultado."
    ),
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
    result = {"path": str(target), "bytes_written": len(content.encode("utf-8")), "append": append}

    project_root = _find_indexed_git_project(target)
    if project_root is None:
        result["audited"] = False
        return result

    file_rel = target.relative_to(project_root).as_posix()
    action = "agrega contenido a" if append else "escribe"
    commit_message = f"chore: Jarvis {action} '{file_rel}' via fs_write_file"
    commit_info = fixer.commit_if_eligible(project_root, file_rel, commit_message)

    result["audited"] = True
    result["commit"] = commit_info
    audit_log.log_tool_call(
        target="fs",
        tool="fs_write_file",
        arguments={"path": str(project_root), "file": file_rel, "append": append},
        result=commit_info,
    )
    return result


@register_tool(
    name="fs_create_dir",
    description="Crea una carpeta en la PC del usuario (y las intermedias que hagan falta).",
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
    description="Mueve o renombra un archivo o carpeta en la PC del usuario, dentro de la raíz permitida.",
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
        "Borra un archivo o carpeta en la PC del usuario (recursivamente). Deshabilitado por default: "
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
