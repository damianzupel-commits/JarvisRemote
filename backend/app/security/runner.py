"""Orquesta qué escáner correr según los lenguajes que ya detectó el indexador
de Codebase (`app/codebase/`) -- no reinventa esa detección, la reusa. Ver la
tabla de decisión en la nota de Obsidian "Cómo Jarvis Audita Seguridad de
Código": Semgrep corre siempre (multi-lenguaje), Bandit solo si hay Python,
Trivy siempre que el binario esté instalado (SCA no depende del lenguaje del
código, depende de qué manifiestos de dependencias haya).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..codebase import store as codebase_store
from ..findings.rescan import merge_file_findings
from ..findings.runner_util import run_scanner
from . import scanners
from . import store as security_store
from .models import Finding, ScanResult


def scan_project(path: str, refresh: bool = False) -> ScanResult:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    if not refresh:
        cached = security_store.load_scan(root)
        if cached is not None:
            return cached

    index = codebase_store.get_or_build(root, refresh=refresh)
    python_files = [f.path for f in index.files if f.language == "Python"]
    cpp_files = [f.path for f in index.files if f.language in ("C", "C++")]
    compile_commands_dir = scanners.find_compile_commands_dir(root)

    tools_run: list[str] = []
    tools_skipped: dict[str, str] = {}
    findings: list[Finding] = []

    run_scanner(
        "semgrep", scanners.run_semgrep, root,
        missing_reason="binario 'semgrep' no encontrado (pip install semgrep)",
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "bandit", scanners.run_bandit, root, python_files,
        missing_reason=(
            "sin archivos Python en el proyecto" if not python_files
            else "binario 'bandit' no encontrado (pip install bandit)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "cppcheck", scanners.run_cppcheck, root, cpp_files,
        missing_reason=(
            "sin archivos C/C++ en el proyecto" if not cpp_files
            else "binario 'cppcheck' no encontrado (pip install cppcheck)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "clang-tidy", scanners.run_clang_tidy, root, cpp_files, compile_commands_dir,
        missing_reason=(
            "sin archivos C/C++ en el proyecto" if not cpp_files
            else "sin compile_commands.json (generalo con 'cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON' "
                 "o el equivalente del build system del proyecto) -- sin eso clang-tidy no puede parsear código real"
            if compile_commands_dir is None
            else "binario 'clang-tidy' no encontrado (pip install clang-tidy)"
        ),
        tools_run=tools_run, tools_skipped=tools_skipped, findings=findings,
    )
    run_scanner(
        "trivy", scanners.run_trivy, root,
        missing_reason=(
            "binario 'trivy' no encontrado -- instalar aparte (no es paquete pip), "
            "ver https://trivy.dev/latest/getting-started/installation/"
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

    security_store.save_scan(result)
    return result


# Manifiestos de dependencias que sí justifica re-escanear con Trivy en un
# rescan puntual -- Trivy es SCA (analiza manifiestos, no código fuente), así
# que solo tiene sentido volver a correrlo cuando el archivo fixeado ES uno de
# estos; para cualquier otro archivo, re-correr Trivy sería pagar el costo de
# escanear TODO el árbol de dependencias del proyecto para nada.
_TRIVY_MANIFEST_NAMES = {
    "requirements.txt", "package.json", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "build.gradle", "build.gradle.kts", "pom.xml", "Pipfile.lock",
}


def rescan_file(path: str, file: str) -> dict:
    """Re-escanea SOLO `file` (relativo a `path`) en vez de todo el proyecto --
    pensado para correr después de aplicar un fix puntual (`code_apply_fix`),
    no como reemplazo de `scan_project`. Semgrep y Bandit soportan apuntar a
    un archivo puntual (ver `scanners.run_semgrep`/`python_files=[file]`);
    Trivy (SCA de manifiestos) solo se re-corre si `file` es uno de esos
    manifiestos -- ver `_TRIVY_MANIFEST_NAMES`. Si el proyecto nunca se
    escaneó antes (sin cache previo), funciona igual: no hay nada para
    comparar como "resuelto", todo lo que aparezca ahora es "nuevo"."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    target = root / file
    if not target.is_file():
        raise FileNotFoundError(str(target))

    previous = security_store.load_scan(root)

    tools_run: list[str] = []
    tools_skipped: dict[str, str] = {}
    new_findings: list[Finding] = []

    run_scanner(
        "semgrep", scanners.run_semgrep, root, target,
        missing_reason="binario 'semgrep' no encontrado (pip install semgrep)",
        tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
    )

    if file.endswith(".py"):
        run_scanner(
            "bandit", scanners.run_bandit, root, [file],
            missing_reason="binario 'bandit' no encontrado (pip install bandit)",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )

    if file.lower().endswith((".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh")):
        run_scanner(
            "cppcheck", scanners.run_cppcheck, root, [file],
            missing_reason="binario 'cppcheck' no encontrado (pip install cppcheck)",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )
        compile_commands_dir = scanners.find_compile_commands_dir(root)
        run_scanner(
            "clang-tidy", scanners.run_clang_tidy, root, [file], compile_commands_dir,
            missing_reason=(
                "sin compile_commands.json" if compile_commands_dir is None
                else "binario 'clang-tidy' no encontrado (pip install clang-tidy)"
            ),
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )

    if Path(file).name in _TRIVY_MANIFEST_NAMES:
        run_scanner(
            "trivy", scanners.run_trivy, root,
            missing_reason="binario 'trivy' no encontrado",
            tools_run=tools_run, tools_skipped=tools_skipped, findings=new_findings,
        )
        # Trivy escanea el árbol completo de manifiestos -- se acota a este
        # archivo antes de mergear, para no reintroducir hallazgos de OTROS
        # manifiestos que ni tocamos.
        new_findings[:] = [f for f in new_findings if f.tool != "trivy" or f.file == file]

    result, resolved, persisting, brand_new = merge_file_findings(
        previous, root, file, new_findings, tools_run, tools_skipped,
    )
    security_store.save_scan(result)

    return {
        "file": file,
        "resolved": [f.to_dict() for f in resolved],
        "persisting": [f.to_dict() for f in persisting],
        "new": [f.to_dict() for f in brand_new],
    }
