"""Tool que compila un reporte de auditoría de código en Markdown -- ver
`app/audit_report.py`. Junta hallazgos de seguridad y calidad ya escaneados,
qué fixes/ediciones ya se aplicaron (con su commit, revertible), y un resumen
ejecutivo, y lo guarda como nota nueva en el vault de Obsidian (autor jarvis)
para que quede versionado y visible en la pestaña Obsidian de la UI."""

from __future__ import annotations

from .. import audit_report as audit_report_module
from . import register_tool


@register_tool(
    name="audit_generate_report",
    description=(
        "Compila un reporte de auditoría de código en Markdown para un proyecto ya escaneado con "
        "security_scan_project y/o quality_scan_project: hallazgos abiertos (seguridad + calidad), fixes y "
        "ediciones ya aplicados (con su commit de git, todos revertibles), un resumen ejecutivo, Y el estado de "
        "la ÚLTIMA corrida de tests real (code_run_tests) -- si nunca se corrió, si el proyecto no tiene suite "
        "de tests, o si la última corrida falló, el resumen ejecutivo lo marca en la primera línea, bien visible, "
        "para que 'sin hallazgos abiertos' nunca se lea como 'verificado' sin que además haya tests reales en "
        "verde. Se guarda como nota nueva en el vault de Obsidian (autor jarvis, tag 'reportes') -- queda ahí, "
        "visible en la pestaña Obsidian de la UI, no se pierde como texto de chat."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado)."},
        },
        "required": ["path"],
    },
)
def audit_generate_report(path: str) -> dict:
    return audit_report_module.generate_report(path)
