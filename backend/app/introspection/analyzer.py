"""Detección de patrones de falla conocidos en el comportamiento del propio
agente (Opción B de auto-reparación, decidida 2026-08-10 después de la v6 del
test del mod de Minecraft -- ver la sesión de esa fecha).

Contexto: en esa v6 encontramos dos bugs reales de comportamiento a mano,
leyendo logs línea por línea:
1. El modelo reescribió el mismo archivo (`sneaky_sword.json`) con contenido
   BYTE-IDÉNTICO 14 veces seguidas, sin avanzar.
2. `SpadeMod.java` quedó bloqueado una vez por el guardrail de "archivo
   pendiente" y nunca se volvió a intentar en el resto de la sesión -- el
   modelo se distrajo con otros archivos y lo abandonó.

Ninguno de los dos es un hallazgo que audite `security_scan`/`quality_scan`
(Ruff, mypy): son bugs de COMPORTAMIENTO del agente, visibles solo mirando la
secuencia temporal de tool calls de una conversación. Por eso este módulo no
analiza código -- analiza `audit_log` (ver `agent.py::run_agent`, que ahora
loguea ahí, con `target="agent"`, cada tool call del loop, bloqueada o no).

Diseño explícito (decisión de Damian, 2026-08-10): este módulo NUNCA toca
código ni dispara una reparación automática. Su única salida es una nota en
el vault de Obsidian con el patrón detectado, la evidencia concreta, y una
hipótesis de causa/corrección -- para que un humano (o una sesión de Claude
Code) decida qué hacer, igual que las notas de `research_topic`. Es
deliberadamente el escalón más chico y menos riesgoso de los tres evaluados
(el otro extremo, dejar que Jarvis edite su propio `backend/app/`, requiere
antes un mecanismo de watchdog/rollback que hoy no existe -- ver esa
conversación para el análisis de riesgo completo)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import audit_log
from ..obsidian import vault

# Corridas de menos escrituras idénticas que esto no cuentan como patrón --
# reescribir el mismo archivo dos veces seguidas (ej. una corrección chica
# inmediata) es comportamiento normal, no un loop. El caso real de v6 fue 14
# repeticiones; 3 es un piso conservador para no generar ruido con casos
# borde legítimos.
_DEFAULT_MIN_REPEATS = 3

_CATEGORY = "autodiagnostico-jarvis"


@dataclass
class Finding:
    pattern: str  # "reescritura_identica_repetida" | "archivo_bloqueado_abandonado"
    conversation_id: str
    tool: str
    path: str
    summary: str
    hypothesis: str
    suggested_fix: str
    evidence: list[dict] = field(default_factory=list)


def _fs_write_entries(conversation_id: str | None = None) -> list[dict]:
    return audit_log.read_entries(target="agent", tool="fs_write_file", conversation_id=conversation_id)


def _group_by_conversation(entries: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        conv_id = entry.get("conversation_id")
        if not conv_id:
            continue  # entradas sin conversation_id (llamadas antes de este cambio) no se pueden agrupar
        groups.setdefault(conv_id, []).append(entry)
    return groups


def _find_repeated_identical_writes(
    conversation_id: str, entries: list[dict], min_repeats: int = _DEFAULT_MIN_REPEATS
) -> list[Finding]:
    """Corridas consecutivas de escrituras EXITOSAS al mismo path con el mismo
    `content_sha256` -- el patrón #1 de v6 (`sneaky_sword.json` x14)."""
    findings: list[Finding] = []
    run: list[dict] = []

    def _flush() -> None:
        if len(run) < min_repeats:
            return
        path = run[0]["arguments"].get("path", "?")
        timestamps = [e.get("timestamp") for e in run]
        findings.append(
            Finding(
                pattern="reescritura_identica_repetida",
                conversation_id=conversation_id,
                tool="fs_write_file",
                path=path,
                summary=(
                    f"Jarvis reescribió '{path}' con contenido byte-idéntico "
                    f"{len(run)} veces seguidas, sin escribir nada nuevo entre medio."
                ),
                hypothesis=(
                    "El modelo entró en un loop: repite la misma tool call porque no percibe que ya tuvo éxito, "
                    "o porque perdió de vista qué le falta hacer después de esta escritura. No hay ningún "
                    "guardrail hoy que detecte 'ya escribiste esto, con este mismo contenido, hace un momento'."
                ),
                suggested_fix=(
                    "Guardrail duro en el loop de tool calls (mismo patrón que `_pending_blocked_write_path` / "
                    "`_obsidian_gate_error` en `agent.py`): si las últimas N llamadas a `fs_write_file` fueron "
                    "al mismo path con el mismo `content_sha256`, bloquear la siguiente con un mensaje explícito "
                    "('ya escribiste esto, dejá de repetirlo y seguí con el resto del trabajo') en vez de "
                    "ejecutarla de nuevo."
                ),
                evidence=[
                    {"timestamp": ts, "path": path, "content_sha256": run[0]["arguments"].get("content_sha256")}
                    for ts in timestamps
                ],
            )
        )

    prev_key: tuple[str, str] | None = None
    for entry in entries:
        if not entry.get("ok"):
            prev_key = None
            _flush()
            run = []
            continue
        args = entry.get("arguments") or {}
        key = (args.get("path"), args.get("content_sha256"))
        if key == prev_key and key[0] is not None:
            run.append(entry)
        else:
            _flush()
            run = [entry]
            prev_key = key
    _flush()
    return findings


