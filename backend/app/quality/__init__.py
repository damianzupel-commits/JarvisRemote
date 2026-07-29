"""Centinela de bugs generales de código (no solo seguridad): misma filosofía
que `app/security/` -- el LLM no debe adivinar bugs de lógica leyendo código a
ojo (mismo riesgo de falsos negativos que llevó a usar escáneres reales para
seguridad), así que corre analizadores/linters reales según los lenguajes que
ya detectó el indexador de Codebase: Ruff+mypy para Python, ESLint+tsc para
JS/TS, detekt para Kotlin. Ver `scanners.py` (wrappers reales), `runner.py`
(orquestación) y `store.py` (cache de resultados). Expuesto al LLM vía
`app/tools/quality_scan.py`; los fixes se aplican con el mismo
`code_apply_fix` que usa `app/security/`."""
