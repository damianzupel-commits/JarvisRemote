"""Wrappers de subprocess sobre escáneres SAST/SCA reales -- Semgrep, Bandit,
Trivy. A propósito NO reimplementamos ningún analizador de vulnerabilidades acá:
el LLM local no debe intentar "adivinar" vulnerabilidades por su cuenta (riesgo
de falsos negativos demasiado alto para una herramienta de auditoría real), así
que estas funciones son puro I/O con binarios externos -- mismo patrón que
`_comfyui_shared.py` para Ollama/ComfyUI, pero por CLI en vez de HTTP.

Cada `run_*` devuelve `None` si la herramienta no está instalada o no aplica
(por ejemplo Bandit sin archivos Python), nunca lanza por eso -- la ausencia de
una herramienta es un dato para el reporte ("Trivy no está instalado"), no un
error que deba frenar el resto del escaneo.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from ..findings.binaries import chunk_paths as _chunk_paths
from ..findings.binaries import relpath as _relpath
from ..findings.binaries import tool_path as _tool_path
from .models import Finding, make_finding_id

_SEMGREP_TIMEOUT = 300
_BANDIT_TIMEOUT = 120
_TRIVY_TIMEOUT = 180
_CPPCHECK_TIMEOUT = 300
_CLANG_TIDY_TIMEOUT = 300

_SEMGREP_SEVERITY = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
_BANDIT_SEVERITY = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
_TRIVY_SEVERITY = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "info",
}
# cppcheck no distingue "critical" -- "error" ya es su categoría más grave
# (buffer overflow, null deref, use-after-free, memory leak reales), se mapea
# a "high" para quedar en la misma escala que el resto de los hallazgos de
# `error`/`ERROR`/`HIGH` de los otros escáneres. "style"/"performance"/
# "portability" son sugerencias de calidad, no vulnerabilidades -- "low".
_CPPCHECK_SEVERITY = {
    "error": "high",
    "warning": "medium",
    "portability": "low",
    "performance": "low",
    "style": "low",
    "information": "info",
}
# Extensiones que son inequívocamente C++ (a diferencia de `.h`, que
# `languages.py` mapea a "C" aunque en la práctica lo comparten C y C++) --
# usado para decidir si forzar `--language=c++` en `run_cppcheck`.
_CPP_SOURCE_EXTS = (".cpp", ".cc", ".cxx", ".hpp", ".hh")

# clang-tidy no trae headers de stdlib propios como cppcheck (`cfg/`) -- es
# el compilador real de Clang, así que sin `-p <build-dir>` apuntando a un
# `compile_commands.json` real (flags de include/macros de la compilación de
# verdad), casi cualquier archivo con un `#include` de la librería estándar
# falla directo con "file not found" antes de poder analizar nada. Curado a
# checks de bugs/seguridad reales -- igual criterio que cppcheck
# (`--enable=warning`, sin sumar `style`/`performance`): `bugprone-*`
# (patrones de bugs reales tipo use-after-move), `cert-*` (el CERT C/C++
# Secure Coding Standard -- overflow, bounds, manejo de recursos,
# genuinamente de seguridad, no solo estilo) y `clang-analyzer-*` (el Clang
# Static Analyzer real: dataflow interprocedural con path-sensitivity, la
# clase de análisis más profundo que cppcheck no hace -- confirmado real
# auditando Luanti el 2026-07-30: encontró un puntero interno usado tras
# reallocation, una llamada virtual durante destrucción y un campo sin
# inicializar que cppcheck no señaló). Se excluye explícitamente
# `clang-analyzer-optin.performance.*` (ej. "Excessive padding in struct" --
# es una sugerencia de layout/performance, no un hallazgo de seguridad,
# confirmado real mezclado con severidad "high" antes de excluirlo). NO existe
# una categoría `security-*` propia en clang-tidy (confirmado con
# `--list-checks --checks='*'`) -- a propósito tampoco se suma
# `cppcoreguidelines-*`/`modernize-*`/`readability-*` (mezclan mucho estilo,
# no seguridad).
_CLANG_TIDY_CHECKS = "-*,bugprone-*,cert-*,clang-analyzer-*,-clang-analyzer-optin.performance.*"
_CLANG_TIDY_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s*(?P<severity>error|warning):\s*"
    r"(?P<message>.*?)\s*\[(?P<check>[\w.\-]+)\]$"
)
# Heurística de severidad por prefijo del check, no un mapeo 1:1 como
# Semgrep/Bandit (clang-tidy no expone una severidad propia más allá de
# error/warning, que en la práctica son casi todas "warning" -- ver docstring
# de `run_clang_tidy`): `clang-analyzer-` es el análisis semántico profundo
# (dataflow real), queda "high"; `bugprone-`/`cert-` son patrones de bugs más
# superficiales (sintácticos/locales), "medium".
_CLANG_TIDY_HIGH_PREFIXES = ("clang-analyzer-",)
_CLANG_TIDY_MEDIUM_PREFIXES = ("bugprone-", "cert-")


def _as_tag_list(value: object) -> list[str]:
    """Normaliza un campo de metadata (`cwe`/`owasp`) a lista de strings --
    la mayoría de las reglas de Semgrep devuelven una lista, pero algunas
    (confirmado con 'django-no-csrf-token', entre otras) lo devuelven como un
    único string plano. `list(str)` explota ese string caracter por caracter
    (ej. "CWE-352: ..." -> ["C","W","E","-","3","5","2",...]), así que hay que
    distinguir el caso string antes de convertir a lista."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return list(value)
    return []


