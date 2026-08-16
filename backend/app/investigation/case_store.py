"""Almacén del estado ACTUAL de un caso de investigación -- nodos y aristas
vigentes, en un directorio propio por caso, versionado con git (spec sección
6: "Versionado del estado del caso con git, reusando el mecanismo de commits
que ya tenés").

Diferencia real con el log append-only (app/investigation/log.py): el log es
la fuente de verdad histórica/forense y NUNCA se reescribe una línea ya
escrita. Esto en cambio es una vista MATERIALIZADA del estado actual --
`nodes.jsonl`/`edges.jsonl` SÍ se reescriben completos en una retracción
(quedan reflejando "cómo está el caso ahora", no "qué pasó"). Esto es seguro
precisamente PORQUE es reconstruible desde cero repasando el log -- ver
`rebuild_from_log`, que es la prueba real del criterio de aceptación de la
spec ("el caso completo se puede reconstruir desde cero a partir de los
artefactos originales y el log").

Cada operación real queda en DOS lugares a la vez: una entrada nueva en el
log firmado (permanente) y el archivo de estado correspondiente actualizado
+ commiteado a git -- redundancia a propósito, no duplicación porque sí: git
da revisión humana fácil (`git log`/`git diff` de un caso cualquiera),
mientras que el log da tamper-evidence criptográfica real."""

from __future__ import annotations

import contextlib
import contextvars
import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import log as log_module
from .models import DerivadaPor, Edge, EdgeType, Node, NodeType


class CaseAlreadyExistsError(FileExistsError):
    pass


class CaseNotFoundError(FileNotFoundError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_dir_for(cases_dir: str | Path, case_id: str) -> Path:
    return Path(cases_dir) / case_id


def _git(case_dir: Path, *args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(case_dir), *args], capture_output=True, text=True, timeout=timeout)


def _git_commit(case_dir: Path, files: list[str], message: str) -> str | None:
    """Commitea SOLO `files` (pathspecs puntuales, nunca `git add -A`) --
    mismo criterio que app/codeedit/fixer.py::_git_commit_file, extendido a
    poder commitear varios archivos relacionados (ej. nodes.jsonl +
    log.jsonl) en un solo commit atómico por operación."""
    add = _git(case_dir, "add", "--", *files)
    if add.returncode != 0:
        return None
    commit = _git(case_dir, "commit", "-m", message, "--", *files)
    if commit.returncode != 0:
        return None
    rev = _git(case_dir, "rev-parse", "--short", "HEAD")
    return rev.stdout.strip() if rev.returncode == 0 else None


_case_locks: dict[str, threading.RLock] = {}
_case_locks_guard = threading.Lock()


def _lock_for(cases_dir: str | Path, case_id: str) -> threading.RLock:
    """Un RLock real por caso (no global -- dos casos distintos pueden
    escribirse en paralelo sin pisarse, solo el MISMO caso se serializa).
    RLock (no Lock) a propósito: `batch` mantiene el lock agarrado durante
    todo el bloque, y `add_node`/`add_edge` llamados adentro necesitan
    poder re-adquirirlo desde el mismo thread sin bloquearse a sí mismos.

    Bug real, serio, encontrado en testing adversarial (2026-08-13, "múltiples
    ingestas simultáneas al mismo caso"): sin ningún lock, `add_node` hace un
    read-check-write real (leer nodes.jsonl, chequear si el id ya existe,
    recién ahí escribir) -- una carrera de threads real (20 threads
    creando el MISMO nodo a la vez) confirmó DOS fallas graves a la vez:
    (1) el chequeo de idempotencia se pisaba (10 nodos duplicados creados
    en vez de 1), y (2) MUCHO más grave, el LOG FIRMADO quedaba corrupto
    (`verify_chain` fallaba real, "seq fuera de orden") -- dos threads
    escribiendo `log.append_entry` a la vez podían leer el mismo
    "última entrada" y escribir dos entradas con el mismo seq/prev_hash,
    rompiendo la cadena de integridad que es la base de todo el módulo."""
    key = str(case_dir_for(cases_dir, case_id).resolve())
    with _case_locks_guard:
        if key not in _case_locks:
            _case_locks[key] = threading.RLock()
        return _case_locks[key]


