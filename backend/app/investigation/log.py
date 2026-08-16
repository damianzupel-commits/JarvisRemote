"""Log append-only del módulo de investigación (spec sección 6): cada
operación (ingesta, creación/edición/retracción de nodo o arista,
confirmación de una sugerencia del modelo) queda como una línea JSON,
encadenada por hash a la anterior Y firmada con Ed25519 (ver
app/investigation/keys.py para la decisión de dónde vive la clave privada).

Dos garantías DISTINTAS, ninguna sustituye a la otra:
- **Encadenamiento por hash** (`prev_hash`/`entry_hash`): tamper-evidence --
  modificar CUALQUIER campo de CUALQUIER entrada vieja cambia su
  entry_hash, lo que rompe el prev_hash de la entrada siguiente, y así en
  cadena hasta el final. Detecta manipulación aunque quien la haga no tenga
  la clave privada.
- **Firma Ed25519** (`signature`): autenticidad -- prueba que cada entrada
  la escribió alguien con acceso a la clave privada real (esta instalación
  de Jarvis), no solo que la cadena de hashes es internamente consistente
  (alguien SIN la clave privada podría, en teoría, reescribir el archivo
  entero generando una cadena de hashes nueva y perfectamente consistente
  consigo misma -- pero no podría firmar cada entrada sin la clave, así que
  `verify_chain` lo detectaría igual).

Append-only de verdad: este módulo SOLO expone `append_entry` (abre en modo
'a', nunca reescribe una línea existente) y `verify_chain`/`read_entries`
(lectura). No existe ninguna función acá para editar o borrar una entrada ya
escrita -- eso es a propósito (spec: "ningún borrado real"). Una corrección
es SIEMPRE una entrada nueva que referencia a la anterior (ver
`retracted_reason` en models.Node/Edge, y el op "retract_node"/"retract_edge"
que arma case_store.py), nunca una edición in-place."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import keys as keys_module

GENESIS_HASH = "0" * 64


class CorruptedLogError(ValueError):
    """Una línea del log no es JSON válido y NO es la última línea del
    archivo -- ver docstring de `read_entries`/`_last_entry` (bug real
    encontrado en testing adversarial, 2026-08-13, "kill duro a mitad de
    un write"): una línea corrupta que NO es la última es una señal mucho
    más seria que una escritura interrumpida (podría ser manipulación real
    del archivo), así que nunca se salta en silencio como si fuera solo
    un write cortado -- eso queda para la tolerancia puntual de la ÚLTIMA
    línea únicamente."""


@dataclass
class LogEntry:
    seq: int
    timestamp: str
    op: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str
    signature: str

    def to_dict(self) -> dict:
        return {
            "seq": self.seq, "timestamp": self.timestamp, "op": self.op, "payload": self.payload,
            "prev_hash": self.prev_hash, "entry_hash": self.entry_hash, "signature": self.signature,
        }

    @staticmethod
    def from_dict(data: dict) -> "LogEntry":
        return LogEntry(**data)


@dataclass
class VerificationResult:
    ok: bool
    entries_checked: int
    broken_at_seq: int | None = None
    reason: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(seq: int, timestamp: str, op: str, payload: dict, prev_hash: str) -> bytes:
    """Serialización determinística (claves ordenadas, sin espacios extra)
    para que el hash/firma de una entrada sea siempre reproducible byte a
    byte a partir de sus campos -- json.dumps sin sort_keys podría variar el
    orden entre procesos/versiones de Python y romper la verificación por
    una diferencia que no es manipulación real."""
    content = {"seq": seq, "timestamp": timestamp, "op": op, "payload": payload, "prev_hash": prev_hash}
    return json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _entry_hash(seq: int, timestamp: str, op: str, payload: dict, prev_hash: str) -> str:
    return hashlib.sha256(_canonical_bytes(seq, timestamp, op, payload, prev_hash)).hexdigest()


def read_entries(log_path: str | Path) -> list[LogEntry]:
    """Bug real, grave, encontrado en testing adversarial (2026-08-13,
    "kill duro a mitad de un write"): un kill que interrumpe
    `append_entry` deja la última línea sin cerrar (JSON inválido) -- antes
    de este fix, CUALQUIER llamada futura que necesitara leer el log
    (incluida `append_entry` misma, vía `_last_entry`) reventaba con un
    `JSONDecodeError` crudo, dejando el CASO ENTERO inutilizable para
    siempre (ninguna escritura nueva podía completarse) hasta reparar el
    archivo a mano -- confirmado en vivo truncando una línea real y
    reintentando escribir. Solo la ÚLTIMA línea se tolera como "escritura
    interrumpida" (se ignora, sin borrar los bytes rotos del archivo -- la
    evidencia de la interrupción queda visible para quien audite a mano);
    una línea corrupta en cualquier OTRA posición es una señal mucho más
    seria (posible manipulación, no un simple corte) y sigue rompiendo
    fuerte con `CorruptedLogError`, nunca se salta en silencio."""
    log_path = Path(log_path)
    if not log_path.is_file():
        return []
    lines = [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    entries = []
    for i, line in enumerate(lines):
        try:
            entries.append(LogEntry.from_dict(json.loads(line)))
        except json.JSONDecodeError as exc:
            if i == len(lines) - 1:
                continue  # última línea, se trata como escritura interrumpida por un kill -- se ignora
            raise CorruptedLogError(
                f"Línea {i} de '{log_path}' no es JSON válido y NO es la última línea del archivo -- "
                "esto es una señal más seria que un kill a mitad de un write (que solo afectaría la última "
                "línea). Revisión manual necesaria antes de seguir usando este caso."
            ) from exc
    return entries


def _last_entry(log_path: Path) -> LogEntry | None:
    """Devuelve solo la ÚLTIMA entrada del log, sin leer/parsear el archivo
    entero -- `append_entry` solo necesita el seq/hash de la última entrada
    para encadenar la nueva, no la historia completa (eso es trabajo de
    `verify_chain`/`rebuild_from_log`, que sí necesitan todo).

    Bug real de performance encontrado en testing adversarial (2026-08-13):
    antes de este fix, `append_entry` llamaba a `read_entries` (lee y
    parsea CADA línea del archivo) en CADA escritura -- O(n²) en la
    cantidad de entradas del log de un caso. Combinado con el mismo tipo de
    bug en case_store.add_node (arreglado con `case_store.batch`), un log
    de servidor de 5000 líneas seguía tardando varios minutos incluso
    DESPUÉS de arreglar el batching de commits de git, porque el cuello de
    botella real se había movido acá. Lee desde el final del archivo en
    bloques (nunca todo de un saque) hasta tener una línea completa.

    Tolera UNA línea final corrupta (mismo motivo real que `read_entries`,
    ver su docstring -- kill duro a mitad de un write) probando la
    anteúltima línea como fallback antes de rendirse -- cubre el caso
    realista de una sola escritura interrumpida sin volver a leer el
    archivo entero."""
    if not log_path.is_file():
        return None
    with log_path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return None
        buf = b""
        pos = size
        chunk_size = 8192
        # hasta 3 saltos de línea reales -- necesitamos poder recuperar
        # hasta 2 líneas completas (la última Y la anteúltima, por si la
        # última está corrupta), no solo 1.
        while pos > 0 and buf.count(b"\n") < 3:
            read_size = min(chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            buf = f.read(read_size) + buf
    lines = [ln for ln in buf.splitlines() if ln.strip()]
    if not lines:
        return None
    for candidate in reversed(lines[-2:]):
        try:
            return LogEntry.from_dict(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return None  # última(s) línea(s) corrupta(s) -- se trata como si el log estuviera vacío (arranca de génesis)


def append_entry(log_path: str | Path, keys_dir: str | Path, op: str, payload: dict[str, Any]) -> LogEntry:
    # ensure_keypair es idempotente (no-op si ya existe) -- se llama acá,
    # no en cada caller por separado, para que CUALQUIER camino que termine
    # escribiendo al log (case_store.add_node/add_edge, o código futuro que
    # llame append_entry directo) funcione en una instalación nueva sin
    # necesitar un paso manual de "generar la clave" antes -- bug real
    # encontrado por los tests de tools/investigation.py.
    keys_module.ensure_keypair(keys_dir)

    log_path = Path(log_path)
    last = _last_entry(log_path)
    seq = last.seq + 1 if last else 0
    prev_hash = last.entry_hash if last else GENESIS_HASH
    timestamp = _now()

    entry_hash = _entry_hash(seq, timestamp, op, payload, prev_hash)
    private_key = keys_module.load_private_key(keys_dir)
    signature = keys_module.sign(private_key, bytes.fromhex(entry_hash))

    entry = LogEntry(
        seq=seq, timestamp=timestamp, op=op, payload=payload,
        prev_hash=prev_hash, entry_hash=entry_hash, signature=signature,
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        # Asegura que el archivo termine en '\n' ANTES de escribir la
        # entrada nueva -- bug real encontrado en testing adversarial
        # (2026-08-13, "kill duro a mitad de un write"): un kill que
        # interrumpe un write() dejaba la última línea sin cerrar, y sin
        # este chequeo la entrada NUEVA (perfectamente válida en sí misma)
        # quedaba pegada directo al final de esa línea rota, sin
        # separador, formando una sola línea inválida -- la entrada nueva
        # se perdía en silencio junto con la vieja. Confirmado en vivo con
        # el mismo patrón en app/tools/reflect.py, arreglado ahí primero.
        if log_path.stat().st_size > 0:
            with log_path.open("rb") as check:
                check.seek(-1, 2)
                if check.read(1) != b"\n":
                    f.write("\n")
        f.write(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")
    return entry


def verify_chain(log_path: str | Path, keys_dir: str | Path) -> VerificationResult:
    """Recorre TODA la cadena desde el génesis y confirma, para cada
    entrada: (1) el hash declarado coincide con el que se recalcula de sus
    propios campos, (2) prev_hash coincide con el entry_hash real de la
    entrada anterior, (3) la firma es válida contra la clave pública. Corta
    en la PRIMERA falla y dice exactamente dónde -- no sigue verificando
    entradas posteriores a una ya rota (no tiene sentido: si la entrada N
    está manipulada, cualquier cosa que "encadene bien" después de ahí fue
    reconstruida por quien la manipuló, no es señal de nada).

    Nunca lanza una excepción -- ver docstring de `read_entries`: una línea
    corrupta que no es la última línea del archivo (bug real de testing
    adversarial 2026-08-13) tira `CorruptedLogError`, que acá se atrapa y
    se reporta como un `VerificationResult(ok=False, ...)` más, no como un
    crash -- mismo contrato que el resto de las fallas que detecta esta
    función (payload manipulado, entrada borrada, firma falsa)."""
    try:
        entries = read_entries(log_path)
    except CorruptedLogError as exc:
        return VerificationResult(ok=False, entries_checked=0, reason=str(exc))
    public_key = keys_module.load_public_key(keys_dir)

    expected_prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        if entry.seq != i:
            return VerificationResult(ok=False, entries_checked=i, broken_at_seq=entry.seq, reason=f"seq fuera de orden: esperaba {i}, encontró {entry.seq}")
        if entry.prev_hash != expected_prev:
            return VerificationResult(ok=False, entries_checked=i, broken_at_seq=entry.seq, reason="prev_hash no coincide con el entry_hash real de la entrada anterior -- cadena rota")

        recomputed_hash = _entry_hash(entry.seq, entry.timestamp, entry.op, entry.payload, entry.prev_hash)
        if recomputed_hash != entry.entry_hash:
            return VerificationResult(ok=False, entries_checked=i, broken_at_seq=entry.seq, reason="entry_hash no coincide con el contenido real de la entrada -- fue modificada")

        if not keys_module.verify(public_key, bytes.fromhex(entry.entry_hash), entry.signature):
            return VerificationResult(ok=False, entries_checked=i, broken_at_seq=entry.seq, reason="firma inválida -- la entrada no fue escrita con la clave privada real")

        expected_prev = entry.entry_hash

    return VerificationResult(ok=True, entries_checked=len(entries))
