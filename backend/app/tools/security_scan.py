"""Tools del centinela de seguridad de código (Fase 1 del roadmap de
"profesiones" de Jarvis -- ver la nota de Obsidian "Cómo Jarvis Audita
Seguridad de Código", autor jarvis).

El LLM NO debe intentar encontrar vulnerabilidades por su cuenta leyendo
código a ojo -- demasiado riesgo de falsos negativos para una herramienta que
se presenta como pentesting real. Hay DOS flujos posibles a partir de acá:

  A) Con un humano revisando en el medio (dry-run primero):
     1. `security_scan_project` corre escáneres SAST/SCA reales (Semgrep, Bandit,
        cppcheck, clang-tidy si hay compile_commands.json, Trivy) y devuelve
        hallazgos reales, con su id estable.
     2. `security_get_finding` trae el contexto de código de un hallazgo puntual,
        y de paso notas relevantes del vault de Obsidian (ver más abajo).
     3. Si hay un fix seguro, el LLM lo redacta (old_snippet -> new_snippet) y lo
        aplica con `code_apply_fix` (ver `app/tools/code_edit.py`), que por
        default hace un dry-run (solo devuelve el diff) y recién escribe +
        commitea si se lo llama de nuevo con confirm=true.

  B) Flujo autónomo autorizado (tarea guiada, sin humano confirmando en el
     medio -- ver SYSTEM_PROMPT en app/agent.py para cuándo aplica): mismos
     pasos 1-2, pero el paso 3 usa `security_audit_find_fix_verify` en vez de
     `code_apply_fix` -- aplica, commitea, Y re-escanea para confirmar que el
     hallazgo puntual quedó resuelto, todo en un solo tool call server-side
     (no depende de que el LLM se acuerde de hacer una segunda llamada con
     confirm=true, ni de recordar el finding_id de memoria -- bug real
     2026-08-09: el modelo alucinó un finding_id inexistente, dos veces
     seguidas, y en la corrida completa nunca terminó de confirmar el fix
     porque se quedó esperando que el USUARIO revisara el dry-run).
"""

# Nota: el nombre real de la tool que aplica el fix (con revisión humana en el
# medio) es `code_apply_fix` (ver app/tools/code_edit.py) -- NO
# "security_apply_fix". Hubo un bug real acá donde las descripciones de
# security_scan_project/security_get_finding, que el LLM lee tal cual como
# parte del schema de tools, mencionaban "security_apply_fix" (un nombre que
# nunca se registró), lo que podía llevar al modelo a intentar llamar una tool
# inexistente después de security_get_finding en vez de code_apply_fix.

from __future__ import annotations

from pathlib import Path

from .. import audit_log
from ..codeedit import fixer
from ..obsidian import vault
from ..quality import runner as quality_runner
from ..security import store
from ..security import runner as security_runner
from ..security import triage as security_triage
from ..security.models import Finding
from ..security.runner import scan_project
from ..testing.runner import run_tests
from . import register_tool

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Cuántos caracteres del contenido de una nota de Obsidian se incluyen en el
# resultado de security_get_finding -- suficiente para que el modelo lea la
# guía real (no solo el título), acotado para no repetir el problema de
# contexto que ya causó un bug real (ver MODEL_CONTEXT_TOKENS en config.py):
# 2 notas x ~600 chars c/u es un costo chico comparado con el resto del
# resultado, y de todos modos el resultado entero sigue pasando por
# _cap_tool_result como red de seguridad final.
_OBSIDIAN_NOTE_PREVIEW_CHARS = 600
_OBSIDIAN_NOTES_PER_FINDING = 2