_batch_state: contextvars.ContextVar[dict | None] = contextvars.ContextVar("_case_store_batch_state", default=None)


@contextlib.contextmanager
def batch(cases_dir: str | Path, keys_dir: str | Path, case_id: str, message: str):
    """Agrupa TODAS las escrituras de nodos/aristas hechas por `add_node`/
    `add_edge` dentro del bloque en UN SOLO commit de git al final, en vez
    de uno por operación -- necesario para archivos grandes. Bug real de
    performance encontrado en testing adversarial (2026-08-13, ver
    docstring de `ingest_server_log`): sin este batching, cada add_node/
    add_edge spawneaba 2-3 subprocess de git (`add`, `commit`, `rev-parse`)
    -- un log de servidor de 50.000 líneas medía ~320ms/línea reales
    (~4.4 horas proyectadas), casi todo overhead de proceso, no trabajo
    real.

    El log firmado (log.jsonl, la fuente de verdad forense real, ver
    docstring del módulo) NO se ve afectado por esto -- sigue escribiéndose
    entrada por entrada exactamente igual, con la misma cadena de hashes.
    Esto solo agrupa el commit de git, que es una capa de conveniencia/
    legibilidad humana (`git log`/`git diff`), no el mecanismo de
    integridad -- agrupar mil escrituras en un commit no pierde ninguna
    granularidad que no siga estando, completa, en el log.

    También evita releer nodes.jsonl entero (y escanearlo linealmente
    buscando el id) en CADA llamada a add_node -- ver `_node_index`: dentro
    de un batch, el índice de ids se construye una sola vez y se mantiene
    en memoria, no es O(n²) en la cantidad de nodos ingestados.

    Tradeoff real y CONOCIDO, verificado en vivo con un kill duro real de
    proceso a mitad de un batch de 2000 nodos (2026-08-13, "matar el
    proceso durante un commit de case_store"): los datos NUNCA se pierden
    ni se corrompen (log firmado íntegro y reconstruible, nodes.jsonl con
    exactamente lo escrito hasta el momento del kill) -- pero git se queda
    atrás, sin ningún commit para lo escrito en el batch interrumpido,
    hasta la PRÓXIMA escritura real al caso (que sí "atrapa" todo lo
    pendiente en su propio commit, confirmado real: el commit siguiente
    incluyó los 1001 nodos huérfanos + el nuevo). Si un caso interrumpido
    a mitad de un batch nunca se vuelve a tocar, `git log`/`git diff` de
    ESE caso puntual quedarían desactualizados para siempre -- un vistazo
    con git solo, sin pasar por la app, subestimaría el contenido real.
    Aceptado a propósito: un kill duro (o corte de luz) no se puede
    interceptar de forma confiable a nivel de aplicación de ningún modo
    (ni con handlers de señal), así que la garantía real que importa es la
    del log firmado, no la de git -- y esa se sostiene siempre.

    Mantiene el lock del caso (ver `_lock_for`) agarrado durante TODO el
    bloque -- una ingesta grande completa es una sola unidad atómica real
    frente a otra ingesta concurrente del mismo caso, no una serie de
    operaciones sueltas que otro proceso podría intercalar."""
    case_dir = case_dir_for(cases_dir, case_id)
    with _lock_for(cases_dir, case_id):
        state = {"files": set(), "node_index": None}
        token = _batch_state.set(state)
        try:
            yield
        finally:
            _batch_state.reset(token)
            if state["files"]:
                _git_commit(case_dir, sorted(state["files"]), message)


def _node_index(cases_dir: str | Path, case_id: str, state: dict) -> dict[str, Node]:
    if state["node_index"] is None:
        state["node_index"] = {n.id: n for n in read_nodes(cases_dir, case_id)}
    return state["node_index"]


