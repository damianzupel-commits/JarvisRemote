"""Tool genérica y auditada para aplicar ediciones de código puntuales -- ver
`app/codeedit/fixer.py`. Compartida por el flujo de seguridad
(`security_scan_project`/`security_get_finding`), el de calidad
(`quality_scan_project`/`quality_get_finding`) y cualquier otra edición
puntual de código dentro de un proyecto: no le importa de dónde salió el
cambio, solo aplica `old_snippet -> new_snippet` de forma mecánica y
auditable (dry-run + diff por default, commit propio y reversible recién con
confirm=true).
"""

from __future__ import annotations

from .. import audit_log
from ..codeedit import fixer
from ..quality import runner as quality_runner
from ..security import runner as security_runner
from . import register_tool

_SEVERITY_LABEL = {"critical": "crítico", "high": "alto", "medium": "medio", "low": "bajo", "info": "informativo"}
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _describe_cascade(resolved: list[dict], new_findings: list[dict]) -> str | None:
    """Mensaje en criollo del efecto del fix sobre el resto de los hallazgos
    del archivo -- puro diff de ids antes/después (ver findings/rescan.py),
    no se infiere causalidad real. `None` si no hay nada que contar (fix
    aplicado pero no resolvió ni introdujo nada más, ej. una edición que no
    tocaba ningún hallazgo)."""
    if not resolved and not new_findings:
        return None
    parts = []
    if resolved:
        counts: dict[str, int] = {}
        for f in resolved:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        breakdown = ", ".join(
            f"{n} {_SEVERITY_LABEL.get(sev, sev)}"
            for sev, n in sorted(counts.items(), key=lambda kv: _SEVERITY_ORDER.get(kv[0], 9))
        )
        parts.append(f"Este fix resolvió {len(resolved)} hallazgo(s) en el archivo ({breakdown}).")
    if new_findings:
        parts.append(
            f"Atención: el cambio también introdujo {len(new_findings)} hallazgo(s) nuevo(s) -- "
            "revisalos antes de dar esto por cerrado."
        )
    return " ".join(parts)


def _rescan_after_fix(path: str, file: str) -> dict:
    """Re-escanea SOLO `file` (seguridad + calidad) después de un fix aplicado
    con éxito -- así el halo del nodo en el grafo 3D y el panel de hallazgos
    de la pestaña Codebase reflejan el estado real sin que el usuario tenga
    que reindexar/reescanear todo el proyecto a mano. Si el rescan puntual
    falla por algún motivo, no se cae el resultado del fix (que ya se aplicó
    y commiteó) -- solo queda sin info de cascada."""
    try:
        sec = security_runner.rescan_file(path, file)
    except Exception:
        sec = {"resolved": [], "persisting": [], "new": []}
    try:
        qual = quality_runner.rescan_file(path, file)
    except Exception:
        qual = {"resolved": [], "persisting": [], "new": []}

    resolved = sec["resolved"] + qual["resolved"]
    persisting = sec["persisting"] + qual["persisting"]
    new_findings = sec["new"] + qual["new"]

    return {
        "resolved_findings": resolved,
        "persisting_findings": persisting,
        "new_findings": new_findings,
        "cascade_message": _describe_cascade(resolved, new_findings),
    }


@register_tool(
    name="code_apply_fix",
    description=(
        "Aplica (o previsualiza) un cambio puntual de código, reemplazando old_snippet por new_snippet en el "
        "archivo indicado -- sirve tanto para fixes de un hallazgo de security_scan_project/quality_scan_project "
        "como para cualquier otra edición puntual de código dentro de un proyecto (no hace falta que venga de un "
        "hallazgo). Por default (confirm=false, RECOMENDADO para la primera llamada) es un dry-run: no escribe "
        "nada, solo devuelve el diff exacto para que el usuario lo revise. Recién con confirm=true escribe el "
        "archivo y, si el proyecto es un repo git, crea un commit separado y reversible (git revert) solo con ese "
        "cambio -- nunca mezcla varios cambios en un commit. old_snippet debe matchear EXACTAMENTE una vez en el "
        "archivo (con suficiente contexto para ser único), igual que una edición normal."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto."},
            "file": {"type": "string", "description": "Ruta del archivo relativa a la raíz del proyecto."},
            "old_snippet": {"type": "string", "description": "Texto exacto a reemplazar (debe aparecer una única vez en el archivo)."},
            "new_snippet": {"type": "string", "description": "Texto de reemplazo."},
            "commit_message": {
                "type": "string",
                "description": "Mensaje de commit si se aplica (ej. 'fix: SQL injection en query.py:42 (auto-fix Jarvis, hallazgo Semgrep)').",
            },
            "confirm": {
                "type": "boolean",
                "description": "Si es true, aplica y commitea de verdad. Si es false (default), solo devuelve el diff sin tocar nada.",
            },
        },
        "required": ["path", "file", "old_snippet", "new_snippet", "commit_message"],
    },
)
def code_apply_fix(
    path: str,
    file: str,
    old_snippet: str,
    new_snippet: str,
    commit_message: str,
    confirm: bool = False,
) -> dict:
    arguments = {"path": path, "file": file, "commit_message": commit_message, "confirm": confirm}
    try:
        result = fixer.apply_fix(
            root=path,
            file=file,
            old_snippet=old_snippet,
            new_snippet=new_snippet,
            commit_message=commit_message,
            confirm=confirm,
        )
    except Exception as exc:
        # Auditar solo la rama que de verdad escribe (confirm=true) -- un dry-run
        # (confirm=false) no modifica nada real, mismo criterio que separa
        # codebase_index_project (no auditado) de desktop/phone (sí auditados).
        if confirm:
            audit_log.log_tool_call(target="code", tool="code_apply_fix", arguments=arguments, error=str(exc))
        raise
    if confirm and result.get("applied"):
        result["rescan"] = _rescan_after_fix(path, file)
    if confirm:
        audit_log.log_tool_call(target="code", tool="code_apply_fix", arguments=arguments, result=result)
    return result