def _find_abandoned_blocked_writes(conversation_id: str, entries: list[dict]) -> list[Finding]:
    """Un `fs_write_file` bloqueado (guardrail de Obsidian, de pending-file, o
    cualquier otro error) del que nunca hay una escritura exitosa posterior al
    MISMO path dentro de la misma conversación -- el patrón #2 de v6
    (`SpadeMod.java`, bloqueado una vez y nunca reintentado)."""
    findings: list[Finding] = []
    for i, entry in enumerate(entries):
        if entry.get("ok"):
            continue
        path = (entry.get("arguments") or {}).get("path")
        if not path:
            continue
        retried = any(
            later.get("ok") is True and (later.get("arguments") or {}).get("path") == path
            for later in entries[i + 1 :]
        )
        if retried:
            continue
        findings.append(
            Finding(
                pattern="archivo_bloqueado_abandonado",
                conversation_id=conversation_id,
                tool="fs_write_file",
                path=path,
                summary=(
                    f"'{path}' fue bloqueado por un guardrail ({entry.get('error', '')[:200]}) "
                    "y nunca se volvió a escribir con éxito en el resto de la sesión."
                ),
                hypothesis=(
                    "El modelo se distrajo con otros archivos después del bloqueo y perdió de vista que "
                    "este quedó pendiente. Mismo patrón que motivó el guardrail de "
                    "`_pending_blocked_write_path` en `agent.py` (agregado después de que v4 y v5 "
                    "abandonaran `build.gradle` de la misma forma) -- si este finding aparece, ese "
                    "guardrail no cubrió este caso puntual (ver docstring de esa función: solo trackea "
                    "UN archivo pendiente a la vez, así que un segundo bloqueo mientras el primero seguía "
                    "pendiente puede perderse)."
                ),
                suggested_fix=(
                    "Extender `_pending_blocked_write_path` (o su reemplazo) para trackear un CONJUNTO de "
                    "paths pendientes en vez de un único valor, así un segundo archivo bloqueado mientras "
                    "el primero sigue pendiente no se pierde cuando el primero se resuelve."
                ),
                evidence=[
                    {"timestamp": entry.get("timestamp"), "path": path, "error": entry.get("error")}
                ],
            )
        )
    return findings


def analyze_conversation(conversation_id: str, min_repeats: int = _DEFAULT_MIN_REPEATS) -> list[Finding]:
    entries = _fs_write_entries(conversation_id)
    return _find_repeated_identical_writes(conversation_id, entries, min_repeats) + _find_abandoned_blocked_writes(
        conversation_id, entries
    )


def analyze_all(min_repeats: int = _DEFAULT_MIN_REPEATS) -> list[Finding]:
    """Analiza TODAS las conversaciones presentes en `audit.log` -- pensado
    para correr después de una sesión sin tener que pasarle el conversation_id
    a mano, o como barrido periódico/on-demand."""
    groups = _group_by_conversation(_fs_write_entries())
    findings: list[Finding] = []
    for conv_id, entries in groups.items():
        findings += _find_repeated_identical_writes(conv_id, entries, min_repeats)
        findings += _find_abandoned_blocked_writes(conv_id, entries)
    return findings


def _note_title(finding: Finding) -> str:
    filename = Path(finding.path).name
    short_conv = finding.conversation_id[:12]
    if finding.pattern == "reescritura_identica_repetida":
        return f"autodiagnóstico: loop de reescritura idéntica en '{filename}' (sesión {short_conv})"
    return f"autodiagnóstico: archivo bloqueado y abandonado '{filename}' (sesión {short_conv})"


def _note_content(finding: Finding) -> str:
    parts = [
        f"Patrón detectado automáticamente por `app/introspection/analyzer.py`: **{finding.pattern}**.",
        f"\n## Qué pasó\n{finding.summary}",
        f"\n## Evidencia\n- Conversación: `{finding.conversation_id}`\n- Tool: `{finding.tool}`\n- Path: `{finding.path}`",
    ]
    for item in finding.evidence:
        parts.append(f"  - {item}")
    parts.append(f"\n## Hipótesis de causa raíz\n{finding.hypothesis}")
    parts.append(f"\n## Corrección sugerida\n{finding.suggested_fix}")
    parts.append(
        "\n## Nota\nEsta nota es solo diagnóstico -- generada por meta-observación (Opción B), no aplica "
        "ningún cambio de código por sí sola. Corregir esto sigue siendo trabajo humano (o de Claude Code) "
        "hasta que se decida dar el siguiente paso del diseño de auto-reparación."
    )
    return "\n".join(parts)


def write_finding_note(finding: Finding) -> vault.VaultNote:
    index_note = vault.link_note_to_category_index(_note_title(finding), category=_CATEGORY, author="jarvis")
    return vault.save_note(
        title=_note_title(finding),
        content=_note_content(finding) + f"\n\n## Notas relacionadas\n- [[{index_note.title}]]",
        author="jarvis",
        tags=["autodiagnostico", finding.pattern],
        category=_CATEGORY,
    )