def create_case(cases_dir: str | Path, case_id: str, titulo: str) -> dict:
    case_dir = case_dir_for(cases_dir, case_id)
    if case_dir.exists():
        raise CaseAlreadyExistsError(f"El caso '{case_id}' ya existe en '{case_dir}'")

    case_dir.mkdir(parents=True)
    (case_dir / "nodes.jsonl").write_text("", encoding="utf-8")
    (case_dir / "edges.jsonl").write_text("", encoding="utf-8")
    (case_dir / "column_mappings").mkdir()

    case_info = {"id": case_id, "titulo": titulo, "created_at": _now()}
    (case_dir / "case.json").write_text(json.dumps(case_info, ensure_ascii=False, indent=2), encoding="utf-8")

    init = _git(case_dir, "init", "-q")
    if init.returncode != 0:
        raise RuntimeError(f"No se pudo inicializar git en '{case_dir}': {init.stderr}")
    _git_commit(case_dir, ["case.json", "nodes.jsonl", "edges.jsonl"], f"Caso creado: {titulo}")
    return case_info


def _append_jsonl(path: Path, data: dict) -> None:
    """Asegura que el archivo termine en '\\n' ANTES de escribir la entrada
    nueva -- mismo bug real y mismo fix que app/investigation/log.py::
    append_entry (ver su docstring): un kill duro a mitad de un write deja
    la última línea sin cerrar, y sin este chequeo la entrada nueva
    quedaría pegada a esa línea rota, formando una sola línea inválida que
    se pierde en silencio junto con la vieja."""
    with path.open("a", encoding="utf-8") as f:
        if path.stat().st_size > 0:
            with path.open("rb") as check:
                check.seek(-1, 2)
                if check.read(1) != b"\n":
                    f.write("\n")
        f.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    """Tolera UNA línea final corrupta (mismo motivo real que
    app/investigation/log.py::read_entries, ver su docstring -- kill duro a
    mitad de un write) -- nodes.jsonl/edges.jsonl son vistas MATERIALIZADAS
    reconstruibles desde el log (ver docstring del módulo), así que una
    línea corrupta que NO es la última es igual de seria que en el log
    real: se rompe fuerte en vez de saltearla en silencio."""
    if not path.is_file():
        return []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    records = []
    for i, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            if i == len(lines) - 1:
                continue  # última línea, se trata como escritura interrumpida por un kill -- se ignora
            raise ValueError(
                f"Línea {i} de '{path}' no es JSON válido y NO es la última línea del archivo -- señal más "
                "seria que un kill a mitad de un write. Revisión manual necesaria, o reconstruir el caso "
                "desde el log con rebuild_from_log."
            ) from exc
    return records


def _rewrite_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records), encoding="utf-8"
    )


def read_nodes(cases_dir: str | Path, case_id: str) -> list[Node]:
    case_dir = case_dir_for(cases_dir, case_id)
    return [Node.from_dict(d) for d in _read_jsonl(case_dir / "nodes.jsonl")]


def read_edges(cases_dir: str | Path, case_id: str) -> list[Edge]:
    case_dir = case_dir_for(cases_dir, case_id)
    return [Edge.from_dict(d) for d in _read_jsonl(case_dir / "edges.jsonl")]


