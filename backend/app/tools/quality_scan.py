"""Tools de detección de bugs generales de código (no solo seguridad) -- ver
`app/quality/`. Misma filosofía que `security_scan.py`: el LLM NO debe adivinar
bugs de lógica leyendo código a ojo (mismo riesgo de falsos negativos que llevó
a usar escáneres reales para seguridad, no al LLM solo). El flujo es igual:

  1. `quality_scan_project` corre analizadores reales (Ruff/mypy para Python,
     ESLint/tsc para JS/TS, detekt para Kotlin, según qué lenguajes detectó
     `codebase_index_project`) y devuelve hallazgos reales con id estable.
  2. `quality_get_finding` trae el contexto de código de un hallazgo puntual.
  3. El fix se aplica con `code_apply_fix` (`app/tools/code_edit.py`) -- el
     mismo tool auditado (dry-run + diff, commit propio y reversible recién
     con confirm=true) que usa el flujo de seguridad.
"""

from __future__ import annotations

from pathlib import Path

from ..quality import store
from ..quality.runner import scan_project
from . import register_tool

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@register_tool(
    name="quality_scan_project",
    description=(
        "Corre analizadores de calidad/bugs REALES (Ruff + mypy si hay Python, ESLint + tsc si hay JS/TS, "
        "detekt si hay Kotlin) sobre un proyecto ya indexado con codebase_index_project (si no está indexado, "
        "lo indexa primero). A diferencia de security_scan_project, esto busca bugs generales (nombres "
        "indefinidos, errores de tipo, variables sin usar, patrones propensos a bugs) -- NO vulnerabilidades "
        "de seguridad, esas las cubre security_scan_project. Devuelve hallazgos reales con severidad, archivo, "
        "línea y regla -- NO son inventados por el modelo. Usa cache salvo refresh=true. Cada hallazgo tiene un "
        "'id' estable para pasarle a code_apply_fix."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la carpeta raíz del proyecto a analizar."},
            "refresh": {
                "type": "boolean",
                "description": "Si es true, ignora el cache y vuelve a correr todos los analizadores. Default false.",
            },
        },
        "required": ["path"],
    },
)
def quality_scan_project(path: str, refresh: bool = False) -> dict:
    result = scan_project(path, refresh=refresh)
    findings_sorted = sorted(result.findings, key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.file, f.line))

    by_severity: dict[str, int] = {}
    for f in result.findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return {
        "root": result.root,
        "scanned_at": result.scanned_at,
        "tools_run": result.tools_run,
        "tools_skipped": result.tools_skipped,
        "total_findings": len(result.findings),
        "findings_by_severity": by_severity,
        "findings": [f.to_dict() for f in findings_sorted[:100]],
        "findings_omitted": max(0, len(findings_sorted) - 100),
    }


@register_tool(
    name="quality_get_finding",
    description=(
        "Trae el detalle completo de un hallazgo de calidad puntual (por su 'id', obtenido de "
        "quality_scan_project) junto con el código real alrededor de la línea afectada -- usar antes de "
        "proponer un fix con code_apply_fix, para ver el contexto exacto del código a modificar."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado)."},
            "finding_id": {"type": "string", "description": "Id del hallazgo, tal como lo devolvió quality_scan_project."},
            "context_lines": {"type": "integer", "description": "Líneas de contexto antes/después a incluir (default 5)."},
        },
        "required": ["path", "finding_id"],
    },
)
def quality_get_finding(path: str, finding_id: str, context_lines: int = 5) -> dict:
    finding = store.find_finding(path, finding_id)
    if finding is None:
        raise ValueError(f"No se encontró el hallazgo '{finding_id}' -- ¿corriste quality_scan_project sobre '{path}'?")

    root = Path(path).resolve()
    file_path = root / finding.file
    code_context = None
    if file_path.is_file():
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, finding.line - context_lines)
        end = min(len(lines), (finding.end_line or finding.line) + context_lines)
        code_context = [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]

    return {"finding": finding.to_dict(), "code_context": code_context}
