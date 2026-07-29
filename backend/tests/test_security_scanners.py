"""Tests de integración reales contra los binarios de Bandit/Semgrep -- sin
mockear el escáner en sí, para confirmar que efectivamente detectan una
vulnerabilidad de verdad (no solo que el código Python que la envuelve
funciona). Requieren que `pip install -r requirements.txt` haya corrido."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.security import scanners

_KNOWN_SQLI_SOURCE = (
    "import sqlite3\n"
    "\n"
    "def get_user(username):\n"
    "    conn = sqlite3.connect('db.sqlite3')\n"
    "    cursor = conn.cursor()\n"
    "    query = \"SELECT * FROM users WHERE username = '\" + username + \"'\"\n"
    "    cursor.execute(query)\n"
    "    return cursor.fetchone()\n"
)


@pytest.fixture
def vulnerable_project(tmp_path) -> Path:
    root = tmp_path / "vuln_proj"
    root.mkdir()
    (root / "vuln.py").write_text(_KNOWN_SQLI_SOURCE, encoding="utf-8")
    return root


def test_run_bandit_detects_real_sql_injection(vulnerable_project):
    """Bandit real (no mockeado), offline y rápido -- el escáner tiene que
    encontrar el B608 (hardcoded_sql_expressions) en la línea de concatenación."""
    if scanners._tool_path("bandit") is None:
        pytest.skip("bandit no está instalado en este entorno")

    findings = scanners.run_bandit(vulnerable_project, python_files=["vuln.py"])

    assert findings is not None
    assert len(findings) >= 1
    sqli = next((f for f in findings if f.rule_id == "B608"), None)
    assert sqli is not None
    assert sqli.tool == "bandit"
    assert sqli.file == "vuln.py"
    assert sqli.line == 6
    assert sqli.severity in ("low", "medium", "high")
    assert "SQL" in sqli.message or "sql" in sqli.message.lower()


def test_run_bandit_detects_finding_split_across_multiple_batches(tmp_path, monkeypatch):
    """Reproduce el bug real (WinError 206 sobre SuperSaaSFastAPI, 743 archivos
    .py) con un repo de test chico: fuerza un `max_chars` diminuto para que
    `chunk_paths` divida los archivos en varios lotes, y confirma que Bandit
    sigue encontrando el hallazgo real esté en el lote que esté, sin
    duplicarlo ni perderlo."""
    if scanners._tool_path("bandit") is None:
        pytest.skip("bandit no está instalado en este entorno")

    root = tmp_path / "multi_file_proj"
    root.mkdir()
    (root / "vuln.py").write_text(_KNOWN_SQLI_SOURCE, encoding="utf-8")
    clean_files = []
    for i in range(5):
        name = f"clean_{i}.py"
        (root / name).write_text("def noop():\n    return 1\n", encoding="utf-8")
        clean_files.append(name)

    # Fuerza ~1 archivo por lote (cada ruta absoluta acá mide bastante más
    # que 30 caracteres) sin tocar el default real de producción.
    from app.findings.binaries import chunk_paths as _real_chunk_paths

    monkeypatch.setattr(scanners, "_chunk_paths", lambda paths: _real_chunk_paths(paths, max_chars=30))

    findings = scanners.run_bandit(root, python_files=["vuln.py", *clean_files])

    assert findings is not None
    sqli_matches = [f for f in findings if f.rule_id == "B608"]
    assert len(sqli_matches) == 1  # ni perdido ni duplicado por el batching


def test_run_bandit_returns_none_without_python_files(tmp_path):
    assert scanners.run_bandit(tmp_path, python_files=[]) is None


def test_run_bandit_returns_none_when_binary_missing(vulnerable_project, monkeypatch):
    monkeypatch.setattr(scanners, "_tool_path", lambda name: None)
    assert scanners.run_bandit(vulnerable_project, python_files=["vuln.py"]) is None


@pytest.mark.timeout(120)
def test_run_semgrep_detects_real_sql_injection(vulnerable_project):
    """Semgrep real con --config auto -- pega al registro público de reglas, por
    eso el timeout más largo y el skip si no hay binario/red. Confirma el mismo
    hallazgo real que Bandit mediante una herramienta y un motor totalmente
    distintos."""
    if scanners._tool_path("semgrep") is None:
        pytest.skip("semgrep no está instalado en este entorno")

    try:
        findings = scanners.run_semgrep(vulnerable_project)
    except (TimeoutError, RuntimeError) as exc:
        pytest.skip(f"semgrep no pudo correr (¿sin red?): {exc}")

    assert findings is not None
    assert any("sql" in f.message.lower() or "injection" in f.message.lower() for f in findings)


def test_run_trivy_returns_none_when_binary_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners, "_tool_path", lambda name: None)
    assert scanners.run_trivy(tmp_path) is None


@pytest.mark.parametrize("scanner_fn, tool_name, extra_args", [
    (scanners.run_semgrep, "semgrep", ()),
    (scanners.run_trivy, "trivy", ()),
])
def test_scanner_subprocess_calls_decode_as_utf8_not_locale_default(tmp_path, monkeypatch, scanner_fn, tool_name, extra_args):
    """Reproduce el bug real (auditando saas-boilerplate el 2026-07-29): sin
    `encoding="utf-8"` explícito, `subprocess.run(..., text=True)` decodifica
    con el codec del sistema (cp1252 en Windows en español) -- un CVE con un
    caracter no representable en cp1252 en la descripción (byte 0x9d real,
    Trivy) tira `UnicodeDecodeError` dentro del hilo lector de subprocess y
    deja `proc.stdout` en `None`, crasheando el escaneo entero. Confirma que
    la llamada real pasa `encoding='utf-8'` y `errors='replace'` -- no alcanza
    con `text=True` solo."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(stdout='{"results": []}' if tool_name == "semgrep" else '{"Results": []}', stderr="", returncode=0)

    monkeypatch.setattr(scanners, "_tool_path", lambda name: tool_name)
    monkeypatch.setattr(scanners.subprocess, "run", fake_run)

    scanner_fn(tmp_path, *extra_args) if extra_args else scanner_fn(tmp_path)

    assert captured.get("encoding") == "utf-8"
    assert captured.get("errors") == "replace"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("CWE-352: Cross-Site Request Forgery (CSRF)", ["CWE-352: Cross-Site Request Forgery (CSRF)"]),
        (["CWE-352: Cross-Site Request Forgery (CSRF)"], ["CWE-352: Cross-Site Request Forgery (CSRF)"]),
        ([], []),
        (None, []),
        ("", []),
    ],
)
def test_as_tag_list_normalizes_string_and_list(value, expected):
    assert scanners._as_tag_list(value) == expected


