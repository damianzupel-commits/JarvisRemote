"""Wrappers de subprocess sobre analizadores de calidad/bugs reales -- Ruff y
mypy para Python, ESLint y tsc para JS/TS, detekt para Kotlin. Mismo criterio
que `app/security/scanners.py`: el LLM local NO debe intentar "adivinar" bugs
de lógica por su cuenta (riesgo de falsos negativos demasiado alto), así que
estas funciones son puro I/O con binarios externos reales.

Cada `run_*` devuelve `None` si la herramienta no está instalada o no aplica
(ej. ESLint/tsc necesitan Node.js, que no viene con este backend -- a
diferencia de Ruff/mypy, que son paquetes pip como Semgrep/Bandit), nunca
lanza por eso -- la ausencia de una herramienta es un dato para el reporte, no
un error que deba frenar el resto del escaneo.

ESLint (validado el 2026-07-29 contra un binario real, ESLint 10.8.0 + Node
24.18, corriendo sobre NodeGoat) y detekt (esquema del reporte JSON, todavía
sin instalar en esta máquina) -- detekt sigue escrito con el mismo cuidado que
el resto pero sin verificar end-to-end; ver la nota de Obsidian
correspondiente.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..findings.binaries import chunk_paths, node_shim_argv, relpath, tool_path
from ..findings.models import Finding, make_finding_id

_RUFF_TIMEOUT = 60
_MYPY_TIMEOUT = 180
_ESLINT_TIMEOUT = 120
_TSC_TIMEOUT = 180
_DETEKT_TIMEOUT = 180

_RUFF_SEVERITY_PREFIXES = (
    ("E9", "critical"),  # errores de sintaxis / runtime
    ("F82", "high"),  # nombres indefinidos
    ("F63", "high"),  # comparaciones/asserts siempre falsos
    ("F70", "high"),  # sintaxis inválida a nivel semántico (break/continue fuera de loop, etc.)
    ("B", "medium"),  # flake8-bugbear: patrones propensos a bugs
    ("C90", "medium"),  # complejidad ciclomática
)

_MYPY_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+)(?::\d+)?:\s*(?P<severity>error|warning):\s*"
    r"(?P<message>.*?)(?:\s+\[(?P<code>[\w-]+)\])?$"
)
_MYPY_SEVERITY = {"error": "high", "warning": "medium"}

_TSC_LINE_RE = re.compile(r"^(?P<file>.+?)\((?P<line>\d+),\d+\):\s*error\s+(?P<code>TS\d+):\s*(?P<message>.*)$")

_ESLINT_CONFIG_FILES = (
    ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yml", ".eslintrc.yaml",
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
)


def _anchored_relpath(root: Path, raw_path: str) -> str:
    """Como `relpath`, pero para salidas de texto (mypy, tsc) que imprimen
    rutas relativas al cwd del subproceso (`root`, ver los `subprocess.run`
    de más abajo) en vez de absolutas. `relpath` sola con una ruta relativa
    llama a `Path(raw).resolve()`, que la resuelve contra el cwd del proceso
    de ESTE backend (no contra `root`) -- eso duplicaba el prefijo del
    proyecto (ej. `backend/backend/app/...`) cuando el backend corre desde
    `backend/` y se escanea un `root` que lo contiene (bug real encontrado al
    hacer dogfooding del propio repo). Ancla primero la ruta relativa a
    `root` antes de resolver."""
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return relpath(root, str(candidate))


def _ruff_severity(code: str) -> str:
    for prefix, severity in _RUFF_SEVERITY_PREFIXES:
        if code.startswith(prefix):
            return severity
    return "low"


# Ruleset curado para cuando el proyecto NO trae su propia config de Ruff:
# pyflakes (F, nombres indefinidos/imports rotos/vars sin usar), errores de
# sintaxis (E9), flake8-bugbear (B, patrones propensos a bugs reales, ej.
# mutable default args) y solo los errores de Pylint (PLE, no PLR/PLC que son
# refactors/convenciones de estilo). A propósito NO incluye "S" (flake8-bandit):
# eso duplicaría lo que ya cubre security_scan_project con Bandit real.
_RUFF_DEFAULT_SELECT = "F,E9,B,PLE"


def _has_ruff_config(root: Path) -> bool:
    if (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            return "[tool.ruff" in pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
    return False


def run_ruff(root: Path, python_files: list[str]) -> list[Finding] | None:
    """Si el proyecto trae su propia config de Ruff (`pyproject.toml` con
    `[tool.ruff]`, o `ruff.toml`/`.ruff.toml`) se respeta tal cual -- mismo
    criterio que Semgrep `--config auto`. Si no, se corre aislado
    (`--isolated`, ignora cualquier config de un directorio ancestro) con un
    ruleset curado (`_RUFF_DEFAULT_SELECT`) enfocado a bugs reales: el ruleset
    default de Ruff sin ningún `--select` resultó ser casi TODAS las reglas
    (incluido estilo/formato puro), demasiado ruido para "detección de bugs".

    Se le pasa la lista explícita de archivos del índice de Codebase
    (gitignore-aware), mismo motivo que Bandit: evita que escanee
    `.venv`/`node_modules` si se le pidiera correr sobre el árbol completo.

    Se corre en lotes (`chunk_paths`), no en una sola invocación -- mismo
    motivo que Bandit: repos reales grandes superan el límite práctico de
    longitud de línea de comando de Windows (`WinError 206`, confirmado real
    sobre SuperSaaSFastAPI el 2026-07-29)."""
    if not python_files:
        return None
    exe = tool_path("ruff")
    if exe is None:
        return None

    absolute_files = [str(root / f) for f in python_files]
    base_cmd = [exe, "check", "--output-format", "json", "--quiet"]
    if not _has_ruff_config(root):
        base_cmd += ["--isolated", "--select", _RUFF_DEFAULT_SELECT]

    findings: list[Finding] = []
    for batch in chunk_paths(absolute_files):
        try:
            proc = subprocess.run(
                base_cmd + batch,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_RUFF_TIMEOUT,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Ruff no terminó en {_RUFF_TIMEOUT}s")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Ruff no devolvió JSON válido (exit={proc.returncode}): {proc.stderr[:500]}")

        for r in data:
            file_rel = relpath(root, r["filename"])
            line = r["location"]["row"]
            code = r.get("code") or "?"
            findings.append(
                Finding(
                    id=make_finding_id("ruff", file_rel, line, code),
                    tool="ruff",
                    file=file_rel,
                    line=line,
                    end_line=(r.get("end_location") or {}).get("row"),
                    severity=_ruff_severity(code),
                    rule_id=code,
                    message=(r.get("message") or "").strip(),
                )
            )
    return findings


def _looks_typed(root: Path, python_files: list[str], sample_size: int = 25) -> bool:
    """Heurística barata para "¿tiene sentido correr mypy acá?": si al menos un
    archivo de una muestra trae anotaciones de tipo (`-> `, `: tipo =`), el
    proyecto ya usa type hints en serio. Evita correr mypy (y su ruido de
    "no type hints anywhere") sobre proyectos Python sin tipar."""
    annotation_re = re.compile(r":\s*[A-Za-z_][\w\.\[\], |]*\s*=")
    for rel in python_files[:sample_size]:
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "-> " in text or annotation_re.search(text):
            return True
    return False


def run_mypy(root: Path, python_files: list[str]) -> list[Finding] | None:
    """mypy solo si el proyecto ya usa type hints (`_looks_typed`) -- errores
    de tipo son bugs reales, pero correrlo sobre código sin anotar es puro
    ruido ("no se puede inferir nada"). `--ignore-missing-imports` evita falsos
    positivos por dependencias de terceros sin stubs.

    Se corre en lotes (`chunk_paths`) por el mismo límite práctico de longitud
    de línea de comando de Windows que Bandit/Ruff (`WinError 206`, confirmado
    real sobre SuperSaaSFastAPI el 2026-07-29). Nota: correr en lotes separados
    puede perder algo de inferencia cross-archivo que mypy haría con el
    proyecto completo en una sola pasada -- es un trade-off aceptado, la
    alternativa (una sola invocación) directamente no corre en repos grandes."""
    if not python_files or not _looks_typed(root, python_files):
        return None
    exe = tool_path("mypy")
    if exe is None:
        return None

    absolute_files = [str(root / f) for f in python_files]
    base_cmd = [
        exe, "--ignore-missing-imports", "--no-error-summary", "--no-color-output",
        # Sin esto, mypy resuelve el "nombre de módulo" de cada archivo por su
        # nombre de archivo solo -- dos conftest.py en subcarpetas top-level
        # distintas (ej. tray-app/ y backend/tests/, sin paquete común) chocan
        # como "módulo duplicado" y mypy aborta con exit 2 antes de analizar
        # nada (bug real encontrado al hacer dogfooding del propio repo, que
        # tiene justamente ese layout). Con esta flag, mypy determina la ruta
        # de cada módulo según el ancestro sin __init__.py más cercano, así
        # archivos en carpetas top-level distintas no colisionan.
        "--explicit-package-bases",
    ]

    findings: list[Finding] = []
    for batch in chunk_paths(absolute_files):
        try:
            proc = subprocess.run(
                base_cmd + batch,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_MYPY_TIMEOUT,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"mypy no terminó en {_MYPY_TIMEOUT}s")

        batch_findings = []
        for raw_line in proc.stdout.splitlines():
            m = _MYPY_LINE_RE.match(raw_line.strip())
            if not m:
                continue
            file_rel = _anchored_relpath(root, m.group("file"))
            line = int(m.group("line"))
            code = m.group("code") or "mypy-error"
            batch_findings.append(
                Finding(
                    id=make_finding_id("mypy", file_rel, line, code),
                    tool="mypy",
                    file=file_rel,
                    line=line,
                    end_line=None,
                    severity=_MYPY_SEVERITY.get(m.group("severity"), "medium"),
                    rule_id=code,
                    message=m.group("message").strip(),
                )
            )

        # exit 0 = sin hallazgos, 1 = hallazgos encontrados (igual que Bandit) --
        # solo exit >=2 (uso inválido/crash) sin ninguna línea parseada es un error real.
        if proc.returncode not in (0, 1) and not batch_findings:
            raise RuntimeError(f"mypy no pudo correr (exit={proc.returncode}): {proc.stderr[:500]}")
        findings.extend(batch_findings)

    return findings


def run_eslint(root: Path, js_ts_files: list[str]) -> list[Finding] | None:
    """ESLint sobre JS/TS. Si el proyecto ya trae su propia config, se respeta
    tal cual; si no, se genera una config plana (flat config, obligatoria desde
    ESLint 9) temporal basada en `@eslint/js` `recommended` para tener igual una
    pasada razonable por default. Requiere Node.js -- no viene empaquetado con
    este backend (a diferencia de Ruff/mypy, que son pip), así que en una
    instalación sin Node esto se reporta como "saltado", no error.

    La rama sin config propia depende de que `@eslint/js` esté instalado
    globalmente junto a ESLint (`npm install -g eslint @eslint/js`); el config
    temporal vive dentro del repo escaneado (no junto a ESLint), así que su
    `require('@eslint/js')` no lo resolvería solo -- por eso se le pasa
    `NODE_PATH` apuntando al `node_modules` global de ESLint. Validado contra
    un binario real (ESLint 10.8.0) el 2026-07-29 corriendo sobre NodeGoat.

    Se corre en lotes (`chunk_paths`) por el mismo límite práctico de longitud
    de línea de comando de Windows que Bandit/Ruff/mypy (`WinError 206`,
    confirmado real sobre SuperSaaSFastAPI el 2026-07-29)."""
    if not js_ts_files:
        return None
    exe = tool_path("eslint")
    if exe is None:
        return None

    has_config = any((root / name).is_file() for name in _ESLINT_CONFIG_FILES)
    absolute_files = [str(root / f) for f in js_ts_files]
    base_cmd = (node_shim_argv(exe, "eslint", "eslint") or [exe]) + [
        "--format", "json", "--no-error-on-unmatched-pattern",
    ]

    env = dict(os.environ)
    global_node_modules = str(Path(exe).resolve().parent / "node_modules")
    env["NODE_PATH"] = os.pathsep.join(p for p in (global_node_modules, env.get("NODE_PATH")) if p)

    tmp_config: Path | None = None
    if not has_config:
        tmp_config = root / ".jarvis-eslint.config.tmp.cjs"
        tmp_config.write_text(
            "const js = require('@eslint/js');\n"
            "module.exports = [\n"
            "  js.configs.recommended,\n"
            "  { languageOptions: { ecmaVersion: 2021, sourceType: 'module', globals: {\n"
            "    require: 'readonly', module: 'readonly', exports: 'writable', process: 'readonly',\n"
            "    console: 'readonly', __dirname: 'readonly', __filename: 'readonly',\n"
            "    window: 'readonly', document: 'readonly',\n"
            "  } } },\n"
            "];\n",
            encoding="utf-8",
        )
        base_cmd += ["--config", str(tmp_config)]

    findings: list[Finding] = []
    try:
        for batch in chunk_paths(absolute_files):
            try:
                proc = subprocess.run(
                    base_cmd + batch, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_ESLINT_TIMEOUT, cwd=str(root), env=env
                )
            except subprocess.TimeoutExpired:
                raise TimeoutError(f"ESLint no terminó en {_ESLINT_TIMEOUT}s")

            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                raise RuntimeError(f"ESLint no devolvió JSON válido (exit={proc.returncode}): {proc.stderr[:500]}")

            for file_result in data:
                file_rel = relpath(root, file_result["filePath"])
                for msg in file_result.get("messages", []):
                    line = msg.get("line") or 1
                    rule_id = msg.get("ruleId") or "eslint-error"
                    findings.append(
                        Finding(
                            id=make_finding_id("eslint", file_rel, line, rule_id),
                            tool="eslint",
                            file=file_rel,
                            line=line,
                            end_line=msg.get("endLine"),
                            severity="high" if msg.get("severity") == 2 else "medium",
                            rule_id=rule_id,
                            message=(msg.get("message") or "").strip(),
                        )
                    )
    finally:
        if tmp_config is not None:
            tmp_config.unlink(missing_ok=True)

    return findings


def run_tsc(root: Path, ts_files: list[str]) -> list[Finding] | None:
    """`tsc --noEmit` sobre el `tsconfig.json` del proyecto -- necesita el
    tsconfig (no una lista de archivos sueltos) para resolver tipos/paths
    correctamente. Sin tsconfig.json no hay forma confiable de correrlo, se
    salta. Requiere Node.js + typescript instalados globalmente."""
    if not ts_files:
        return None
    tsconfig = root / "tsconfig.json"
    if not tsconfig.is_file():
        return None
    exe = tool_path("tsc")
    if exe is None:
        return None

    cmd = (node_shim_argv(exe, "typescript", "tsc") or [exe]) + ["--noEmit", "-p", str(tsconfig)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=_TSC_TIMEOUT,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"tsc no terminó en {_TSC_TIMEOUT}s")

    findings = []
    for raw_line in proc.stdout.splitlines():
        m = _TSC_LINE_RE.match(raw_line.strip())
        if not m:
            continue
        file_rel = _anchored_relpath(root, m.group("file"))
        findings.append(
            Finding(
                id=make_finding_id("tsc", file_rel, int(m.group("line")), m.group("code")),
                tool="tsc",
                file=file_rel,
                line=int(m.group("line")),
                end_line=None,
                severity="high",
                rule_id=m.group("code"),
                message=m.group("message").strip(),
            )
        )
    return findings


def run_detekt(root: Path, kotlin_files: list[str]) -> list[Finding] | None:
    """detekt (SAST de calidad para Kotlin) -- no viene por pip ni por el JDK
    que ya tiene este equipo (ver [[android-cli-toolchain]]), requiere
    instalar el CLI aparte (ver https://detekt.dev/docs/gettingstarted/cli).

    NOTA: el parseo del reporte JSON no se pudo validar contra un binario real
    (detekt no está instalado en esta máquina) -- escrito de forma defensiva
    (todos los campos con `.get()`) para no romper si el esquema exacto de
    esta versión de detekt difiere; en el peor caso devuelve una lista vacía
    en vez de fallar."""
    if not kotlin_files:
        return None
    exe = tool_path("detekt") or tool_path("detekt-cli")
    if exe is None:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "detekt-report.json"
        input_arg = ",".join(str(root / f) for f in kotlin_files)
        try:
            proc = subprocess.run(
                [exe, "--input", input_arg, "--report", f"json:{report_path}"],
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_DETEKT_TIMEOUT,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"detekt no terminó en {_DETEKT_TIMEOUT}s")

        if not report_path.is_file():
            raise RuntimeError(f"detekt no generó reporte (exit={proc.returncode}): {proc.stderr[:500]}")
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise RuntimeError("detekt generó un reporte JSON inválido")

    issues = data if isinstance(data, list) else data.get("issues", [])
    findings = []
    for issue in issues:
        location = issue.get("location", {}) or {}
        source = location.get("source", location)
        file_raw = location.get("path") or issue.get("file") or ""
        if not file_raw:
            continue
        file_rel = relpath(root, file_raw)
        line = source.get("line", 1) if isinstance(source, dict) else 1
        rule_id = issue.get("rule") or issue.get("id") or "detekt-issue"
        severity_raw = str(issue.get("severity", "")).lower()
        severity = {"error": "high", "warning": "medium", "info": "low"}.get(severity_raw, "medium")
        findings.append(
            Finding(
                id=make_finding_id("detekt", file_rel, line, rule_id),
                tool="detekt",
                file=file_rel,
                line=line,
                end_line=None,
                severity=severity,
                rule_id=rule_id,
                message=(issue.get("message") or "").strip(),
            )
        )
    return findings