def _cascade_key(f: Finding) -> str:
    """Agrupa hallazgos que probablemente se resuelven con UN SOLO fix --
    para priorizar reparación masiva por efecto cascada en vez de ir
    hallazgo por hallazgo en orden arbitrario (pedido real 2026-08-10).

    Trivy (SCA de dependencias): agrupa por (archivo del manifiesto,
    paquete) -- el mensaje de Trivy siempre arranca con "{paquete} {versión}:
    ..." (ver security/scanners.py::run_trivy), así que el paquete es el
    primer token del mensaje. Varios CVEs del MISMO paquete en el MISMO
    manifiesto suelen resolverse con un solo bump de versión.

    Cualquier otro escáner (hallazgos de patrón de código: Semgrep, Bandit,
    cppcheck, clang-tidy): agrupa por `rule_id` a nivel de PROYECTO entero
    (no por archivo) -- el mismo patrón repetido en varios archivos/líneas
    suele compartir la misma causa raíz y el mismo criterio de fix, aunque
    cada ocurrencia todavía necesite su propio old_snippet/new_snippet
    puntual vía security_audit_find_fix_verify (no hay forma de aplicar un
    fix a "todas las ocurrencias de una regla" en un solo tool call -- cada
    una es una edición mecánica distinta -- pero agruparlas ayuda a priorizar
    cuáles atacar primero y a no reportarlas como problemas sueltos sin
    relación cuando en realidad comparten causa)."""
    if f.tool == "trivy":
        package = f.message.split(" ", 1)[0] if f.message else "?"
        return f"dep:{f.file}:{package}"
    return f"rule:{f.rule_id}"


def _cascade_sizes(findings: list[Finding]) -> dict[str, int]:
    """Tamaño de cada grupo de cascada, calculado sobre TODOS los hallazgos
    del proyecto (no solo el subset que termina en la respuesta) -- así el
    cascade_size que ve el modelo es el real, incluso si ese hallazgo puntual
    queda en una página recortada."""
    sizes: dict[str, int] = {}
    for f in findings:
        key = _cascade_key(f)
        sizes[key] = sizes.get(key, 0) + 1
    return sizes


def _finding_with_cascade(f: Finding, sizes: dict[str, int]) -> dict:
    d = f.to_dict()
    key = _cascade_key(f)
    d["cascade_group"] = key
    d["cascade_size"] = sizes[key]
    return d


