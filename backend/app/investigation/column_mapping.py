"""Mapeo de columnas de un CSV/JSONL genérico a campos del schema de
entidades (spec sección 2 + decisión de Damian 2026-08-12, ambigüedad #6):
la PRIMERA vez que se ve una estructura de columnas nueva, el modelo local
propone qué columna corresponde a qué campo (mirando nombres de columna +
valores de ejemplo) -- Damian confirma o corrige, y ESE mapeo confirmado se
guarda como config reutilizable, indexado por la firma de las columnas (no
por nombre de archivo: dos archivos distintos con las mismas columnas
reusan el mismo mapeo sin volver a preguntar).

Rol del modelo estrictamente acotado a PROPONER (spec sección 5,
"normalización") -- `propose_mapping` nunca escribe nada, nunca se guarda
sola: guardar el mapeo confirmado es una acción DELIBERADA y aparte
(`save_mapping`), disparada por la confirmación real de Damian, no un efecto
colateral automático de proponer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..llm_client import client
from .models import REQUIRED_NODE_FIELDS, NodeType

_MAX_SAMPLE_ROWS = 5
_MAX_OUTPUT_TOKENS = 1024


@dataclass
class MappingProposal:
    node_type: NodeType
    columns: dict[str, str]  # nombre de columna del CSV -> campo del schema (o ausente si no matchea nada)
    unmapped_columns: list[str]
    reasoning: str


def source_signature(columns: list[str]) -> str:
    """Mismo conjunto/orden de columnas -> siempre la misma firma -- lo que
    permite reusar un mapeo confirmado en un archivo NUEVO con la misma
    estructura, sin volver a proponer/preguntar."""
    return hashlib.sha256("|".join(columns).encode("utf-8")).hexdigest()[:16]


def _mapping_path(mappings_dir: str | Path, columns: list[str]) -> Path:
    return Path(mappings_dir) / f"{source_signature(columns)}.json"


def load_saved_mapping(mappings_dir: str | Path, columns: list[str]) -> dict | None:
    path = _mapping_path(mappings_dir, columns)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_mapping(
    mappings_dir: str | Path, columns: list[str], node_type: NodeType, column_mapping: dict[str, str],
    defaults: dict[str, object] | None = None,
) -> dict:
    """Persiste un mapeo YA CONFIRMADO por Damian -- nunca se llama desde
    `propose_mapping`. Sobrescribe si ya había uno guardado para esta misma
    firma de columnas (Damian corrigiendo un mapeo previo)."""
    mappings_dir = Path(mappings_dir)
    mappings_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "node_type": node_type.value,
        "columns_seen": columns,
        "column_mapping": column_mapping,
        "defaults": defaults or {},
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    _mapping_path(mappings_dir, columns).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


_SYSTEM_PROMPT = (
    "Sos un asistente de mapeo de datos. Te dan las columnas de un CSV y algunas filas de ejemplo, más una "
    "lista de campos de destino de un tipo de entidad. Tu única tarea es proponer, para cada columna del CSV, "
    "a qué campo de destino corresponde (o ninguno si no aplica) -- mirando el NOMBRE de la columna y los "
    "VALORES de ejemplo, no inventes relaciones que no se vean en los datos reales. Nunca concluyas nada más "
    "que el mapeo. Respondé SOLO con JSON: "
    '{"columns": {"columna_csv": "campo_destino", ...}, "reasoning": "explicación breve"}. '
    "Una columna que no corresponda a ningún campo simplemente no aparece en \"columns\"."
)


def _parse_proposal(node_type: NodeType, columns: list[str], raw: str) -> MappingProposal:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"El modelo no devolvió JSON parseable para el mapeo: {raw[:300]!r}")
    data = json.loads(raw[start : end + 1])
    proposed_columns = {k: v for k, v in data.get("columns", {}).items() if k in columns}
    unmapped = [c for c in columns if c not in proposed_columns]
    return MappingProposal(
        node_type=node_type, columns=proposed_columns, unmapped_columns=unmapped,
        reasoning=data.get("reasoning", ""),
    )


async def propose_mapping(node_type: NodeType, columns: list[str], sample_rows: list[dict[str, str]]) -> MappingProposal:
    """SOLO propone -- nunca guarda, nunca escribe al grafo. `sample_rows`
    idealmente 3-5 filas reales del CSV (no todo el archivo: alcanza para
    que el modelo vea el FORMATO de los valores, y mandar todo el archivo
    sería carísimo de prompt para nada)."""
    target_fields = sorted(REQUIRED_NODE_FIELDS[node_type])
    user_msg = (
        f"Tipo de entidad de destino: {node_type.value}\n"
        f"Campos de destino disponibles: {target_fields}\n"
        f"Columnas del CSV: {columns}\n"
        f"Filas de ejemplo:\n{json.dumps(sample_rows[:_MAX_SAMPLE_ROWS], ensure_ascii=False, indent=2)}"
    )
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user_msg}],
        temperature=0,
        max_tokens=_MAX_OUTPUT_TOKENS,
    )
    raw = response.choices[0].message.content or ""
    return _parse_proposal(node_type, columns, raw)