def run_semgrep(root: Path, scan_target: Path | None = None) -> list[Finding] | None:
    """Corre Semgrep con `--config auto` (autodetecta lenguajes y trae
    reglas relevantes del registro público). Multi-lenguaje -- es el escáner
    principal para JS/TS, Kotlin, y secundario (dataflow) para Python.

    `scan_target` (default: `root`, todo el proyecto) permite apuntar a un
    archivo puntual en vez de al árbol completo -- lo usa `rescan_file` (ver
    `findings/rescan.py`) para no re-escanear todo el proyecto solo para ver
    si UN archivo sigue teniendo hallazgos después de un fix. `cwd` sigue
    siendo siempre `root` (la raíz del proyecto), nunca el archivo -- Semgrep
    necesita el árbol completo como contexto para reglas con reglas
    interprocedurales/dataflow, aunque el target puntual acote qué reporta."""
    exe = _tool_path("semgrep")
    if exe is None:
        return None

    target = scan_target if scan_target is not None else root
    try:
        proc = subprocess.run(
            [exe, "scan", "--config", "auto", "--json", "--quiet", str(target)],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=_SEMGREP_TIMEOUT,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Semgrep no terminó en {_SEMGREP_TIMEOUT}s")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Semgrep no devolvió JSON válido (exit={proc.returncode}): {proc.stderr[:500]}")

    findings = []
    for r in data.get("results", []):
        extra = r.get("extra", {})
        metadata = extra.get("metadata", {})
        file_rel = _relpath(root, r["path"])
        line = r["start"]["line"]
        rule_id = r["check_id"]
        findings.append(
            Finding(
                id=make_finding_id("semgrep", file_rel, line, rule_id),
                tool="semgrep",
                file=file_rel,
                line=line,
                end_line=r.get("end", {}).get("line"),
                severity=_SEMGREP_SEVERITY.get(extra.get("severity", ""), "medium"),
                rule_id=rule_id,
                message=extra.get("message", "").strip(),
                cwe=_as_tag_list(metadata.get("cwe")),
                owasp=_as_tag_list(metadata.get("owasp")),
                confidence=metadata.get("confidence"),
            )
        )
    return findings