@register_tool(
    name="security_scan_project",
    description=(
        "Corre escáneres de seguridad REALES (Semgrep multi-lenguaje, Bandit si hay Python, cppcheck si hay "
        "C/C++, clang-tidy además si el proyecto trae compile_commands.json (análisis semántico más profundo), "
        "Trivy para CVEs de dependencias si está instalado) sobre un proyecto ya indexado con codebase_index_project "
        "(si no está indexado, lo indexa primero). Devuelve hallazgos reales con severidad, archivo, línea, "
        "regla y CWE/OWASP -- NO son inventados por el modelo. Usa cache salvo refresh=true (Semgrep con "
        "--config auto puede tardar). Cada hallazgo tiene un 'id' estable para pasarle a code_apply_fix. El "
        "resumen sin 'file' viene ordenado por severidad y recortado (tanto en cantidad como, más abajo en el "
        "pipeline, en tamaño de mensaje) para no inundar el contexto en proyectos con cientos de hallazgos -- "
        "en un proyecto grande, un hallazgo puntual de severidad media/baja (ej. el que te haya señalado el "
        "usuario por archivo/línea) puede quedar afuera de ese recorte aunque exista de verdad. Si ya sabés en "
        "qué archivo tenés que buscar (porque el usuario te lo dijo, o porque ya viste ese archivo en un "
        "resumen previo), pasá 'file' (ruta relativa a la raíz del proyecto, ej. 'introduction/views.py') para "
        "traer TODOS los hallazgos de ESE archivo puntual sin el recorte del resumen global. Cada hallazgo trae "
        "'cascade_group' y 'cascade_size' -- hallazgos con el mismo 'cascade_group' probablemente se resuelven "
        "con UN SOLO fix (ej. varios CVEs del mismo paquete de dependencia en el mismo manifiesto, resueltos "
        "con un solo bump de versión; o el mismo patrón de código repetido en varios lugares). El orden de "
        "'findings' ya viene priorizado por 'cascade_size' descendente (mayor cascada primero) y severidad como "
        "criterio secundario -- si el usuario pidió una reparación de VARIOS hallazgos, andá en ese orden en vez "
        "de uno arbitrario: los de mayor cascade_size resuelven más terreno por cada fix aplicado."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la carpeta raíz del proyecto a auditar."},
            "refresh": {
                "type": "boolean",
                "description": "Si es true, ignora el cache y vuelve a correr todos los escáneres. Default false.",
            },
            "file": {
                "type": "string",
                "description": (
                    "Opcional: ruta relativa (a 'path') de un archivo puntual. Si se pasa, devuelve TODOS los "
                    "hallazgos de ese archivo (sin el recorte por cantidad/severidad del resumen global) en vez "
                    "del resumen de todo el proyecto."
                ),
            },
        },
        "required": ["path"],
    },
)
def security_scan_project(path: str, refresh: bool = False, file: str | None = None) -> dict:
    result = scan_project(path, refresh=refresh)
    # Hallazgos que security_triage_findings ya reclasificó como falso
    # positivo (ver app/security/triage.py) se excluyen del conteo/detalle
    # real -- mismo criterio que el ruido conocido en audit_report.py, nunca
    # se borran del ScanResult cacheado, solo se excluyen de lo que se
    # reporta como vulnerabilidad real.
    real_findings = [f for f in result.findings if f.triage_status != "false_positive"]
    triaged_false_positives = len(result.findings) - len(real_findings)

    cascade_sizes = _cascade_sizes(real_findings)
    findings_sorted = sorted(
        real_findings,
        key=lambda f: (-cascade_sizes[_cascade_key(f)], _SEVERITY_ORDER.get(f.severity, 9), f.file, f.line),
    )

    by_severity: dict[str, int] = {}
    for f in real_findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    response = {
        "root": result.root,
        "scanned_at": result.scanned_at,
        "tools_run": result.tools_run,
        "tools_skipped": result.tools_skipped,
        "total_findings": len(real_findings),
        "findings_by_severity": by_severity,
    }
    if triaged_false_positives:
        response["triaged_false_positives"] = (
            f"{triaged_false_positives} hallazgo(s) más fueron reclasificados como falso positivo por "
            "security_triage_findings -- no cuentan acá, pero siguen guardados con su razón (llamá de "
            "nuevo a security_triage_findings o mirá el finding puntual con triage_status/triage_reasoning "
            "si querés revisar el criterio)."
        )

    if file is not None:
        # Filtro por archivo puntual -- normaliza separadores (el modelo puede
        # mandar "introduction\\views.py" en Windows) antes de comparar contra
        # Finding.file, que siempre usa "/" (ver security/scanners.py).
        normalized = file.replace("\\", "/").lstrip("/")
        file_findings = [f for f in findings_sorted if f.file == normalized]
        response["file"] = normalized
        response["findings"] = [_finding_with_cascade(f, cascade_sizes) for f in file_findings]
        response["findings_omitted"] = 0
        return response

    # Cap razonable para no inundar el contexto del modelo en repos grandes con
    # muchos hallazgos de baja severidad -- el resumen por severidad de arriba ya
    # da el panorama completo, esto es el detalle accionable de los más urgentes.
    response["findings"] = [_finding_with_cascade(f, cascade_sizes) for f in findings_sorted[:100]]
    response["findings_omitted"] = max(0, len(findings_sorted) - 100)
    return response


def _finding_not_found_error(path: str, file: str | None, rule_id: str | None, line: int | None) -> str:
    """Arma un mensaje de error ACCIONABLE cuando no se pudo resolver un
    hallazgo -- si hay candidatos reales para (file, rule_id), los lista con
    sus líneas en vez del genérico "puede haber más de uno, agregá line".

    Bug real 2026-08-09 (round 2), visto en las 3 corridas del caso B608 en
    pygoat: el mensaje anterior no decía CUÁLES eran las líneas válidas, así
    que el modelo reintentaba adivinando líneas al azar (42, 100, 142...)
    2-3 veces antes de acertar. Mostrando la lista real de entrada, la
    corrección debería salir en el segundo intento como mucho."""
    if file and rule_id:
        lines = store.find_candidate_lines(path, file, rule_id)
        if lines:
            return (
                f"No hay un hallazgo con rule_id='{rule_id}' en '{file}'"
                + (f" en la línea {line}" if line is not None else "")
                + f" -- SÍ hay hallazgos con esa regla en ese archivo en la(s) línea(s): {lines}. "
                "Reintentá con 'line' igual a una de esas."
            )
    return (
        f"No se encontró ese hallazgo en '{path}' -- ¿corriste security_scan_project sobre este proyecto? "
        "Si pasaste 'file'+'rule_id', puede haber más de un hallazgo con esa regla en ese archivo, o ninguno: "
        "corré security_scan_project(file=...) para ver los hallazgos reales de ese archivo."
    )


