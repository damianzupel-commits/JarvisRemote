"""Orquesta qué analizador de calidad correr según los lenguajes que ya
detectó el indexador de Codebase (`app/codebase/`) -- mismo patrón que
`app/security/runner.py`: Ruff+mypy si hay Python, ESLint+tsc si hay JS/TS,
detekt si hay Kotlin."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..codebase import store as codebase_store
from ..findings.models import Finding, ScanResult
from ..findings.rescan import merge_file_findings
from ..findings.runner_util import run_scanner
from . import scanners
from . import store as quality_store

_JS_TS_LANGUAGES = {"JavaScript", "JavaScript (JSX)", "TypeScript", "TypeScript (TSX)"}
_TS_LANGUAGES = {"TypeScript", "TypeScript (TSX)"}


def scan_project(path: str, refresh: bool = False) -> ScanResult:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    if not refresh:
        cached = quality_store.load_scan(root)
        if cached is not None:
            return cached

    index = codebase_store.get_or_build(root, refresh=refresh)
    python_files = [f.path for f in index.files if f.language == "Python"]
    js_ts_files = [f.path for f in index.files if f.language in _JS_TS_LANGUAGES]
    ts_files = [f.path for f in index.files if f.language in _TS_LANGUAGES]
    kotlin_files = [f.path for f in index.files if f.language == "Kotlin"]

    tools_run: list[str] = []
    tools_skipped: dict[str, str] = {}
    findings: list[Finding] = []

    run_scanner(
        "ruff", scanners.run_ruff, root, python_files,
        missing_reason=(
            "sin archivos Python en el proyecto" if not python_files
            else "binario 'ruff' no encontrado (pip install ruff)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "mypy", scanners.run_mypy, root, python_files,
        missing_reason=(
            "sin archivos Python en el proyecto" if not python_files
            else "no se detectaron type hints (o binario 'mypy' no encontrado -- pip install mypy)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "eslint", scanners.run_eslint, root, js_ts_files,
        missing_reason=(
            "sin archivos JS/TS en el proyecto" if not js_ts_files
            else "binario 'eslint' no encontrado (requiere Node.js -- npm install -g eslint)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "tsc", scanners.run_tsc, root, ts_files,
        missing_reason=(
            "sin archivos TypeScript en el proyecto" if not ts_files
            else "sin tsconfig.json (o binario 'tsc' no encontrado -- requiere Node.js, npm install -g typescript)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "detekt", scanners.run_detekt, root, kotlin_files,
        missing_reason=(
            "sin archivos Kotlin en el proyecto" if not kotlin_files
            else "binario 'detekt' no encontrado -- instalar aparte, ver https://detekt.dev/docs/gettingstarted/cli"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )

    result = ScanResult(
        root=str(root),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        tools_run=tools_run,
        tools_skipped=tools_skipped,
        findings=findings,
    )
    quality_store.save_scan(result)
    return result


_JS_TS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx")


def rescan_file(path: str, file: str) -> dict:
    """Re-escanea SOLO `file` en vez de todo el proyecto -- ver
    `security/runner.py::rescan_file`, mismo criterio. Ruff/mypy/ESLint/detekt
    soportan una lista de archivos puntual; tsc NO se re-corre acá (necesita
    el `tsconfig.json` completo para resolver tipos entre archivos, no tiene
    un modo "un solo archivo" confiable -- ver docstring de `run_tsc`), así
    que un fix en un .ts no dispara un rescan de tsc hasta el próximo
    `quality_scan_project` completo."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    target = root / file
    if not target.is_file():
        raise FileNotFoundError(str(target))

    previous = quality_store.load_scan(root)

    tools_run: list[str] = []
    tools_skipped: dict[str, str] = {}
    new_findings: list[Finding] = []

    if file.endswith(".py"):
        run_scanner(
            "ruff", scanners.run_ruff, root, [file],
            missing_reason="binario 'ruff' no encontrado (pip install ruff)",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )
        run_scanner(
            "mypy", scanners.run_mypy, root, [file],
            missing_reason="no se detectaron type hints (o binario 'mypy' no encontrado)",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )
    if file.endswith(_JS_TS_SUFFIXES):
        run_scanner(
            "eslint", scanners.run_eslint, root, [file],
            missing_reason="binario 'eslint' no encontrado (requiere Node.js)",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )
    if file.endswith(".kt"):
        run_scanner(
            "detekt", scanners.run_detekt, root, [file],
            missing_reason="binario 'detekt' no encontrado",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )

    result, resolved, persisting, brand_new = merge_file_findings(
        previous, root, file, new_findings, tools_run, tools_skipped,
    )
    quality_store.save_scan(result)

    return {
        "file": file,
        "resolved": [f.to_dict() for f in resolved],
        "persisting": [f.to_dict() for f in persisting],
        "new": [f.to_dict() for f in brand_new],
    }
