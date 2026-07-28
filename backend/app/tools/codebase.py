"""Tools de análisis de codebase: detectar lenguajes e indexar la estructura
completa (archivos, funciones, clases, imports) de un proyecto dado.

A diferencia de `fs_*` (filesystem.py), estas tools son de solo lectura y no
están sandboxeadas a `FS_ALLOWED_ROOT` -- el usuario puede pedir analizar
cualquier repo en su disco (ej. uno de otro proyecto suyo), y el índice
resultante se guarda aparte (`settings.codebase_index_dir`), nunca dentro del
proyecto analizado. Ver `app/codebase/` para la lógica de indexado.
"""

from __future__ import annotations

from ..codebase import store
from . import register_tool


def _summary(index) -> dict:
    return {
        "root": index.root,
        "indexed_at": index.indexed_at,
        "file_count": index.file_count,
        "primary_language": index.primary_language,
        "languages": [
            {"language": s.language, "file_count": s.file_count, "line_count": s.line_count}
            for s in index.languages
        ],
        "top_level_entries": sorted({f.path.split("/")[0] for f in index.files}),
    }


@register_tool(
    name="codebase_index_project",
    description=(
        "Analiza un proyecto/repo completo en el disco: detecta automáticamente los lenguajes de "
        "programación usados y construye un índice estructural completo (todos los archivos, y sus "
        "funciones/clases/imports). Devuelve un resumen (desglose de lenguajes, cantidad de archivos, "
        "carpetas de primer nivel) -- usar codebase_search_symbol o codebase_file_outline para ver el "
        "detalle. Tarda más la primera vez; usa un cache salvo refresh=true."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la carpeta raíz del proyecto a analizar."},
            "refresh": {
                "type": "boolean",
                "description": "Si es true, ignora el cache y re-analiza todo el proyecto desde cero. Default false.",
            },
        },
        "required": ["path"],
    },
)
def codebase_index_project(path: str, refresh: bool = False) -> dict:
    index = store.get_or_build(path, refresh=refresh)
    return _summary(index)


@register_tool(
    name="codebase_search_symbol",
    description=(
        "Busca funciones o clases por nombre (coincidencia parcial, sin distinguir mayúsculas) dentro "
        "de un proyecto ya indexado con codebase_index_project. Devuelve en qué archivo y línea aparece "
        "cada coincidencia."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la carpeta raíz del proyecto (ya indexado)."},
            "name": {"type": "string", "description": "Nombre (o parte del nombre) de la función/clase a buscar."},
            "limit": {"type": "integer", "description": "Máximo de resultados (default 20)."},
        },
        "required": ["path", "name"],
    },
)
def codebase_search_symbol(path: str, name: str, limit: int = 20) -> dict:
    index = store.load_cached(path)
    if index is None:
        raise ValueError(f"'{path}' no está indexado todavía -- llamá primero a codebase_index_project.")

    needle = name.lower()
    matches = []
    for f in index.files:
        for sym in f.symbols:
            if sym.kind == "import":
                continue
            if needle in sym.name.lower():
                matches.append({"file": f.path, "line": sym.line, "kind": sym.kind, "name": sym.name})

    return {"query": name, "matches": matches[:limit], "total_matches": len(matches)}


@register_tool(
    name="codebase_file_outline",
    description=(
        "Devuelve el lenguaje y la lista de símbolos (funciones, clases, imports, con su línea) de un "
        "archivo puntual dentro de un proyecto ya indexado con codebase_index_project."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la carpeta raíz del proyecto (ya indexado)."},
            "file": {"type": "string", "description": "Ruta del archivo relativa a la raíz del proyecto."},
        },
        "required": ["path", "file"],
    },
)
def codebase_file_outline(path: str, file: str) -> dict:
    index = store.load_cached(path)
    if index is None:
        raise ValueError(f"'{path}' no está indexado todavía -- llamá primero a codebase_index_project.")

    normalized = file.replace("\\", "/").lstrip("/")
    entry = next((f for f in index.files if f.path == normalized), None)
    if entry is None:
        raise FileNotFoundError(f"'{file}' no está en el índice de '{path}'.")

    return {
        "path": entry.path,
        "language": entry.language,
        "line_count": entry.line_count,
        "symbols": [{"kind": s.kind, "name": s.name, "line": s.line} for s in entry.symbols],
    }