def add_node(cases_dir: str | Path, keys_dir: str | Path, case_id: str, node: Node) -> Node:
    """Idempotente por id -- necesario porque los nodos con clave natural
    (Archivo por su sha256, Cuenta por plataforma+handle, Host por ip/
    dominio, ver models.py) pueden volver a construirse con el MISMO id en
    una reingesta incremental (ej. el nodo Archivo que representa un CSV
    ingestado hace referencia el mismo archivo en cada carga posterior) --
    sin este chequeo, cada reingesta duplicaría la entrada en nodes.jsonl y
    generaría una entrada de log redundante para algo que ya existe.

    Serializado con `_lock_for` -- bug real, grave, encontrado en testing
    adversarial (2026-08-13, ver docstring de `_lock_for`): sin el lock, el
    read-check-write de este chequeo de idempotencia tenía una carrera real
    bajo llamadas concurrentes (20 threads creando el mismo nodo a la vez
    producían 10 duplicados Y corrompían el log firmado)."""
    case_dir = case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise CaseNotFoundError(f"El caso '{case_id}' no existe")

    with _lock_for(cases_dir, case_id):
        state = _batch_state.get()
        if state is not None:
            index = _node_index(cases_dir, case_id, state)
            existing = index.get(node.id)
            if existing is not None:
                return existing
            log_module.append_entry(case_dir / "log.jsonl", keys_dir, op="create_node", payload=node.to_dict())
            _append_jsonl(case_dir / "nodes.jsonl", node.to_dict())
            index[node.id] = node
            state["files"].update(["nodes.jsonl", "log.jsonl"])
            return node

        existing = next((n for n in read_nodes(cases_dir, case_id) if n.id == node.id), None)
        if existing is not None:
            return existing

        log_module.append_entry(case_dir / "log.jsonl", keys_dir, op="create_node", payload=node.to_dict())
        _append_jsonl(case_dir / "nodes.jsonl", node.to_dict())
        _git_commit(case_dir, ["nodes.jsonl", "log.jsonl"], f"create_node: {node.tipo.value} {node.id}")
        return node


def add_edge(cases_dir: str | Path, keys_dir: str | Path, case_id: str, edge: Edge) -> Edge:
    """Bug real encontrado en testing adversarial (2026-08-13): antes de
    este chequeo, una arista podía crearse apuntando a ids de nodo que
    NUNCA existieron en el caso -- quedaba persistida en edges.jsonl y en
    el log firmado sin ningún error, una arista huérfana real (confirmado
    con un test directo: `add_edge` con dos ids inventados no fallaba).
    Se valida acá, en el único punto de entrada real para crear aristas
    (todos los parsers y `fusion.confirm_fusion` pasan por acá), en vez de
    en cada caller por separado. Serializado con `_lock_for`, mismo motivo
    real que `add_node` (ver su docstring)."""
    case_dir = case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise CaseNotFoundError(f"El caso '{case_id}' no existe")

    with _lock_for(cases_dir, case_id):
        state = _batch_state.get()
        known_ids = _node_index(cases_dir, case_id, state) if state is not None else {n.id: n for n in read_nodes(cases_dir, case_id)}
        missing = [node_id for node_id in (edge.origen, edge.destino) if node_id not in known_ids]
        if missing:
            raise ValueError(
                f"No se puede crear la arista '{edge.tipo.value}': el/los nodo(s) {missing} no existen en el "
                f"caso '{case_id}' -- una arista solo puede conectar nodos ya creados."
            )

        log_module.append_entry(case_dir / "log.jsonl", keys_dir, op="create_edge", payload=edge.to_dict())
        _append_jsonl(case_dir / "edges.jsonl", edge.to_dict())

        if state is not None:
            state["files"].update(["edges.jsonl", "log.jsonl"])
            return edge

        _git_commit(case_dir, ["edges.jsonl", "log.jsonl"], f"create_edge: {edge.tipo.value} {edge.origen}->{edge.destino}")
        return edge


