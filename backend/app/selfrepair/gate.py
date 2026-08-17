"""Guardrail duro de self-target: detecta cuándo una tool call de escritura
(`fs_write_file` o `code_apply_fix(confirm=true)`) apunta adentro del propio
código de Jarvis (`backend/`, la carpeta que contiene el proceso corriendo
AHORA), y decide si corresponde bloquearla. Usado desde el loop de tool
calls en `app/agent.py`, mismo lugar que `_obsidian_gate_error`/
`_pending_blocked_write_path`.

Reglas, deliberadamente estrictas (más fricción que velocidad, a pedido
explícito de Damian):

1. `fs_write_file` sobre código propio SIEMPRE se bloquea, sin excepción --
   no hay mecanismo de propuesta para una reescritura completa de archivo,
   solo para reemplazos de snippet puntuales y revisables.
2. `code_apply_fix` con `confirm=false` (dry-run) NUNCA se bloquea -- así es
   como se genera una propuesta en primer lugar, no debe tener fricción.
3. `code_apply_fix` con `confirm=true` sobre código propio requiere:
   a. Un `proposal_id` (formato `sf-xxxxxxxx`) presente LITERALMENTE en el
      texto del mensaje del usuario de ESTE turno -- no un booleano que
      pone el modelo, no una frase libre tipo "sí, dale" (ver discusión de
      diseño: un booleano del modelo es exactamente el nivel de confianza
      que ya falló antes, ej. `confirm_target_change` en
      security_audit_find_fix_verify).
   b. Que esa propuesta exista, siga en estado "proposed" (no aplicada ya),
      y su `file` resuelva al MISMO path que se está por escribir.
   c. Que `old_snippet`/`new_snippet` de la llamada real coincidan EXACTO
      con los de la propuesta -- si no, alguien podría reusar un
      proposal_id ya aprobado para colar un cambio distinto al mismo
      archivo. Sin este chequeo, (b) solo no alcanza."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from . import store
from .models import SelfFixProposal

# backend/app/selfrepair/gate.py -> parents[2] = backend/
JARVIS_OWN_SOURCE_ROOT = Path(__file__).resolve().parents[2]

_PROPOSAL_ID_RE = re.compile(r"\bsf-[0-9a-f]{8}\b")


def generate_proposal_id() -> str:
    return f"sf-{secrets.token_hex(4)}"


def extract_confirmed_proposal_ids(user_message: str) -> list[str]:
    """Todos los proposal_id presentes en el mensaje -- plural a propósito:
    un fix real puede necesitar más de un snippet en el mismo archivo (ej.
    la definición de una función Y su call site, lejos una de la otra), y
    Damian puede confirmar varios proposal_id en el mismo mensaje ('confirmo
    sf-aaaaaaaa y sf-bbbbbbbb'). Si solo se devolviera el primero, la
    segunda tool call de ese mismo turno nunca encontraría el suyo."""
    if not user_message:
        return []
    return _PROPOSAL_ID_RE.findall(user_message)


def is_self_target(resolved_path: Path) -> bool:
    try:
        resolved_path.relative_to(JARVIS_OWN_SOURCE_ROOT)
    except ValueError:
        return False
    return True


def _resolve_target_path(tool_name: str, args: dict) -> Path | None:
    if tool_name == "fs_write_file":
        from ..tools.filesystem import _resolve

        raw = args.get("path")
        if not raw:
            return None
        try:
            return _resolve(raw)
        except Exception:
            return None
    if tool_name == "code_apply_fix":
        root = args.get("path")
        file = args.get("file")
        if not root or not file:
            return None
        try:
            return (Path(root) / file).resolve()
        except Exception:
            return None
    return None


def _resolve_proposal_path(proposal: SelfFixProposal) -> Path:
    return (JARVIS_OWN_SOURCE_ROOT / proposal.file).resolve()


def _matching_pending_proposal(proposal_id: str, target: Path, args: dict) -> SelfFixProposal | None:
    proposal = store.load_proposal(proposal_id)
    if proposal is None or proposal.status != "proposed":
        return None
    if _resolve_proposal_path(proposal) != target:
        return None
    if proposal.old_snippet != args.get("old_snippet") or proposal.new_snippet != args.get("new_snippet"):
        return None
    return proposal


def self_target_gate_error(tool_name: str, args: dict, user_message: str) -> str | None:
    if tool_name not in ("fs_write_file", "code_apply_fix"):
        return None

    target = _resolve_target_path(tool_name, args)
    if target is None or not is_self_target(target):
        return None

    if tool_name == "fs_write_file":
        return (
            "Ese archivo es código propio de Jarvis (adentro de la carpeta del backend que está "
            "corriendo ahora) -- fs_write_file (reescritura completa) nunca está permitido ahí, sin "
            "excepción. Usá code_apply_fix con confirm=false primero para generar una propuesta "
            "revisable (diff puntual), y confirm=true recién después de que Damian confirme un "
            "proposal_id concreto en el chat."
        )

    if not args.get("confirm"):
        return None  # dry-run: así se genera la propuesta, sin fricción

    proposal_ids = extract_confirmed_proposal_ids(user_message)
    if any(_matching_pending_proposal(pid, target, args) is not None for pid in proposal_ids):
        return None

    return (
        "Ese archivo es código propio de Jarvis -- aplicarle un cambio de verdad (confirm=true) "
        "requiere un proposal_id (formato 'sf-xxxxxxxx') que Damian haya escrito LITERALMENTE en su "
        "mensaje de este turno, generado antes con selfrepair_propose_fix, y el old_snippet/"
        "new_snippet de esta llamada tienen que coincidir exacto con esa propuesta. No alcanza con "
        "que el usuario 'ya haya dicho que sí' en general -- pedile que confirme el proposal_id "
        "concreto."
    )


def consume_proposal_if_applied(tool_name: str, args: dict, user_message: str, result: object, applied_at: str) -> None:
    """Llamado DESPUÉS de que `call_tool` corrió con éxito -- si esto era un
    `code_apply_fix(confirm=true)` self-target que pasó el gate de arriba,
    marca la propuesta usada como aplicada para que no se pueda reusar el
    mismo proposal_id para otro cambio después."""
    if tool_name != "code_apply_fix" or not args.get("confirm"):
        return
    if isinstance(result, dict) and "error" in result:
        return
    target = _resolve_target_path(tool_name, args)
    if target is None or not is_self_target(target):
        return
    for proposal_id in extract_confirmed_proposal_ids(user_message):
        if _matching_pending_proposal(proposal_id, target, args) is not None:
            store.mark_applied(proposal_id, applied_at)
            return
