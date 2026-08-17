"""Triage con LLM de hallazgos crudos de Semgrep/Bandit/etc.

Contexto real (ver `docs/owasp_benchmark/`): corriendo `security_scan_project`
contra el corpus completo de OWASP Benchmark (2740 casos), la tasa de falso
positivo promedio fue **44.1%** -- sobre todo en categorías que dependen de
seguir el flujo del dato (SQL injection 73%, command injection 87%, LDAP
injection 87.5%). La causa no es un bug de Jarvis: Semgrep (y los otros
escáneres del pipeline) son motores de PATTERN-MATCHING, no siguen flujo de
datos real -- no reconocen que un input ya pasó por un ORM que lo escapa, una
validación previa fuera de la línea marcada, o un `PreparedStatement` con
parámetros bindeados en vez de concatenación.

Este módulo agrega el paso que Semgrep no puede dar: el LLM mira el CÓDIGO
REAL alrededor de cada hallazgo (no solo el mensaje del escáner) y decide si
es una vulnerabilidad real o un falso positivo genuino. Nunca inventa un
hallazgo nuevo, solo reclasifica uno que un escáner real ya generó -- y la
reclasificación queda siempre marcada y con su razón (`Finding.triage_status`/
`triage_reasoning`), nunca un descarte silencioso.

Validación empírica de si esto realmente baja el falso positivo (y en
cuánto le cuesta al recall): ver `docs/owasp_benchmark/triage_validation.md`,
re-corriendo el mismo benchmark con este módulo antes/después."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from ..findings.models import Finding
from ..llm_client import client
from . import triage_reference
from .rule_categories import category_for_rule

logger = logging.getLogger("jarvis.security.triage")

# Líneas de contexto antes/después de la línea marcada -- suficiente para ver
# sanitización/validación cercana (mismo default que security_get_finding,
# ver app/tools/security_scan.py) sin inflar el prompt con el archivo entero.
_CONTEXT_LINES = 8

# La respuesta esperada es un JSON chico (verdict + una oración) -- un tope
# bajo mantiene cada llamada rápida y barata, mismo criterio que
# `reserved_response_tokens` en agent.py pero mucho más chico porque acá no
# hace falta generar una respuesta larga, solo un veredicto.
_MAX_OUTPUT_TOKENS = 200

_SYSTEM_PROMPT = (
    "Sos un revisor experto de hallazgos de seguridad. Un escaner de patrones "
    "(Semgrep u otro) marco un hallazgo en codigo real -- tu trabajo es decidir "
    "si es una vulnerabilidad REAL o un FALSO POSITIVO, mirando el codigo real "
    "alrededor de la linea marcada (viene con '>>' al lado de esa linea).\n\n"
    "El escaner hace pattern-matching, NO sigue flujo de datos real: puede "
    "marcar codigo que en realidad ya esta sanitizado, validado o "
    "parametrizado de una forma que el patron no reconoce -- por ejemplo: "
    "un PreparedStatement con parametros bindeados (?) en vez de "
    "concatenacion de strings, un ORM que ya escapa el input automaticamente, "
    "una validacion/sanitizacion aplicada antes de la linea marcada (aunque "
    "este fuera de la ventana de codigo que ves), o un dato que en realidad "
    "nunca viene de una fuente no confiable (no del usuario).\n\n"
    "IMPORTANTE -- criterio ÚNICO valido para 'false_positive': tiene que "
    "haber un MECANISMO TECNICO CONCRETO en el codigo que de verdad neutraliza "
    "la vulnerabilidad (una sanitizacion, un escape, una validacion, una "
    "parametrizacion real que VES en el codigo). NUNCA marques 'false_positive' "
    "por el nombre del archivo, el nombre de la clase/paquete, comentarios, o "
    "porque el codigo 'parece' de prueba, demo, ejemplo o material educativo -- "
    "eso no dice nada sobre si el patron es explotable. Juzgá el codigo como si "
    "fuera a correr en producción con datos reales de un usuario, sin importar "
    "de dónde parezca venir el archivo. Un algoritmo débil (ej. DES, MD5, "
    "SHA1, java.util.Random para algo sensible) usado sin ningún mecanismo que "
    "lo mitigue es SIEMPRE 'real', nunca 'false_positive', sin importar el "
    "contexto aparente.\n\n"
    "Respondé SIEMPRE con un único objeto JSON, nada mas alrededor:\n"
    '{"verdict": "real", "reasoning": "una oracion corta"} '
    'o {"verdict": "false_positive", "reasoning": "una oracion corta explicando que sanitizacion/validacion ves"}\n\n'
    "Ante la duda, respondé 'real' -- es preferible un falso positivo "
    "reportado de mas que una vulnerabilidad real descartada por error."
)


@dataclass
class TriageVerdict:
    verdict: str  # "real" | "false_positive"
    reasoning: str
    raw_response: str = ""


def _code_context(root: Path, finding: Finding, context_lines: int = _CONTEXT_LINES) -> str:
    file_path = root / finding.file
    if not file_path.is_file():
        return "(no se pudo leer el archivo -- puede haberse movido/borrado desde el escaneo)"
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, finding.line - context_lines)
    end = min(len(lines), (finding.end_line or finding.line) + context_lines)
    numbered = []
    for i in range(start, end + 1):
        marker = ">>" if i == finding.line else "  "
        numbered.append(f"{marker} {i}: {lines[i - 1]}")
    return "\n".join(numbered)


def _build_user_prompt(finding: Finding, code_context: str, reference: str | None = None) -> str:
    prompt = (
        f"Regla del escaner: {finding.rule_id}\n"
        f"Mensaje del escaner: {finding.message}\n"
        f"Archivo: {finding.file}, linea {finding.line}\n\n"
        f"Codigo real (linea marcada con '>>'):\n{code_context}"
    )
    if reference:
        # Referencia curada por categoría (lookup determinístico por rule_id
        # -> categoría, ver rule_categories.py + triage_reference.py) -- NO
        # búsqueda semántica. Bug real 2026-08-11: sin esto, el modelo daba
        # por resuelta una categoría (ej. trust boundary) con la mitigación
        # de OTRA (ej. escape de HTML, que mitiga XSS) -- ver el docstring
        # de triage_reference.py para el caso concreto que motivó esto.
        prompt += (
            "\n\n--- Referencia curada para ESTA categoría puntual -- seguila estrictamente, "
            "no uses criterio de otra categoría de vulnerabilidad ---\n" + reference
        )
    return prompt


def _parse_verdict(content: str) -> TriageVerdict:
    """Nunca lanza -- una respuesta que no se puede parsear se trata como
    'real' (mismo criterio conservador que el system prompt le pide al
    modelo ante la duda): un fallo de parseo NUNCA debe traducirse en perder
    silenciosamente un hallazgo real."""
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("triage: respuesta del modelo no es JSON parseable: %r", content[:200])
        return TriageVerdict(
            verdict="real",
            reasoning="No se pudo interpretar la respuesta del modelo -- se mantiene como real por seguridad.",
            raw_response=content,
        )
    verdict = data.get("verdict")
    if verdict not in ("real", "false_positive"):
        verdict = "real"
    reasoning = str(data.get("reasoning", ""))[:500]
    return TriageVerdict(verdict=verdict, reasoning=reasoning, raw_response=content)


async def triage_finding(root: Path, finding: Finding) -> TriageVerdict:
    code_context = _code_context(root, finding)
    category = category_for_rule(finding.rule_id)
    reference = triage_reference.get_reference_for_category(category)
    user_prompt = _build_user_prompt(finding, code_context, reference)
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=_MAX_OUTPUT_TOKENS,
        temperature=0,
    )
    content = response.choices[0].message.content or ""
    return _parse_verdict(content)


async def triage_findings(root: Path, findings: list[Finding]) -> list[Finding]:
    """Corre triage secuencial (una llamada al LLM a la vez -- un único
    modelo local cargado, mandarlas en paralelo solo las haría competir por
    el mismo GPU/proceso) sobre cada finding y devuelve una NUEVA lista con
    `triage_status`/`triage_reasoning` seteados. No muta la lista original;
    si algún finding ya venía con `triage_status` seteado de una corrida
    anterior, se re-triagea igual (no hay cache de veredictos entre
    corridas en esta primera versión)."""
    triaged: list[Finding] = []
    for f in findings:
        try:
            verdict = await triage_finding(root, f)
        except Exception as exc:
            logger.warning("triage: fallo la llamada al modelo para %s:%s -- se mantiene como real: %s", f.file, f.line, exc)
            triaged.append(
                Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": f"Error en triage: {exc}"})
            )
            continue
        triaged.append(
            Finding(**{**f.to_dict(), "triage_status": verdict.verdict, "triage_reasoning": verdict.reasoning})
        )
    return triaged