_KNOWN_USE_AFTER_FREE_SOURCE = (
    "#include <stdlib.h>\n"
    "\n"
    "int main(void) {\n"
    "    int *p = malloc(sizeof(int));\n"
    "    free(p);\n"
    "    *p = 42;\n"
    "    return 0;\n"
    "}\n"
)

_FAKE_CPPCHECK_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<results version="2">\n'
    '    <cppcheck version="2.17.1"/>\n'
    "    <errors>\n"
    '        <error id="deallocuse" severity="error" msg="Dereferencing \'p\' after it is deallocated" '
    'verbose="Dereferencing \'p\' after it is deallocated" cwe="416">\n'
    '            <location file="{file}" line="6" column="6"/>\n'
    "        </error>\n"
    "    </errors>\n"
    "</results>\n"
)


def test_run_cppcheck_detects_real_use_after_free(tmp_path):
    """cppcheck real (no mockeado) -- confirma que el binario del paquete pip
    `cppcheck` (ver requirements.txt) efectivamente detecta un use-after-free
    real, no solo que el wrapper de Python arma bien la línea de comando."""
    if scanners._tool_path("cppcheck") is None:
        pytest.skip("cppcheck no está instalado en este entorno")

    root = tmp_path / "cpp_proj"
    root.mkdir()
    (root / "vuln.c").write_text(_KNOWN_USE_AFTER_FREE_SOURCE, encoding="utf-8")

    findings = scanners.run_cppcheck(root, cpp_files=["vuln.c"])

    assert findings is not None
    uaf = next((f for f in findings if f.rule_id == "deallocuse"), None)
    assert uaf is not None
    assert uaf.tool == "cppcheck"
    assert uaf.file == "vuln.c"
    assert uaf.line == 6
    assert uaf.severity == "high"
    assert uaf.cwe == ["CWE-416"]


