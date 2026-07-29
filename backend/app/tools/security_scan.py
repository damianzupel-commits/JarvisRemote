"""Tools del centinela de seguridad de código (Fase 1 del roadmap de
"profesiones" de Jarvis -- ver la nota de Obsidian "Cómo Jarvis Audita
Seguridad de Código", autor jarvis).

El LLM NO debe intentar encontrar vulnerabilidades por su cuenta leyendo
código a ojo -- demasiado riesgo de falsos negativos para una herramienta que
se presenta como pentesting real. El flujo correcto es:
  1. `security_scan_project` corre escáneres SAST/SCA reales (Semgrep, Bandit,
     cppcheck, clang-tidy si hay compile_commands.json, Trivy) y devuelve
     hallazgos reales, con su id estable.
  2. El LLM interpreta cada hallazgo consultando `obsidian_search_notes` (la
     base de conocimiento ya cargada tiene notas por tipo de vulnerabilidad,
     categoría OWASP y cómo leer falsos positivos de cada herramienta) --
     no inventa la explicación de memoria.
  3. Si hay un fix seguro, el LLM lo redacta (old_snippet -> new_snippet) y lo
     aplica con `code_apply_fix` (ver `app/tools/code_edit.py`), que por
     default hace un dry-run (solo devuelve el diff) y recién escribe +
     commitea si se lo llama de nuevo con confirm=true -- nunca hay un edit
     silencioso. Ese mismo tool también aplica fixes de `quality_scan_project`
     y cualquier otra edición puntual de código.
"""

from __future__ import annotations

from pathlib import Path

from ..security import store
from ..security.runner import scan_project
from . import register_tool

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@register_tool(
    name="security_scan_project",
    description=(
        "Corre escáneres de seguridad REALES (Semgrep multi-lenguaje, Bandit si hay Python, cppcheck si hay "
        "C/C++, clang-tidy además si el proyecto trae compile_commands.json (análisis semántico más profundo), "
        "Trivy para CVEs de dependencias si está instalado) sobre un proyecto ya indexado con codebase_index_project "
        "(si no está indexado, lo indexa primero). Devuelve hallazgos reales con severidad, archivo, línea, "
        "regla y CWE/OWASP -- NO son inventados por el modelo. Usa cache salvo refresh=true (Semgrep con "
        "--config auto puede tardar). Cada hallazgo tiene un 'id' estable para pasarle a security_apply_fix."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la carpeta raíz del proyecto a auditar."},
            "refresh": {
                "type": "boolean",
                "description": "Si es true, ignora el cache y vuelve a correr todos los escáneres. Default false.",
            },
        },
        "required": ["path"],
    },
)
def security_scan_project(path: str, refresh: bool = False) -> dict:
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
        # Cap razonable para no inundar el contexto del modelo en repos grandes con
        # muchos hallazgos de baja severidad -- el resumen por severidad de arriba ya
        # da el panorama completo, esto es el detalle accionable de los más urgentes.
        "findings": [f.to_dict() for f in findings_sorted[:100]],
        "findings_omitted": max(0, len(findings_sorted) - 100),
    }


@register_tool(
    name="security_get_finding",
    description=(
        "Trae el detalle completo de un hallazgo puntual (por su 'id', obtenido de security_scan_project) "
        "junto con el código real alrededor de la línea afectada -- usar antes de proponer un fix con "
        "security_apply_fix, para ver el contexto exacto del código a modificar."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado)."},
            "finding_id": {"type": "string", "description": "Id del hallazgo, tal como lo devolvió security_scan_project."},
            "context_lines": {"type": "integer", "description": "Líneas de contexto antes/después a incluir (default 5)."},
        },
        "required": ["path", "finding_id"],
    },
)
def security_get_finding(path: str, finding_id: str, context_lines: int = 5) -> dict:
    finding = store.find_finding(path, finding_id)
    if finding is None:
        raise ValueError(f"No se encontró el hallazgo '{finding_id}' -- ¿corriste security_scan_project sobre '{path}'?")

    root = Path(path).resolve()
    file_path = root / finding.file
    code_context = None
    if file_path.is_file():
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, finding.line - context_lines)
        end = min(len(lines), (finding.end_line or finding.line) + context_lines)
        code_context = [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]

    return {"finding": finding.to_dict(), "code_context": code_context}