def run_bandit(root: Path, python_files: list[str]) -> list[Finding] | None:
    """Corre Bandit (SAST específico de Python) sobre los archivos .py que ya
    trajo el índice de Codebase (gitignore-aware). Devuelve None si Bandit no
    está instalado o si no hay archivos Python -- no tiene sentido correrlo
    sobre un proyecto sin Python.

    A propósito NO se usa `bandit -r <root>`: Bandit no respeta .gitignore por
    su cuenta, así que un `-r` recursivo sobre la raíz del proyecto termina
    escaneando también `.venv/` (miles de archivos de dependencias instaladas)
    -- confirmado en la práctica: sobre este mismo repo eso hizo que Bandit no
    terminara ni en 120s. Pasarle la lista explícita de archivos del índice
    evita ese problema de raíz.

    La lista se pasa en lotes (`chunk_paths`), no en una sola invocación: un
    repo real con muchos archivos (743 .py en SuperSaaSFastAPI, confirmado
    real el 2026-07-29) supera el límite práctico de longitud de línea de
    comando de Windows y `CreateProcess` tira `WinError 206` (mensaje engañoso,
    no es un archivo puntual el problema, es la línea de comando completa)."""
    if not python_files:
        return None
    exe = _tool_path("bandit")
    if exe is None:
        return None

    absolute_files = [str(root / f) for f in python_files]
    findings: list[Finding] = []
    for batch in _chunk_paths(absolute_files):
        try:
            proc = subprocess.run(
                [exe, *batch, "-f", "json", "-q"],
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_BANDIT_TIMEOUT,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Bandit no terminó en {_BANDIT_TIMEOUT}s")

        # Bandit sale con exit code 1 cuando SÍ encuentra issues -- no es una
        # señal de error, a diferencia de la mayoría de las CLIs. Solo tratamos
        # como error real si el stdout no es JSON parseable.
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Bandit no devolvió JSON válido (exit={proc.returncode}): {proc.stderr[:500]}")

        for r in data.get("results", []):
            file_rel = _relpath(root, r["filename"])
            line = r["line_number"]
            rule_id = r["test_id"]
            cwe = r.get("issue_cwe", {})
            findings.append(
                Finding(
                    id=make_finding_id("bandit", file_rel, line, rule_id),
                    tool="bandit",
                    file=file_rel,
                    line=line,
                    end_line=(r.get("line_range") or [line])[-1],
                    severity=_BANDIT_SEVERITY.get(r.get("issue_severity", ""), "medium"),
                    rule_id=rule_id,
                    message=r.get("issue_text", "").strip(),
                    cwe=[f"CWE-{cwe['id']}"] if cwe.get("id") else [],
                    confidence=r.get("issue_confidence"),
                )
            )
    return findings


def run_cppcheck(root: Path, cpp_files: list[str]) -> list[Finding] | None:
    """Corre cppcheck (SAST real para C/C++ -- Semgrep casi no tiene reglas
    efectivas para este stack, confirmado real auditando Luanti el 2026-07-29:
    0 hallazgos, no porque el proyecto esté limpio, sino porque no había
    herramienta que supiera leer C/C++ en serio) sobre los archivos .c/.h/.cpp/
    .hpp/etc. que ya trajo el índice de Codebase (gitignore-aware) -- mismo
    motivo que Bandit/Ruff: evita que escanee dependencias vendorizadas si se
    le pidiera correr sobre el árbol completo.

    El binario viene del paquete pip `cppcheck` (wheel de terceros que empaqueta
    el binario real de cppcheck, ver requirements.txt) -- a diferencia de Trivy,
    no hace falta instalación aparte ni admin/UAC: cae solito en
    `.venv/Scripts/cppcheck.exe`, que `_tool_path` ya sabe encontrar.

    El reporte va por XML a **stderr**, no a stdout -- particularidad real de
    cppcheck (stdout solo lleva el progreso "Checking X..." con `-q` ya
    suprimido). `--enable=warning` suma checks de bugs reales (null deref,
    resource/memory leak, uninitialized var) más allá de la clase `error`
    (siempre activa); a propósito NO se suma `style`/`performance` acá --son
    sugerencias de calidad, no hallazgos de seguridad, y este escáner vive en
    `security/`, no en `quality/`. Tampoco se usa `--force` (probar todas las
    combinaciones de `#ifdef`): en un proyecto grande con mucha compilación
    condicional (ej. Luanti) puede multiplicar el tiempo de análisis por archivo
    sin aportar hallazgos de seguridad adicionales proporcionales al costo.

    Se corre en lotes (`chunk_paths`) por el mismo límite práctico de longitud
    de línea de comando de Windows que Bandit/Ruff/mypy.

    Nota sobre `.h`: `languages.py::EXTENSION_TO_LANGUAGE` mapea CUALQUIER `.h`
    a lenguaje "C" (no puede saber, solo por la extensión, si el header es en
    realidad C++ -- `.h` lo usan ambos) -- sin ayuda, cppcheck hace la misma
    suposición y parsea esos archivos como C puro. Confirmado real auditando
    Luanti el 2026-07-29: eso producía 351 falsos `syntaxError` ("high") sobre
    headers de Irrlicht con `namespace`/`class` (código C++ real, sintaxis
    inválida en C). Si `cpp_files` trae al menos un archivo con extensión de
    fuente C++ inequívoca (`_CPP_SOURCE_EXTS`), se asume que el proyecto entero
    es C++ y se fuerza `--language=c++` -- en la práctica, un proyecto mixto
    con headers `.h` compartidos entre código C y C++ es casi siempre C++ de
    verdad (guía que da el propio cppcheck para este caso), y parsear C válido
    como C++ casi nunca produce falsos positivos nuevos (la excepción real:
    identificadores que son palabra reservada en C++ pero no en C, ej. una
    variable llamada `class` -- infrecuente en la práctica)."""
    if not cpp_files:
        return None
    exe = _tool_path("cppcheck")
    if exe is None:
        return None

    absolute_files = [str(root / f) for f in cpp_files]
    jobs = str(max(1, os.cpu_count() or 1))
    base_cmd = [
        exe, "--enable=warning", "-q", "--xml", "--xml-version=2", "-j", jobs,
        "--suppress=missingInclude", "--suppress=missingIncludeSystem",
    ]
    if any(f.endswith(_CPP_SOURCE_EXTS) for f in cpp_files):
        base_cmd.append("--language=c++")

    findings: list[Finding] = []
    for batch in _chunk_paths(absolute_files):
        try:
            proc = subprocess.run(
                base_cmd + batch,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_CPPCHECK_TIMEOUT,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"cppcheck no terminó en {_CPPCHECK_TIMEOUT}s")

        # cppcheck manda el reporte XML a stderr, no a stdout (a propósito,
        # documentado en su propio --help) -- y sale con exit 0 incluso cuando
        # sí encuentra issues, a diferencia de Bandit/mypy.
        try:
            xml_root = ET.fromstring(proc.stderr)
        except ET.ParseError:
            raise RuntimeError(f"cppcheck no devolvió XML válido (exit={proc.returncode}): {proc.stderr[:500]}")

        for error_el in xml_root.findall("./errors/error"):
            rule_id = error_el.get("id", "cppcheck-issue")
            severity_raw = error_el.get("severity", "")
            message = error_el.get("msg", "").strip()
            cwe = error_el.get("cwe")
            location = error_el.find("location")
            if location is None:
                continue
            file_rel = _relpath(root, location.get("file", ""))
            line = int(location.get("line") or 1)
            findings.append(
                Finding(
                    id=make_finding_id("cppcheck", file_rel, line, rule_id),
                    tool="cppcheck",
                    file=file_rel,
                    line=line,
                    end_line=None,
                    severity=_CPPCHECK_SEVERITY.get(severity_raw, "medium"),
                    rule_id=rule_id,
                    message=message,
                    cwe=[f"CWE-{cwe}"] if cwe else [],
                )
            )
    return findings


def find_compile_commands_dir(root: Path) -> Path | None:
    """Ubica el directorio que trae `compile_commands.json` (la "compilation
    database" real, generada con `cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`
    o equivalente) -- `clang-tidy -p <ese dir>` lo necesita para saber las
    flags de include/macros/standard reales de cada archivo. Se busca primero
    en la raíz del proyecto (dónde muchos proyectos lo symlinkean/copian a
    propósito para herramientas como esta) y si no, un nivel adentro en
    cualquier carpeta (cubre el caso más común, `build/compile_commands.json`,
    sin asumir un nombre fijo de carpeta de build). `None` si no existe --
    `run_clang_tidy` NUNCA debe correr sin esto (ver su docstring).

    Ojo al generarlo con CMake: el generador `-G "Unix Makefiles"`/
    `"MinGW Makefiles"` puede volcar los flags de include en un
    `@archivo_de_respuesta` referenciado desde `compile_commands.json` en vez
    de inline -- y ESE archivo recién se crea cuando de verdad se corre el
    build (`make`/`mingw32-make`), no en el configure. Si solo se corrió
    `cmake -B build` sin buildear nada, clang-tidy lee un `compile_commands.json`
    con referencias a archivos que no existen todavía y falla en cascada con
    "file not found" en casi todo (confirmado real el 2026-07-30 auditando
    Luanti). `-G "Ninja"` no tiene este problema (siempre vuelca los flags
    inline) -- preferirlo para generar la compilation database, aunque el
    build en sí después se corra con otro generador."""
    direct = root / "compile_commands.json"
    if direct.is_file():
        return root
    for candidate in sorted(root.glob("*/compile_commands.json")):
        return candidate.parent
    return None


def _detect_gnu_cross_target_args(compile_commands_dir: Path) -> list[str]:
    """clang-tidy trae su propio Clang embebido, que en Windows por defecto
    apunta al target `x86_64-pc-windows-msvc` -- si el `compile_commands.json`
    real fue generado con un compilador estilo GCC/MinGW (no MSVC), Clang
    reconoce los flags GNU (`-mthreads`, etc. -- el "driver mode" sí se infiere
    bien del nombre del ejecutable) pero los rechaza igual porque el target
    sigue siendo msvc ("unsupported option ... for target
    x86_64-pc-windows-msvc"), y sin las rutas de include propias de ESE GCC
    (`--gcc-toolchain`) tampoco encuentra la librería estándar real. Confirmado
    real el 2026-07-30 validando contra un build real de Luanti con MinGW
    portable: sin este fix, análisis fallaba en cascada ("'vector' file not
    found") en la mayoría de los archivos reales del proyecto.

    Se detecta consultando `<compilador> -dumpmachine` (lo soportan GCC/Clang,
    NO MSVC `cl.exe`/`clang-cl.exe` -- por eso sirve para distinguir el caso
    sin necesidad de parsear flags a mano) sobre el compilador que el propio
    `compile_commands.json` dice haber usado -- generalizado a cualquier
    instalación GCC/MinGW real, no hardcodeado a una ruta particular."""
    cc_path = compile_commands_dir / "compile_commands.json"
    try:
        entries = json.loads(cc_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not entries:
        return []

    first = entries[0]
    if "arguments" in first and first["arguments"]:
        compiler = first["arguments"][0]
    else:
        compiler = first.get("command", "").split(" ", 1)[0].strip('"')
    if not compiler:
        return []
    compiler_name = Path(compiler).name.lower()
    if compiler_name in ("cl.exe", "cl", "clang-cl.exe", "clang-cl"):
        return []

    try:
        proc = subprocess.run(
            [compiler, "-dumpmachine"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    triple = proc.stdout.strip()
    toolchain_root = Path(compiler).resolve().parent.parent
    return [f"--extra-arg=--target={triple}", f"--extra-arg=--gcc-toolchain={toolchain_root}"]


def run_clang_tidy(root: Path, cpp_files: list[str], compile_commands_dir: Path | None) -> list[Finding] | None:
    """Corre clang-tidy -- análisis semántico real (Clang Static Analyzer vía
    `clang-analyzer-*`: dataflow interprocedural con path-sensitivity), la
    clase de bug más profunda que cppcheck no hace (cppcheck analiza
    sintácticamente, sin construir un AST semánticamente completo).

    A diferencia de cppcheck (que trae su propio set de headers sintéticos
    para poder analizar sin un toolchain real, ver `cfg/` en su instalación),
    clang-tidy ES el compilador real de Clang -- sin `compile_commands.json`
    real (flags de include/macros/standard de la compilación real del
    proyecto), casi CUALQUIER archivo con un solo `#include` de la librería
    estándar falla de entrada con "file not found" antes de analizar una sola
    línea. Confirmado real el 2026-07-30: en esta máquina (sin ningún
    compilador C/C++ instalado -- ni MSVC ni MinGW ni el propio Clang trae uno
    -- clang-tidy viene de un wheel de pip que solo empaqueta el binario, no
    un toolchain completo) hasta `#include <stdlib.h>` en un .c vacío falla.
    Por eso, a propósito, esta función NUNCA corre sin un `compile_commands_dir`
    real (ver `find_compile_commands_dir` y el gateo en `runner.py`) -- correrla
    igual "mejor que nada" sería, en la práctica, pura salida de ruido (100% de
    los archivos reales fallando por header no encontrado), no un hallazgo real.

    El reporte es texto plano por stdout (clang-tidy no tiene un formato
    JSON/XML estable entre versiones para esto -- solo `--export-fixes` en
    YAML, que trae reemplazos de auto-fix, no diagnósticos con severidad),
    mismo criterio de parseo por regex que mypy/tsc en `quality/scanners.py`.
    Las líneas `note:` (contexto del path del analyzer, ej. "Memory is
    allocated" / "Memory is released") se ignoran a propósito -- son parte del
    mismo diagnóstico que la línea `warning:`/`error:` que las precede, no
    hallazgos nuevos.

    Exit code NO indica si hubo hallazgos (a diferencia de Bandit/mypy) -- va
    en 0 aun con warnings reales, y sube a 1 cuando hay un error de compilación
    real (header faltante, sintaxis inválida) en alguno de los archivos del
    lote; como eso puede pasar de forma legítima en un lote grande (un header
    autogenerado que todavía no se generó, por ejemplo) sin invalidar los
    hallazgos reales de los demás archivos, no se trata como error fatal."""
    if not cpp_files or compile_commands_dir is None:
        return None
    exe = _tool_path("clang-tidy")
    if exe is None:
        return None

    absolute_files = [str(root / f) for f in cpp_files]
    base_cmd = [exe, "-p", str(compile_commands_dir), "--checks", _CLANG_TIDY_CHECKS, "--quiet"]
    base_cmd += _detect_gnu_cross_target_args(compile_commands_dir)

    findings: list[Finding] = []
    for batch in _chunk_paths(absolute_files):
        try:
            proc = subprocess.run(
                base_cmd + batch,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_CLANG_TIDY_TIMEOUT,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"clang-tidy no terminó en {_CLANG_TIDY_TIMEOUT}s")

        for raw_line in proc.stdout.splitlines():
            m = _CLANG_TIDY_LINE_RE.match(raw_line.strip())
            if not m:
                continue
            file_rel = _relpath(root, m.group("file"))
            check = m.group("check")
            if check.startswith(_CLANG_TIDY_HIGH_PREFIXES):
                severity = "high"
            elif check.startswith(_CLANG_TIDY_MEDIUM_PREFIXES):
                severity = "medium"
            else:
                severity = "low"
            findings.append(
                Finding(
                    id=make_finding_id("clang-tidy", file_rel, int(m.group("line")), check),
                    tool="clang-tidy",
                    file=file_rel,
                    line=int(m.group("line")),
                    end_line=None,
                    severity=severity,
                    rule_id=check,
                    message=m.group("message").strip(),
                )
            )
    return findings


def run_trivy(root: Path) -> list[Finding] | None:
    """SCA de dependencias (`trivy fs`) -- CVEs conocidos en requirements.txt,
    package.json/package-lock.json, build.gradle, etc. Devuelve None si el
    binario `trivy` no está instalado (no viene empaquetado por pip, a
    diferencia de Semgrep/Bandit -- requiere instalación aparte)."""
    exe = _tool_path("trivy")
    if exe is None:
        return None

    try:
        proc = subprocess.run(
            [exe, "fs", "--scanners", "vuln", "--format", "json", "--quiet", str(root)],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=_TRIVY_TIMEOUT,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Trivy no terminó en {_TRIVY_TIMEOUT}s")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Trivy no devolvió JSON válido (exit={proc.returncode}): {proc.stderr[:500]}")

    findings = []
    for result in data.get("Results", []) or []:
        target = result.get("Target", "")
        file_rel = _relpath(root, str(root / target)) if not Path(target).is_absolute() else _relpath(root, target)
        for vuln in result.get("Vulnerabilities", []) or []:
            rule_id = vuln.get("VulnerabilityID", "unknown")
            pkg = vuln.get("PkgName", "?")
            findings.append(
                Finding(
                    id=make_finding_id("trivy", file_rel, 1, f"{rule_id}:{pkg}"),
                    tool="trivy",
                    file=file_rel,
                    line=1,
                    end_line=None,
                    severity=_TRIVY_SEVERITY.get(vuln.get("Severity", ""), "info"),
                    rule_id=rule_id,
                    message=(
                        f"{pkg} {vuln.get('InstalledVersion', '?')}: {vuln.get('Title') or vuln.get('Description', '')}"
                        f" (fix: {vuln.get('FixedVersion', 'sin fix disponible')})"
                    ).strip(),
                    cwe=list(vuln.get("CweIDs", [])),
                )
            )
    return findings