def _related_obsidian_notes(finding) -> list[dict]:
    """Busca notas del vault relevantes para este hallazgo (patrones de la
    vulnerabilidad, guías de remediación) -- automático, no depende de que el
    LLM se acuerde de llamar obsidian_search_notes por su cuenta (bug real
    2026-08-09: nunca lo llamó en una corrida completa de audit+fix). Nunca
    rompe el resultado del hallazgo si el vault/embeddings fallan -- en el
    peor caso, security_get_finding devuelve sin notas en vez de fallar
    entero por un problema de una capacidad aparte."""
    query = " ".join(filter(None, [finding.rule_id, *finding.cwe, *finding.owasp]))
    if not query:
        return []
    try:
        notes = vault.search_notes(query, limit=_OBSIDIAN_NOTES_PER_FINDING)
    except Exception:
        return []
    results = []
    for note in notes:
        content = note.content
        truncated = len(content) > _OBSIDIAN_NOTE_PREVIEW_CHARS
        results.append(
            {
                "title": note.title,
                "tags": note.tags,
                "content_preview": content[:_OBSIDIAN_NOTE_PREVIEW_CHARS],
                "truncated": truncated,
            }
        )
    return results


@register_tool(
    name="security_get_finding",
    description=(
        "Trae el detalle completo de un hallazgo puntual -- código real alrededor de la línea afectada, MÁS "
        "notas relevantes del vault de Obsidian (patrones de la vulnerabilidad, guías de remediación ya "
        "cargadas) buscadas automáticamente -- usar antes de proponer un fix con code_apply_fix o "
        "security_audit_find_fix_verify, para ver el contexto exacto y no redactar el fix de memoria. "
        "Identificá el hallazgo por 'finding_id' (tal como lo devolvió security_scan_project) O por "
        "'file'+'rule_id' (y 'line' si hay más de un hallazgo con esa regla en ese archivo) -- preferí esta "
        "segunda forma: 'finding_id' es un hash interno fácil de citar mal de memoria entre un tool call y "
        "el siguiente, mientras que file/rule_id/line son texto que ya viste tal cual en el resultado de "
        "security_scan_project."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado)."},
            "finding_id": {"type": "string", "description": "Id del hallazgo, tal como lo devolvió security_scan_project."},
            "file": {"type": "string", "description": "Ruta del archivo (relativa a 'path') -- alternativa a finding_id, junto con rule_id."},
            "rule_id": {"type": "string", "description": "Regla del hallazgo (ej. 'B608') -- junto con 'file', alternativa a finding_id."},
            "line": {"type": "integer", "description": "Línea del hallazgo -- necesario si hay más de uno con la misma regla en el archivo."},
            "context_lines": {"type": "integer", "description": "Líneas de contexto antes/después a incluir (default 5)."},
        },
        "required": ["path"],
    },
)
def security_get_finding(
    path: str,
    finding_id: str | None = None,
    file: str | None = None,
    rule_id: str | None = None,
    line: int | None = None,
    context_lines: int = 5,
) -> dict:
    finding = store.find_finding(path, finding_id=finding_id, file=file, rule_id=rule_id, line=line)
    if finding is None:
        raise ValueError(_finding_not_found_error(path, file, rule_id, line))

    root = Path(path).resolve()
    file_path = root / finding.file
    code_context = None
    if file_path.is_file():
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, finding.line - context_lines)
        end = min(len(lines), (finding.end_line or finding.line) + context_lines)
        code_context = [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]

    return {
        "finding": finding.to_dict(),
        "code_context": code_context,
        "obsidian_notes": _related_obsidian_notes(finding),
    }