def test_run_cppcheck_returns_none_without_cpp_files(tmp_path):
    assert scanners.run_cppcheck(tmp_path, cpp_files=[]) is None


def test_run_cppcheck_returns_none_when_binary_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners, "_tool_path", lambda name: None)
    assert scanners.run_cppcheck(tmp_path, cpp_files=["vuln.c"]) is None


def test_run_cppcheck_parses_xml_from_stderr_not_stdout(tmp_path, monkeypatch):
    """Reproduce una particularidad real de cppcheck: el reporte `--xml` sale
    por stderr, no por stdout (stdout solo lleva el progreso "Checking X...").
    Si el wrapper leyera `proc.stdout` en vez de `proc.stderr` (como hacen
    Semgrep/Bandit/Trivy), no encontraría nunca ningún hallazgo."""
    (tmp_path / "vuln.c").write_text(_KNOWN_USE_AFTER_FREE_SOURCE, encoding="utf-8")
    file_uri = (tmp_path / "vuln.c").as_posix()

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(
            stdout="Checking vuln.c ...\n",
            stderr=_FAKE_CPPCHECK_XML.format(file=file_uri),
            returncode=0,
        )

    monkeypatch.setattr(scanners, "_tool_path", lambda name: "cppcheck")
    monkeypatch.setattr(scanners.subprocess, "run", fake_run)

    findings = scanners.run_cppcheck(tmp_path, cpp_files=["vuln.c"])

    assert findings is not None
    assert len(findings) == 1
    assert findings[0].rule_id == "deallocuse"
    assert findings[0].severity == "high"
    assert findings[0].cwe == ["CWE-416"]


