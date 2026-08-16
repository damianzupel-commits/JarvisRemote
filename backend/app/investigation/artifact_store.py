"""Almacén de artefactos de solo lectura, indexado por SHA-256 (spec sección
2: "al entrar un artefacto se calcula SHA-256, se guarda copia inmutable en
un almacén de solo-lectura"). Vive FUERA de cualquier directorio versionado
con git (decisión de Damian, 2026-08-12) -- un repo de caso solo versiona el
grafo/log/metadata, nunca los binarios originales, así que este store es un
directorio de datos aparte, mismo criterio que `security_scan_dir`/
`codebase_index_dir` (cache-like, no un repo git en sí mismo).

Content-addressed: la ruta de cada artefacto sale de su propio hash
(sharding de 2 caracteres para no amontonar miles de archivos en un mismo
directorio), así el mismo archivo cargado dos veces -- o desde dos casos
distintos -- se guarda UNA sola vez, siempre en la misma ruta.

Reingesta incremental (decisión de Damian): esto NO decide por sí solo qué
hacer si un artefacto se recarga -- eso es responsabilidad de cada parser
(que sabe cómo diferenciar "línea/mensaje ya visto" de "nuevo" para SU
formato). Lo que este módulo ofrece es el mecanismo genérico para que un
parser guarde y lea su propio `ingestion_marker` (un string opaco para este
módulo -- un offset de línea, un id/timestamp del último mensaje procesado,
lo que tenga sentido para ese formato) asociado al hash del artefacto, así
sabe desde dónde seguir la próxima vez sin tener que re-parsear todo desde
cero. El marker es la ÚNICA parte de un ArtifactRecord que se actualiza
después de creado -- los bytes del artefacto en sí nunca cambian una vez
escritos (`store_artifact` es un no-op si el hash ya existe)."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ArtifactRecord:
    sha256: str
    original_name: str
    size: int
    mime: str | None
    ingested_at: str
    ingested_by: str
    ingestion_marker: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "ArtifactRecord":
        return ArtifactRecord(**data)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _object_path(store_dir: Path, sha256: str) -> Path:
    return store_dir / "objects" / sha256[:2] / sha256


def _record_path(store_dir: Path, sha256: str) -> Path:
    return store_dir / "records" / f"{sha256}.json"


def store_artifact(store_dir: str | Path, data: bytes, original_name: str, ingested_by: str) -> ArtifactRecord:
    """Guarda `data` si su hash todavía no está en el store (no-op si ya
    existe -- inmutable, nunca se reescribe un objeto ya guardado) y
    devuelve el ArtifactRecord real (el existente si ya estaba, uno nuevo si
    no). El hash se calcula acá, nunca se confía en uno que mande el
    caller."""
    store_dir = Path(store_dir)
    sha256 = hashlib.sha256(data).hexdigest()

    existing = read_record(store_dir, sha256)
    if existing is not None:
        return existing

    object_path = _object_path(store_dir, sha256)
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(data)

    mime, _ = mimetypes.guess_type(original_name)
    record = ArtifactRecord(
        sha256=sha256, original_name=original_name, size=len(data), mime=mime,
        ingested_at=_now(), ingested_by=ingested_by,
    )
    _save_record(store_dir, record)
    return record


def _save_record(store_dir: Path, record: ArtifactRecord) -> None:
    record_path = _record_path(store_dir, record.sha256)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def read_record(store_dir: str | Path, sha256: str) -> ArtifactRecord | None:
    store_dir = Path(store_dir)
    record_path = _record_path(store_dir, sha256)
    if not record_path.is_file():
        return None
    return ArtifactRecord.from_dict(json.loads(record_path.read_text(encoding="utf-8")))


def read_artifact_bytes(store_dir: str | Path, sha256: str) -> bytes:
    store_dir = Path(store_dir)
    object_path = _object_path(store_dir, sha256)
    if not object_path.is_file():
        raise FileNotFoundError(f"No hay ningún artefacto con hash '{sha256}' en el store")
    return object_path.read_bytes()


def set_ingestion_marker(store_dir: str | Path, sha256: str, marker: str | None) -> ArtifactRecord:
    """Único campo mutable de un ArtifactRecord -- ver docstring del módulo.
    Falla si el artefacto no existe (no crea un record fantasma sin bytes
    detrás)."""
    store_dir = Path(store_dir)
    record = read_record(store_dir, sha256)
    if record is None:
        raise FileNotFoundError(f"No hay ningún artefacto con hash '{sha256}' en el store")
    record.ingestion_marker = marker
    _save_record(store_dir, record)
    return record
