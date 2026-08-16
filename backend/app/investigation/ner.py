"""NER asistido por modelo (spec sección 5, punto 1: "Extracción de
entidades sobre texto no estructurado → propuestas de nodo, siempre en
estado 'pendiente de confirmación'"; paso 5 del orden de implementación).

Reglas duras que este módulo respeta:

1. El texto sobre el que corre SIEMPRE tiene que venir de un artefacto YA
   ingresado al caso (un `Archivo` con hash real ya en el grafo) -- nunca
   texto suelto sin origen. `propose_entities` exige `artefacto_origen`
   como parámetro obligatorio, no opcional: la trazabilidad no es una
   opción, es la condición de entrada (spec sección 2 + criterio de
   aceptación "todo nodo se puede rastrear hasta un artefacto con hash
   verificable").
2. Ninguna propuesta entra al grafo sola. Queda en estado "pendiente" en
   `proposals.jsonl` hasta que `confirm_proposal`/`reject_proposal` la
   resuelva -- son las únicas dos funciones de este módulo que escriben al
   caso de verdad, y ambas quedan en el log firmado (spec sección 6:
   "confirmación de sugerencia" es una operación que se audita).
3. `Archivo` NUNCA es un tipo proponible por NER (`_NER_ELIGIBLE_TYPES`
   excluye `NodeType.ARCHIVO`): su campo obligatorio `sha256` solo puede
   salir de un hash real calculado sobre bytes reales, nunca de que el
   modelo "lea" un nombre de archivo en un texto y lo alucine.
4. Un candidato con campos inválidos (falta un campo requerido, tipo de
   dato que no castea, etc.) se descarta individualmente sin tirar abajo
   el resto del batch -- pero queda visible en `NerResult.discarded` con el
   motivo, nunca se pierde en silencio total.

Confianza: dos ejes DISTINTOS, no confundir.
- `confianza_extraccion` (nueva, vive en `EntityProposal`, no en el Node):
  qué tan seguro está el modelo de que identificó correctamente el límite
  y el tipo de la entidad en el texto -- una propiedad de la EXTRACCIÓN.
- `campos["confianza"]` de una `Persona` (ya existía, ver models.py): mide
  si esa persona existe como entidad distinguible y si los alias listados
  le pertenecen -- una propiedad de la ENTIDAD, decidida por Damian
  2026-08-12. El modelo puede proponer ambas, pero son preguntas distintas
  y el system prompt se lo aclara explícitamente para no mezclarlas.

Trazabilidad de un nodo confirmado: igual que csv_parser.py (mismo patrón,
no un campo nuevo inventado) -- confirmar una propuesta crea el Node Y una
arista `aparece_en` real hacia el `Archivo` de origen, con
`derivada_por=DerivadaPor.MODELO` y `confianza=confianza_extraccion`. Así
"un clic hasta el artefacto con hash verificable" sigue siendo cierto para
nodos que vinieron de NER, sin tocar el schema de Node."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from ..llm_client import client
from . import case_store
from . import log as log_module
from .models import (
    REQUIRED_NODE_FIELDS,
    DerivadaPor,
    EdgeType,
    Node,
    NodeType,
    make_cuenta,
    make_dispositivo,
    make_edge,
    make_evento,
    make_host,
    make_organizacion,
    make_persona,
    make_transaccion,
)

_MAX_OUTPUT_TOKENS = 2048

_MAKE_FUNCS: dict[NodeType, Callable[..., Node]] = {
    NodeType.PERSONA: make_persona,
    NodeType.CUENTA: make_cuenta,
    NodeType.DISPOSITIVO: make_dispositivo,
    NodeType.HOST: make_host,
    NodeType.TRANSACCION: make_transaccion,
    NodeType.EVENTO: make_evento,
    NodeType.ORGANIZACION: make_organizacion,
}  # ARCHIVO deliberadamente ausente -- ver punto 3 del docstring del módulo

_NER_ELIGIBLE_TYPES = list(_MAKE_FUNCS.keys())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EntityProposal:
    id: str
    tipo: NodeType
    campos: dict[str, Any]
    texto_fuente: str
    confianza_extraccion: float
    razon: str
    artefacto_origen: str
    status: str  # "pendiente" | "confirmado" | "rechazado"
    created_at: str
    resolved_at: str | None = None
    resolved_reason: str | None = None
    node_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "tipo": self.tipo.value, "campos": self.campos,
            "texto_fuente": self.texto_fuente, "confianza_extraccion": self.confianza_extraccion,
            "razon": self.razon, "artefacto_origen": self.artefacto_origen, "status": self.status,
            "created_at": self.created_at, "resolved_at": self.resolved_at,
            "resolved_reason": self.resolved_reason, "node_id": self.node_id,
        }

    @staticmethod
    def from_dict(data: dict) -> "EntityProposal":
        return EntityProposal(
            id=data["id"], tipo=NodeType(data["tipo"]), campos=data["campos"],
            texto_fuente=data["texto_fuente"], confianza_extraccion=data["confianza_extraccion"],
            razon=data["razon"], artefacto_origen=data["artefacto_origen"], status=data["status"],
            created_at=data["created_at"], resolved_at=data.get("resolved_at"),
            resolved_reason=data.get("resolved_reason"), node_id=data.get("node_id"),
        )


@dataclass
class NerResult:
    proposals: list[EntityProposal] = field(default_factory=list)
    discarded: list[dict] = field(default_factory=list)  # {"candidate": {...}, "reason": "..."}


# Nombres de campo con semántica de "lista" o "número" en el schema (ver
# REQUIRED_NODE_FIELDS) -- el modelo local a veces devuelve un string suelto
# donde corresponde una lista (bug real encontrado corriendo esto contra el
# modelo real, ver _coerce_campos), mismo tipo de normalización que ya hace
# csv_parser.py para valores de CSV (siempre strings), pero acá la entrada
# ya es JSON tipado y puede venir bien o mal.
_LIST_FIELDS = frozenset({"alias", "identificadores"})
_NUMERIC_FIELDS = frozenset({"confianza", "monto"})

# Sin esto, "campos {sorted(...)}" en el prompt es solo una lista de
# nombres -- el modelo real, corrido de verdad, confundió "etiqueta" (el
# nombre de la Persona) con "alias" (que además esperaba una lista, no un
# string) y dejó "etiqueta" en null. Describir semántica + tipo esperado
# por campo, no solo el nombre, es lo que corrige eso en el prompt; la
# validación de abajo (_missing_required_value) es la red de seguridad para
# cuando el modelo igual se equivoca.
_FIELD_HINTS: dict[str, str] = {
    "etiqueta": "nombre o identificador principal de la persona (string, ej. 'Juan Perez') -- obligatorio, nunca null",
    "alias": "lista de apodos o nombres alternativos (array de strings, [] si no hay ninguno)",
    "confianza": "0 a 1, qué tan segura es la existencia de esta entidad como algo distinguible",
    "plataforma": "nombre de la plataforma/servicio (string, ej. 'Telegram', 'Mercado Pago')",
    "handle": "usuario/nombre de cuenta en esa plataforma, tal como aparece en el texto (string)",
    "fecha_alta": "fecha de creación de la cuenta si el texto la menciona, si no null",
    "tipo_dispositivo": "tipo de dispositivo (string, ej. 'teléfono', 'notebook')",
    "identificadores": "identificadores del dispositivo (array de strings: IMEI, número de serie, número de teléfono, etc.)",
    "ip_o_dominio": "IP o dominio mencionado (string)",
    "asn": "ASN si el texto lo menciona, si no null",
    "geolocalizacion_declarada": "geolocalización mencionada en el texto, si no null",
    "tipo_transaccion": "tipo de transacción (string, ej. 'transferencia', 'pago')",
    "monto": "monto de la transacción (número, no un string)",
    "timestamp": "fecha/hora de la transacción, ISO 8601 si se puede inferir del texto",
    "contraparte": "la otra parte de la transacción, si el texto la nombra",
    "timestamp_utc": "fecha/hora del evento, ISO 8601 si se puede inferir del texto",
    "descripcion": "descripción breve del evento (string)",
    "fuente": "de dónde sale este evento según el propio texto (ej. 'mensaje de chat')",
    "nombre": "nombre de la organización o archivo (string)",
}


def _entity_types_prompt_block() -> str:
    lines = []
    for tipo in _NER_ELIGIBLE_TYPES:
        campos_desc = "; ".join(f"{c} ({_FIELD_HINTS.get(c, 'string')})" for c in sorted(REQUIRED_NODE_FIELDS[tipo]))
        lines.append(f"- {tipo.value}: {campos_desc}")
    return "\n".join(lines)


_SYSTEM_PROMPT_TEMPLATE = (
    "Sos un asistente de extracción de entidades (NER) para un caso de investigación. Te dan un fragmento de "
    "texto no estructurado y tenés que proponer las entidades que el texto menciona EXPLÍCITAMENTE -- nunca "
    "infieras una entidad que el texto no nombra, ni completes campos con datos que no estén en el texto "
    "(dejalos null antes que inventarlos). Un campo marcado como lista SIEMPRE tiene que ser un array JSON, "
    "nunca un string suelto -- ej. \"alias\": [\"Juanito\"], no \"alias\": \"Juanito\". Un campo marcado como "
    "obligatorio nunca puede quedar null: si no podés completarlo con algo que el texto realmente dice, no "
    "propongas esa entidad. Tipos de entidad disponibles y sus campos:\n"
    "{tipos}\n"
    "Para cada entidad que encuentres, devolvé un objeto con:\n"
    '- "tipo": uno de los tipos de arriba (el nombre exacto)\n'
    '- "campos": los campos de ese tipo, según lo que el texto realmente dice\n'
    '- "texto_fuente": el fragmento EXACTO del texto de donde sale esta entidad, para que un humano lo pueda '
    "verificar\n"
    '- "confianza_extraccion": 0 a 1 -- qué tan seguro estás de que identificaste correctamente el límite y el '
    "tipo de esta entidad en el texto. Esto NO es si la entidad existe o es real -- es solo qué tan clara fue "
    "la extracción.\n"
    '- "razon": una frase breve\n'
    "Respondé SOLO con un array JSON de esos objetos, sin texto alrededor. Si no hay ninguna entidad "
    "reconocible, devolvé exactamente []."
)


def _coerce_campos(campos: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(campos)
    for field_name, value in campos.items():
        if field_name in _LIST_FIELDS and value is not None and not isinstance(value, list):
            coerced[field_name] = [value]
        elif field_name in _NUMERIC_FIELDS and isinstance(value, str):
            coerced[field_name] = float(value)
    return coerced


def _strip_empty_values(campos: dict[str, Any]) -> dict[str, Any]:
    """Un valor `None` o string vacío para una clave se trata como "no lo
    completes" en vez de pasarlo tal cual al make_* -- así es la firma REAL
    de cada make_* (fuente única de verdad, ver models.py) la que decide si
    esa clave tiene default legítimo (ej. `fecha_alta`/`asn`, se omite sin
    problema) o es de verdad obligatoria sin default (ej. `etiqueta`,
    `TypeError` real por argumento faltante -> el candidato se descarta).
    Evita duplicar acá una lista aparte de "qué campo puede quedar vacío"
    que ya vive codificada en cada firma make_*. No toca `[]` (una lista
    vacía real, ej. `alias=[]`, es un valor legítimo, no un vacío a limpiar)."""
    return {k: v for k, v in campos.items() if v is not None and v != ""}


def _parse_candidates(artefacto_origen: str, raw: str) -> NerResult:
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"El modelo no devolvió un array JSON parseable para NER: {raw[:300]!r}")
    candidates = json.loads(raw[start : end + 1])

    result = NerResult()
    for candidate in candidates:
        try:
            tipo = NodeType(candidate["tipo"])
            if tipo not in _MAKE_FUNCS:
                raise ValueError(f"tipo '{tipo.value}' no es proponible por NER")
            coerced = _coerce_campos(candidate["campos"])
            campos_for_call = _strip_empty_values(coerced)
            # node.campos (no `coerced` crudo) queda en la propuesta -- ya
            # tiene los defaults reales aplicados (ej. alias=[] si no vino),
            # así que lo que ve Damian YA es la entidad final, y
            # confirm_proposal puede volver a llamar al mismo make_* con
            # estos campos sin sorpresas.
            node = _MAKE_FUNCS[tipo](**campos_for_call)
        except (KeyError, ValueError, TypeError) as exc:
            result.discarded.append({"candidate": candidate, "reason": str(exc)})
            continue

        result.proposals.append(EntityProposal(
            id=uuid.uuid4().hex, tipo=tipo, campos=node.campos,
            texto_fuente=candidate.get("texto_fuente", ""),
            confianza_extraccion=float(candidate.get("confianza_extraccion", 0.5)),
            razon=candidate.get("razon", ""), artefacto_origen=artefacto_origen,
            status="pendiente", created_at=_now(),
        ))
    return result


async def propose_entities(texto: str, artefacto_origen: str) -> NerResult:
    """SOLO propone -- nunca escribe al caso. `artefacto_origen` es el id
    del Node Archivo ya ingresado del que sale `texto` (obligatorio, ver
    punto 1 del docstring del módulo)."""
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(tipos=_entity_types_prompt_block())
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": texto}],
        temperature=0,
        max_tokens=_MAX_OUTPUT_TOKENS,
    )
    raw = response.choices[0].message.content or ""
    return _parse_candidates(artefacto_origen, raw)


def _proposals_path(case_dir: Path) -> Path:
    return case_dir / "proposals.jsonl"


def _write_proposals(case_dir: Path, proposals: list[EntityProposal]) -> None:
    # A propósito NO se commitea a git (a diferencia de nodes.jsonl/
    # edges.jsonl/log.jsonl): una propuesta pendiente no es todavía "estado
    # del caso" en el sentido de la spec (sección 6), es un borrador de
    # trabajo. Recién cuando se confirma se vuelve estado real, y esa
    # llamada pasa por case_store.add_node/add_edge, que sí commitea.
    _proposals_path(case_dir).write_text(
        "".join(json.dumps(p.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n" for p in proposals),
        encoding="utf-8",
    )


def save_proposals(cases_dir: str | Path, case_id: str, proposals: list[EntityProposal]) -> list[EntityProposal]:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")
    existing = read_proposals(cases_dir, case_id)
    existing.extend(proposals)
    _write_proposals(case_dir, existing)
    return proposals


def read_proposals(cases_dir: str | Path, case_id: str, status: str | None = None) -> list[EntityProposal]:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    path = _proposals_path(case_dir)
    if not path.is_file():
        return []
    all_proposals = [
        EntityProposal.from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if status is None:
        return all_proposals
    return [p for p in all_proposals if p.status == status]


def confirm_proposal(cases_dir: str | Path, keys_dir: str | Path, case_id: str, proposal_id: str) -> Node:
    """Única forma de que una propuesta de NER se vuelva un Node real. Crea
    el Node + la arista `aparece_en` de trazabilidad hacia el Archivo de
    origen (ver docstring del módulo), y dos cosas quedan en `proposals.jsonl`
    actualizadas: `status="confirmado"` y `node_id` apuntando al Node real
    creado, para poder ir de la propuesta al resultado y viceversa."""
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")
    proposals = read_proposals(cases_dir, case_id)
    target = next((p for p in proposals if p.id == proposal_id), None)
    if target is None:
        raise ValueError(f"No existe la propuesta '{proposal_id}' en el caso '{case_id}'")
    if target.status != "pendiente":
        raise ValueError(f"La propuesta '{proposal_id}' ya fue resuelta ({target.status})")

    node = _MAKE_FUNCS[target.tipo](**target.campos)
    case_store.add_node(cases_dir, keys_dir, case_id, node)

    edge = make_edge(
        tipo=EdgeType.APARECE_EN, origen=node.id, destino=target.artefacto_origen,
        artefacto_origen=target.artefacto_origen, confianza=target.confianza_extraccion,
        derivada_por=DerivadaPor.MODELO,
    )
    case_store.add_edge(cases_dir, keys_dir, case_id, edge)

    at = _now()
    target.status = "confirmado"
    target.resolved_at = at
    target.node_id = node.id
    log_module.append_entry(
        case_dir / "log.jsonl", keys_dir, op="confirm_proposal",
        payload={"id": proposal_id, "node_id": node.id, "at": at},
    )
    _write_proposals(case_dir, proposals)
    return node


def reject_proposal(cases_dir: str | Path, keys_dir: str | Path, case_id: str, proposal_id: str, reason: str) -> EntityProposal:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")
    proposals = read_proposals(cases_dir, case_id)
    target = next((p for p in proposals if p.id == proposal_id), None)
    if target is None:
        raise ValueError(f"No existe la propuesta '{proposal_id}' en el caso '{case_id}'")
    if target.status != "pendiente":
        raise ValueError(f"La propuesta '{proposal_id}' ya fue resuelta ({target.status})")

    at = _now()
    target.status = "rechazado"
    target.resolved_at = at
    target.resolved_reason = reason
    log_module.append_entry(
        case_dir / "log.jsonl", keys_dir, op="reject_proposal",
        payload={"id": proposal_id, "reason": reason, "at": at},
    )
    _write_proposals(case_dir, proposals)
    return target