@pytest.mark.parametrize(
    "cpp_files, expect_forced_cpp",
    [
        (["src/main.cpp", "include/foo.h"], True),
        (["include/foo.hpp"], True),
        (["src/main.c", "include/foo.h"], False),
    ],
)
def test_run_cppcheck_forces_cpp_language_for_mixed_projects(tmp_path, monkeypatch, cpp_files, expect_forced_cpp):
    """Reproduce el bug real encontrado auditando Luanti el 2026-07-29: sin
    `--language=c++`, cppcheck parsea `.h` como C puro (mismo criterio por
    extensión que `languages.py`) y un header C++ real con `namespace`/`class`
    dispara `syntaxError` en cascada -- 351 falsos "high" sobre el propio
    Luanti antes de este fix. Si el proyecto tiene algún archivo fuente C++
    inequívoco (.cpp/.cc/.cxx/.hpp/.hh), se asume que los .h del mismo proyecto
    también son C++ y se fuerza el modo; en un proyecto puro de C (solo .c/.h)
    se deja el auto-detect de cppcheck tal cual."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout="", stderr='<?xml version="1.0"?><results version="2"><errors/></results>', returncode=0)

    monkeypatch.setattr(scanners, "_tool_path", lambda name: "cppcheck")
    monkeypatch.setattr(scanners.subprocess, "run", fake_run)

    scanners.run_cppcheck(tmp_path, cpp_files=cpp_files)

    assert ("--language=c++" in captured["cmd"]) == expect_forced_cpp


def test_run_cppcheck_raises_on_invalid_xml(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners, "_tool_path", lambda name: "cppcheck")
    monkeypatch.setattr(
        scanners.subprocess, "run",
        lambda *a, **k: SimpleNamespace(stdout="", stderr="not xml at all", returncode=1),
    )

    with pytest.raises(RuntimeError):
        scanners.run_cppcheck(tmp_path, cpp_files=["vuln.c"])


def test_run_semgrep_normalizes_string_cwe_and_owasp(tmp_path, monkeypatch):
    """Reproduce el bug real encontrado auditando repos externos (PyGoat/NodeGoat):
    algunas reglas de Semgrep (ej. 'django-no-csrf-token') devuelven `cwe`/`owasp`
    como un string plano en vez de lista -- antes del fix, `list(metadata["cwe"])`
    explotaba ese string caracter por caracter en vez de tratarlo como un tag único."""
    fake_semgrep_output = {
        "results": [
            {
                "check_id": "python.django.security.django-no-csrf-token.django-no-csrf-token",
                "path": str(tmp_path / "template.html"),
                "start": {"line": 10},
                "end": {"line": 12},
                "extra": {
                    "severity": "WARNING",
                    "message": "Manually-created forms in django templates should specify a csrf_token",
                    "metadata": {
                        "cwe": "CWE-352: Cross-Site Request Forgery (CSRF)",
                        "owasp": "A01:2021 - Broken Access Control",
                    },
                },
            }
        ]
    }

    monkeypatch.setattr(scanners, "_tool_path", lambda name: "semgrep")
    monkeypatch.setattr(
        scanners.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout=json.dumps(fake_semgrep_output), stderr="", returncode=0),
    )

    findings = scanners.run_semgrep(tmp_path)

    assert findings is not None
    assert len(findings) == 1
    assert findings[0].cwe == ["CWE-352: Cross-Site Request Forgery (CSRF)"]
    assert findings[0].owasp == ["A01:2021 - Broken Access Control"]


# --- clang-tidy ---------------------------------------------------------
#
# A diferencia de cppcheck (que trae headers sintéticos propios), clang-tidy
# ES el compilador real de Clang -- sin compile_commands.json real no puede
# parsear ni un `#include <stdlib.h>` (confirmado real el 2026-07-30, en esta
# máquina sin ningún toolchain C/C++ instalado). El test de integración de
# abajo por eso usa un archivo SIN ningún include externo (compila con el
# clang-tidy real, sin depender de un compilador de sistema) -- justo lo
# suficiente para probar que el wrapper funciona end-to-end de verdad, no solo
# con output mockeado.

_BARE_USE_AFTER_FREE_CPP = (
    "int use_after_free() {\n"
    "    int *p = new int(42);\n"
    "    delete p;\n"
    "    return *p;\n"
    "}\n"
)


def _write_compile_commands(root: Path, filename: str) -> None:
    import json as _json

    (root / "compile_commands.json").write_text(
        _json.dumps([
            {
                "directory": str(root),
                "command": f"clang++ -std=c++17 -c {filename}",
                "file": filename,
            }
        ]),
        encoding="utf-8",
    )


def test_run_clang_tidy_detects_real_use_after_free_with_real_compile_commands(tmp_path):
    """clang-tidy real (no mockeado), con un `compile_commands.json` real --
    confirma que el binario del paquete pip `clang-tidy` (ver requirements.txt)
    efectivamente hace el análisis semántico profundo (`clang-analyzer-*`,
    dataflow real) que cppcheck no hace, no solo que el wrapper arma bien la
    línea de comando."""
    if scanners._tool_path("clang-tidy") is None:
        pytest.skip("clang-tidy no está instalado en este entorno")

    (tmp_path / "vuln.cpp").write_text(_BARE_USE_AFTER_FREE_CPP, encoding="utf-8")
    _write_compile_commands(tmp_path, "vuln.cpp")

    findings = scanners.run_clang_tidy(tmp_path, cpp_files=["vuln.cpp"], compile_commands_dir=tmp_path)

    assert findings is not None
    uaf = next((f for f in findings if f.rule_id == "clang-analyzer-cplusplus.NewDelete"), None)
    assert uaf is not None
    assert uaf.tool == "clang-tidy"
    assert uaf.file == "vuln.cpp"
    assert uaf.line == 4
    assert uaf.severity == "high"  # clang-analyzer-* -- ver _CLANG_TIDY_HIGH_PREFIXES


def test_run_clang_tidy_returns_none_without_cpp_files(tmp_path):
    assert scanners.run_clang_tidy(tmp_path, cpp_files=[], compile_commands_dir=tmp_path) is None


def test_run_clang_tidy_returns_none_without_compile_commands_dir(tmp_path):
    """El gateo más importante de este wrapper: NUNCA debe correr sin una
    compilation database real -- ver el docstring de `run_clang_tidy` sobre
    por qué eso sería puro ruido (100% de los archivos reales fallando por
    header no encontrado), no un hallazgo real."""
    assert scanners.run_clang_tidy(tmp_path, cpp_files=["vuln.cpp"], compile_commands_dir=None) is None


def test_run_clang_tidy_returns_none_when_binary_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners, "_tool_path", lambda name: None)
    assert scanners.run_clang_tidy(tmp_path, cpp_files=["vuln.cpp"], compile_commands_dir=tmp_path) is None


def test_run_clang_tidy_parses_text_output_and_ignores_note_lines(tmp_path, monkeypatch):
    """clang-tidy no tiene un formato JSON/XML estable para esto -- reporta en
    texto plano por stdout (mismo criterio de parseo por regex que mypy/tsc en
    quality/scanners.py). Las líneas `note:` (contexto del path del analyzer)
    tienen que ignorarse -- no son hallazgos nuevos, son parte del diagnóstico
    `warning:`/`error:` que las precede."""
    fake_stdout = (
        "C:\\proj\\vuln.cpp:4:12: warning: Use of memory after it is released "
        "[clang-analyzer-cplusplus.NewDelete]\n"
        "    4 |     return *p;\n"
        "      |            ^~\n"
        "C:\\proj\\vuln.cpp:2:14: note: Memory is allocated\n"
        "    2 |     int *p = new int(42);\n"
        "      |              ^~~~~~~~~~~\n"
        "C:\\proj\\vuln.cpp:3:5: note: Memory is released\n"
    )

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(stdout=fake_stdout, stderr="", returncode=0)

    monkeypatch.setattr(scanners, "_tool_path", lambda name: "clang-tidy")
    monkeypatch.setattr(scanners.subprocess, "run", fake_run)
    (tmp_path / "vuln.cpp").write_text(_BARE_USE_AFTER_FREE_CPP, encoding="utf-8")

    findings = scanners.run_clang_tidy(tmp_path, cpp_files=["vuln.cpp"], compile_commands_dir=tmp_path)

    assert findings is not None
    assert len(findings) == 1  # las 3 líneas `note:` no cuentan como hallazgos
    assert findings[0].rule_id == "clang-analyzer-cplusplus.NewDelete"
    assert findings[0].line == 4


@pytest.mark.parametrize(
    "check, expected_severity",
    [
        ("clang-analyzer-cplusplus.NewDelete", "high"),
        ("clang-analyzer-security.insecureAPI.strcpy", "high"),
        ("bugprone-use-after-move", "medium"),
        ("cert-err34-c", "medium"),
        ("misc-unused-parameters", "low"),
    ],
)
def test_run_clang_tidy_severity_by_check_prefix(tmp_path, monkeypatch, check, expected_severity):
    def fake_run(cmd, **kwargs):
        stdout = f"C:\\proj\\vuln.cpp:1:1: warning: msg [{check}]\n"
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)

    monkeypatch.setattr(scanners, "_tool_path", lambda name: "clang-tidy")
    monkeypatch.setattr(scanners.subprocess, "run", fake_run)
    (tmp_path / "vuln.cpp").write_text(_BARE_USE_AFTER_FREE_CPP, encoding="utf-8")

    findings = scanners.run_clang_tidy(tmp_path, cpp_files=["vuln.cpp"], compile_commands_dir=tmp_path)

    assert findings is not None
    assert findings[0].severity == expected_severity


def test_find_compile_commands_dir_prefers_project_root(tmp_path):
    (tmp_path / "compile_commands.json").write_text("[]", encoding="utf-8")
    assert scanners.find_compile_commands_dir(tmp_path) == tmp_path


def test_find_compile_commands_dir_falls_back_to_build_subdir(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "compile_commands.json").write_text("[]", encoding="utf-8")
    assert scanners.find_compile_commands_dir(tmp_path) == build_dir


def test_find_compile_commands_dir_returns_none_when_absent(tmp_path):
    assert scanners.find_compile_commands_dir(tmp_path) is None