def _rescan_targeted(path: str, file: str) -> dict:
    """Re-escanea SOLO `file` (seguridad + calidad) -- mismo criterio que
    `code_edit._rescan_after_fix`, pero vive acá aparte porque
    security_audit_find_fix_verify necesita el detalle CRUDO (no solo el
    mensaje de cascada) para poder decidir si el hallazgo puntual que estaba
    arreglando ya no aparece. Si el rescan falla, no se cae el resultado del
    fix (que ya se aplicó y commiteó) -- solo queda sin info de verificación."""
    try:
        sec = security_runner.rescan_file(path, file)
    except Exception as exc:
        sec = {"resolved": [], "persisting": [], "new": [], "error": str(exc)}
    try:
        qual = quality_runner.rescan_file(path, file)
    except Exception as exc:
        qual = {"resolved": [], "persisting": [], "new": [], "error": str(exc)}
    return {
        "resolved_findings": sec.get("resolved", []) + qual.get("resolved", []),
        "persisting_findings": sec.get("persisting", []) + qual.get("persisting", []),
        "new_findings": sec.get("new", []) + qual.get("new", []),
    }


def _run_tests_after_fix(path: str) -> dict:
    """Paso de 'testear real' (ver `app/testing/runner.py`), agregado
    2026-08-10 tras el informe de estado que identificó esto como el gap
    principal del pipeline: `security_audit_find_fix_verify` ya aplicaba,
    commiteaba y re-escaneaba en un solo paso atómico, pero re-escanear con
    Semgrep/Bandit/etc. solo confirma que un PATRÓN de código ya no aparece --
    nunca confirma que el proyecto sigue funcionando. Se corre siempre que el
    fix se aplicó de verdad, sin que el LLM tenga que acordarse de llamar
    code_run_tests aparte (mismo criterio que llevó a este mismo tool a existir
    en primer lugar: no depender de que el modelo se acuerde de un segundo paso).

    Si el rescan/detección de tests falla por algún motivo ajeno (proyecto sin
    suite, timeout, etc.), no tira abajo el resultado del fix -- que ya se
    aplicó y commiteó -- solo queda sin verificación funcional, marcado como
    tal en el resultado."""
    try:
        result = run_tests(path)
        return result.to_dict()
    except Exception as exc:
        return {"detected": False, "passed": False, "error": str(exc)}