def retract_node(cases_dir: str | Path, keys_dir: str | Path, case_id: str, node_id: str, reason: str) -> Node:
    """Serializado con `_lock_for`, mismo motivo real que `add_node` (ver
    su docstring) -- este también hace un read-modify-write real sobre
    nodes.jsonl/log.jsonl."""
    case_dir = case_dir_for(cases_dir, case_id)
    with _lock_for(cases_dir, case_id):
        nodes = read_nodes(cases_dir, case_id)
        target = next((n for n in nodes if n.id == node_id), None)
        if target is None:
            raise ValueError(f"No existe el nodo '{node_id}' en el caso '{case_id}'")

        # Un solo timestamp para AMBOS lugares (el nodo y la entrada del log) --
        # ver Node.retract()/rebuild_from_log: si cada uno tomara "ahora" por su
        # cuenta, reconstruir desde el log daría un retracted_at distinto al
        # real (bug real encontrado por el test de reconstrucción).
        at = _now()
        target.retract(reason, at=at)
        log_module.append_entry(
            case_dir / "log.jsonl", keys_dir, op="retract_node", payload={"id": node_id, "reason": reason, "at": at}
        )
        _rewrite_jsonl(case_dir / "nodes.jsonl", [n.to_dict() for n in nodes])
        _git_commit(case_dir, ["nodes.jsonl", "log.jsonl"], f"retract_node: {node_id} ({reason})")
        return target


def retract_edge(cases_dir: str | Path, keys_dir: str | Path, case_id: str, edge_id: str, reason: str) -> Edge:
    """Retractar una arista `mismo_que` NUNCA toca los nodos que vinculaba
    (decisión de Damian, 2026-08-12) -- por diseño, esta función solo lee/
    reescribe edges.jsonl, jamás nodes.jsonl. Serializado con `_lock_for`,
    mismo motivo real que `add_node`."""
    case_dir = case_dir_for(cases_dir, case_id)
    with _lock_for(cases_dir, case_id):
        edges = read_edges(cases_dir, case_id)
        target = next((e for e in edges if e.id == edge_id), None)
        if target is None:
            raise ValueError(f"No existe la arista '{edge_id}' en el caso '{case_id}'")

        at = _now()  # ver retract_node -- mismo motivo real para fijar un solo timestamp
        target.retract(reason, at=at)
        log_module.append_entry(
            case_dir / "log.jsonl", keys_dir, op="retract_edge", payload={"id": edge_id, "reason": reason, "at": at}
        )
        _rewrite_jsonl(case_dir / "edges.jsonl", [e.to_dict() for e in edges])
        _git_commit(case_dir, ["edges.jsonl", "log.jsonl"], f"retract_edge: {edge_id} ({reason})")
        return target


def rebuild_from_log(cases_dir: str | Path, keys_dir: str | Path, case_id: str) -> tuple[list[Node], list[Edge]]:
    """Reconstruye nodos/aristas DESDE CERO repasando el log entero, sin
    leer nodes.jsonl/edges.jsonl para nada -- esta es la prueba real de que
    el caso es reconstruible a partir del log solo (criterio de aceptación
    de la spec). Verifica la cadena ANTES de confiar en ella: reconstruir a
    partir de un log manipulado sin darse cuenta sería peor que no
    reconstruir nada."""
    case_dir = case_dir_for(cases_dir, case_id)
    log_path = case_dir / "log.jsonl"

    verification = log_module.verify_chain(log_path, keys_dir)
    if not verification.ok:
        raise ValueError(
            f"No se puede reconstruir: el log está corrupto en seq={verification.broken_at_seq} "
            f"({verification.reason})"
        )

    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    for entry in log_module.read_entries(log_path):
        if entry.op == "create_node":
            node = Node.from_dict(entry.payload)
            nodes[node.id] = node
        elif entry.op == "create_edge":
            edge = Edge.from_dict(entry.payload)
            edges[edge.id] = edge
        elif entry.op == "retract_node":
            node_id = entry.payload["id"]
            if node_id in nodes:
                nodes[node_id].retract(entry.payload["reason"], at=entry.payload["at"])
        elif entry.op == "retract_edge":
            edge_id = entry.payload["id"]
            if edge_id in edges:
                edges[edge_id].retract(entry.payload["reason"], at=entry.payload["at"])
        # "ingest_artifact" y otros ops no representan nodos/aristas -- se
        # ignoran acá a propósito, quedan solo como evidencia en el log.

    return list(nodes.values()), list(edges.values())
