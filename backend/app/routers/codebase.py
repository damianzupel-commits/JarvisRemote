"""Endpoints HTTP que consume la pestaña "Codebase" de la ventana de Jarvis
(tray-app/ui/codebase_view.py) -- a diferencia de las tools de
`app/tools/codebase.py` (pensadas para que el LLM las llame con resultados
resumidos), acá se expone el índice completo para que la UI dibuje el árbol
coloreado por lenguaje."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import verify_api_key
from ..codebase import graph, store
from ..codebase.languages import MAX_FILE_SIZE_BYTES, detect_language
from ..findings import severity_index

router = APIRouter(prefix="/api/codebase", tags=["codebase"], dependencies=[Depends(verify_api_key)])


@router.get("/recent")
async def recent_projects() -> dict:
    return {"projects": store.list_cached_projects()}


@router.get("/index")
async def get_index(path: str = Query(...), refresh: bool = Query(False)) -> dict:
    try:
        index = store.get_or_build(path, refresh=refresh)
    except NotADirectoryError:
        raise HTTPException(status_code=404, detail=f"'{path}' no es una carpeta válida")
    return index.to_dict()


@router.get("/graph")
async def get_graph(path: str = Query(...)) -> dict:
    """Además de nodos/edges, cada nodo trae `severity` (severidad máxima entre
    los hallazgos de seguridad/calidad ya cacheados para ese archivo, o `null` si
    no tuvo hallazgos O el proyecto todavía no se escaneó -- la UI no puede
    distinguir esos dos casos por nodo, por eso `security_scanned`/
    `quality_scanned` van a nivel del grafo entero, para que el halo nunca
    aparezca "limpio" en un proyecto sin escanear)."""
    try:
        index = store.get_or_build(path, refresh=False)
    except NotADirectoryError:
        raise HTTPException(status_code=404, detail=f"'{path}' no es una carpeta válida")

    risk = severity_index.build_file_risk_index(path)
    risk_files = risk["files"]
    nodes = [
        {
            "path": f.path,
            "language": f.language,
            "severity": risk_files.get(f.path, {}).get("severity"),
            "finding_count": risk_files.get(f.path, {}).get("finding_count", 0),
        }
        for f in index.files
    ]
    return {
        "nodes": nodes,
        "edges": graph.build_edges(index),
        "security_scanned": risk["security_scanned"],
        "security_scanned_at": risk["security_scanned_at"],
        "quality_scanned": risk["quality_scanned"],
        "quality_scanned_at": risk["quality_scanned_at"],
    }


@router.get("/file")
async def get_file(path: str = Query(...), file: str = Query(...)) -> dict:
    """Contenido de un archivo del proyecto, para el panel lector de la
    pestaña Codebase (se abre al hacer click en un nodo del grafo). `file` es
    relativo a `path` -- se valida que el resultado no se escape de `path`
    (ej. `file="../../../../Windows/System32/..."`) antes de tocar el disco.

    También trae `findings` (seguridad+calidad ya cacheados para ESE archivo,
    ordenados por severidad descendente, ruido conocido excluido) para que el
    panel muestre de un vistazo qué línea corregir primero -- ver
    `findings/severity_index.py::list_file_findings`."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"'{path}' no es una carpeta válida")

    target = (root / file).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="La ruta del archivo queda fuera del proyecto")

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"'{file}' no existe en el proyecto")

    size = target.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"'{file}' es demasiado grande para mostrar ({size} bytes)")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No pude leer '{file}': {exc}")

    file_findings = severity_index.list_file_findings(root, file)
    return {
        "path": file,
        "content": content,
        "language": detect_language(target.name),
        "findings": file_findings["findings"],
        "findings_noise_omitted": file_findings["noise_omitted"],
        "security_scanned": file_findings["security_scanned"],
        "quality_scanned": file_findings["quality_scanned"],
    }