@register_tool(
    name="security_audit_find_fix_verify",
    description=(
        "Aplica, COMMITEA, y VERIFICA un fix para un hallazgo de seguridad puntual en un solo paso atómico -- "
        "a diferencia de code_apply_fix (dry-run por default, necesita una segunda llamada con confirm=true "
        "para escribir de verdad), esta tool escribe y commitea directo, sin paso intermedio, y después "
        "re-escanea el archivo para confirmar si el hallazgo puntual quedó resuelto, Y corre la suite de tests "
        "REAL del proyecto (ver code_run_tests) para confirmar que el fix no rompió nada -- el resultado trae "
        "'tests' con 'detected' (si se encontró un comando de test real), 'passed' y 'exit_code'. Un fix con "
        "'finding_resolved': true pero 'tests': {'detected': true, 'passed': false} significa que el patrón de "
        "código ya no aparece PERO algo se rompió -- reportale eso al usuario explícitamente, no lo des por "
        "resuelto. Si 'tests': {'detected': false}, no hay ninguna suite real en el proyecto para verificar con "
        "-- decilo así, no lo confundas con que los tests fallaron. Usar SOLO cuando el "
        "usuario pidió explícitamente auditar Y reparar (no solo reportar) -- ver SYSTEM_PROMPT para cuándo "
        "este flujo autónomo está autorizado. Identificá el hallazgo por 'file'+'rule_id' (y 'line' si hace "
        "falta desambiguar), tal como aparecen en security_scan_project/security_get_finding -- no hace falta "
        "el finding_id exacto. old_snippet/new_snippet siguen siendo tu responsabilidad (mismo criterio que "
        "code_apply_fix: old_snippet debe matchear EXACTAMENTE una vez en el archivo). El resultado incluye "
        "'finding_resolved' (bool) -- reportale eso al usuario como confirmación real, no asumas que el fix "
        "funcionó solo porque el commit se hizo. "
        "Si el USUARIO pidió arreglar un hallazgo ESPECÍFICO (nombrando su regla, ej. 'el B608'), pasá SIEMPRE "
        "'requested_rule_id' (y 'requested_file' si lo dijo) con eso -- constante en todas tus llamadas de este "
        "pedido, aunque el hallazgo que termines aplicando sea otro. Si 'rule_id'/'file' de esta llamada no "
        "coinciden con lo pedido, la tool RECHAZA aplicar el fix (sin escribir nada) a menos que también mandes "
        "'confirm_target_change=true' -- eso es a propósito: no sustituyas el hallazgo pedido por otro más fácil "
        "en silencio (bug real 2026-08-09: pasó tres veces seguidas). Si de verdad no podés resolver el pedido "
        "original (ambiguo, no existe, etc.), decíselo al usuario en tu respuesta ANTES de aplicar un fix "
        "distinto, no lo reemplaces sin avisar."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto."},
            "file": {"type": "string", "description": "Ruta del archivo relativa a la raíz del proyecto."},
            "rule_id": {"type": "string", "description": "Regla del hallazgo a resolver (ej. 'B608'), tal como aparece en el scan."},
            "line": {"type": "integer", "description": "Línea del hallazgo, si hay más de uno con la misma regla en el archivo."},
            "old_snippet": {"type": "string", "description": "Texto exacto a reemplazar (debe aparecer una única vez en el archivo)."},
            "new_snippet": {"type": "string", "description": "Texto de reemplazo."},
            "commit_message": {"type": "string", "description": "Mensaje de commit."},
            "requested_rule_id": {
                "type": "string",
                "description": (
                    "Regla que el USUARIO pidió arreglar originalmente en este pedido (si nombró una específica) "
                    "-- constante en todas las llamadas de este pedido, se compara contra 'rule_id' para detectar "
                    "si te desviaste a otro hallazgo distinto sin avisar."
                ),
            },
            "requested_file": {
                "type": "string",
                "description": "Archivo que el usuario pidió originalmente (si lo dijo) -- mismo criterio que requested_rule_id.",
            },
            "confirm_target_change": {
                "type": "boolean",
                "description": (
                    "Poné true SOLO si 'rule_id'/'file' difieren a propósito de 'requested_rule_id'/"
                    "'requested_file' Y ya le explicaste al usuario por qué en tu respuesta. Default false."
                ),
            },
        },
        "required": ["path", "file", "rule_id", "old_snippet", "new_snippet", "commit_message"],
    },
)
def security_audit_find_fix_verify(
    path: str,
    file: str,
    rule_id: str,
    old_snippet: str,
    new_snippet: str,
    commit_message: str,
    line: int | None = None,
    requested_rule_id: str | None = None,
    requested_file: str | None = None,
    confirm_target_change: bool = False,
) -> dict:
    if requested_rule_id and not confirm_target_change:
        target_changed = requested_rule_id != rule_id or (requested_file is not None and requested_file != file)
        if target_changed:
            raise ValueError(
                f"Ibas a aplicar el fix sobre rule_id='{rule_id}' en '{file}', pero el usuario había pedido "
                f"'{requested_rule_id}'" + (f" en '{requested_file}'" if requested_file else "") + ". Si es a "
                "propósito (el pedido original no se pudo resolver y elegiste otro hallazgo real en su lugar), "
                "primero contáselo al usuario en tu respuesta y volvé a llamar esta tool con "
                "confirm_target_change=true. Si no fue a propósito, volvé a intentar con el rule_id/file "
                "originales -- usá security_get_finding(file=..., rule_id=...) para ubicarlo bien, ahora te da "
                "las líneas reales disponibles si la que probaste no matcheó."
            )

    target = store.find_finding(path, file=file, rule_id=rule_id, line=line)
    if target is None:
        raise ValueError(_finding_not_found_error(path, file, rule_id, line))

    arguments = {"path": path, "file": file, "rule_id": rule_id, "line": line, "commit_message": commit_message}
    try:
        apply_result = fixer.apply_fix(
            root=path,
            file=file,
            old_snippet=old_snippet,
            new_snippet=new_snippet,
            commit_message=commit_message,
            confirm=True,
        )
    except Exception as exc:
        audit_log.log_tool_call(target="code", tool="security_audit_find_fix_verify", arguments=arguments, error=str(exc))
        raise

    result: dict = {**apply_result, "targeted_finding": target.to_dict()}

    if apply_result.get("applied"):
        rescan = _rescan_targeted(path, file)
        resolved_ids = {f["id"] for f in rescan["resolved_findings"]}
        result.update(rescan)
        result["finding_resolved"] = target.id in resolved_ids
        result["tests"] = _run_tests_after_fix(path)

    audit_log.log_tool_call(target="code", tool="security_audit_find_fix_verify", arguments=arguments, result=result)
    return result


