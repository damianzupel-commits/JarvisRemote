"""Tests de `app/findings/noise.py` -- reglas con ruido conocido, compartidas
entre el reporte ejecutivo y el panel de lectura de código de Codebase."""

from app.findings.models import Finding
from app.findings.noise import split_noise


def _finding(rule_id: str, severity: str = "high") -> Finding:
    return Finding(
        id=rule_id, tool="cppcheck", file="a.cpp", line=1, end_line=None,
        severity=severity, rule_id=rule_id, message="msg",
    )


def test_split_noise_filters_cppcheck_analysis_limitation_rules():
    """confirmado real auditando Luanti el 2026-07-29: correr cppcheck archivo
    por archivo (sin el árbol de includes/macros real de una compilación de
    verdad) produce estos tres ids en volumen -- no son vulnerabilidades, son
    cppcheck avisando que le faltó contexto (288 `normalCheckLevelMaxBranches`
    y 33 `unknownMacro`, marcado "high" pese a no ser un hallazgo real, sobre
    un proyecto real de ~379k líneas)."""
    findings = [
        _finding("normalCheckLevelMaxBranches", "info"),
        _finding("unknownMacro", "high"),
        _finding("preprocessorErrorDirective", "high"),
        _finding("arrayIndexOutOfBounds", "high"),  # hallazgo real, no debe filtrarse
    ]

    real, noise = split_noise(findings)

    assert [f.rule_id for f in real] == ["arrayIndexOutOfBounds"]
    assert {f.rule_id for f in noise} == {
        "normalCheckLevelMaxBranches", "unknownMacro", "preprocessorErrorDirective",
    }
