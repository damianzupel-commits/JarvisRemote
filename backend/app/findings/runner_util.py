"""Orquestación común para "correr N herramientas externas, degradar con
gracia si alguna falta o no aplica" -- mismo patrón repetido en
`security/runner.py` y `quality/runner.py`: cada herramienta se agrega a
`tools_run` (incluso si no encontró nada) o a `tools_skipped` con el motivo
(no instalada, sin archivos aplicables), nunca frena al resto del escaneo."""

from __future__ import annotations

from typing import Callable

from .models import Finding


def run_scanner(
    name: str,
    fn: Callable[..., list[Finding] | None],
    *args: object,
    missing_reason: str,
    tools_run: list[str],
    tools_skipped: dict[str, str],
    findings: list[Finding],
) -> None:
    try:
        result = fn(*args)
    except (TimeoutError, RuntimeError) as exc:
        tools_skipped[name] = str(exc)
        return
    if result is None:
        tools_skipped[name] = missing_reason
    else:
        tools_run.append(name)
        findings.extend(result)