@register_tool(
    name="security_triage_findings",
    description=(
        "Revisa con criterio (el LLM, mirando el código real alrededor de cada hallazgo) los hallazgos ya "
        "escaneados de un proyecto (security_scan_project), y reclasifica los que sean falso positivo genuino -- "
        "Semgrep y el resto de los escáneres hacen pattern-matching, no siguen flujo de datos real: pueden marcar "
        "código que ya está sanitizado/validado/parametrizado de una forma que el patrón no reconoce (ej. "
        "PreparedStatement con parámetros bindeados en vez de concatenación, un ORM que ya escapa el input, una "
        "validación previa fuera de la línea marcada). Cada hallazgo revisado queda marcado con 'triage_status' "
        "('real' o 'false_positive') y 'triage_reasoning' (la razón concreta, nunca un descarte silencioso) -- los "
        "marcados como falso positivo dejan de contar en security_scan_project/audit_generate_report, pero NUNCA "
        "se borran del historial, siguen ahí si hace falta revisar el criterio. Corre una llamada al modelo por "
        "hallazgo -- en un proyecto con muchos hallazgos puede tardar; usar 'limit' para acotar a los N más "
        "urgentes primero si hace falta. No re-triagea hallazgos que ya tienen triage_status salvo que se pida "
        "force=true."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado con security_scan_project)."},
            "limit": {"type": "integer", "description": "Máximo de hallazgos a triagear en esta llamada (default: todos los pendientes)."},
            "force": {"type": "boolean", "description": "Si es true, re-triagea también los que ya tienen triage_status. Default false."},
        },
        "required": ["path"],
    },
)
async def security_triage_findings(path: str, limit: int | None = None, force: bool = False) -> dict:
    root = Path(path).resolve()
    result = store.load_scan(root)
    if result is None:
        raise ValueError(
            f"No hay un escaneo guardado para '{path}' -- corré security_scan_project primero."
        )

    pending = [f for f in result.findings if force or f.triage_status is None]
    if limit is not None:
        pending = pending[: int(limit)]

    triaged = await security_triage.triage_findings(root, pending)
    triaged_by_id = {f.id: f for f in triaged}
    new_findings = [triaged_by_id.get(f.id, f) for f in result.findings]
    result.findings = new_findings
    store.save_scan(result)

    real_count = sum(1 for f in triaged if f.triage_status == "real")
    false_positive_count = sum(1 for f in triaged if f.triage_status == "false_positive")
    result_summary = {
        "project": str(root),
        "triaged_now": len(triaged),
        "reclassified_as_real": real_count,
        "reclassified_as_false_positive": false_positive_count,
        "still_pending": sum(1 for f in new_findings if f.triage_status is None),
        "false_positives": [
            {"file": f.file, "line": f.line, "rule_id": f.rule_id, "reasoning": f.triage_reasoning}
            for f in triaged
            if f.triage_status == "false_positive"
        ],
    }
    audit_log.log_tool_call(
        target="code", tool="security_triage_findings",
        arguments={"path": path, "limit": limit, "force": force}, result=result_summary,
    )
    return result_summary
