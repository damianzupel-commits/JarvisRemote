"""Filtro de "ruido conocido" compartido entre el reporte ejecutivo
(`audit_report.py`) y el panel de lectura de código de la pestaña Codebase
(`GET /api/codebase/file`) -- antes vivía solo en `audit_report.py`; se separa
acá para que ambos consumidores usen exactamente la misma lista de reglas
ruidosas, sin arriesgarse a que diverjan con el tiempo.
"""

from __future__ import annotations

from .models import Finding

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Reglas con ruido conocido muy alto -- casi siempre falsos positivos o
# hallazgos no accionables en la práctica, no vulnerabilidades reales.
# Confirmado auditando repos externos reales el 2026-07-29: sobre httpie/cli
# (código real, no vulnerable a propósito), 768 de 854 hallazgos de seguridad
# eran B101 sobre `assert` dentro de tests/*.py -- ruido clásico y documentado
# de Bandit, no algo que ningún equipo trate como vulnerabilidad.
KNOWN_NOISE_RULES: dict[str, str] = {
    "B101": "bandit assert_used -- marca todo uso de `assert`, casi siempre en test suites",
    # cppcheck se corre archivo por archivo desde la lista del índice de Codebase
    # (ver app/security/scanners.py::run_cppcheck), no compilando el proyecto de
    # verdad -- sin el árbol de includes/macros real, estos tres ids no son
    # hallazgos de seguridad, son cppcheck avisando que le faltó contexto para
    # terminar de analizar. Confirmado real auditando Luanti el 2026-07-29: 288
    # `normalCheckLevelMaxBranches` y 33 `unknownMacro` (marcado "high" por
    # cppcheck, pese a no ser una vulnerabilidad) sobre un proyecto real de
    # ~379k líneas.
    "normalCheckLevelMaxBranches": "cppcheck avisando límite de profundidad de análisis, no es un hallazgo real",
    "unknownMacro": "cppcheck no pudo resolver una macro sin el árbol de includes completo (limitación de escanear archivo por archivo en vez de compilar)",
    "preprocessorErrorDirective": "#include/#error no resuelto por faltar el árbol de includes completo, no una directiva de seguridad real",
}


def split_noise(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """Separa hallazgos en (reales, ruido conocido) según `KNOWN_NOISE_RULES`."""
    real = [f for f in findings if f.rule_id not in KNOWN_NOISE_RULES]
    noise = [f for f in findings if f.rule_id in KNOWN_NOISE_RULES]
    return real, noise
