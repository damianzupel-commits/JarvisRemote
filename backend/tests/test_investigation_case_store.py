"""Tests de app/investigation/case_store.py -- git real (no mockeado, mismo
criterio que test_filesystem_audit.py/test_opencode_tool.py con subprocesos
reales), y la prueba real del criterio de aceptación de la spec:
reconstrucción completa del caso desde cero a partir del log."""

from __future__ import annotations

import threading

import pytest

from app.investigation import case_store, keys, models
from app.investigation import log as log_module


@pytest.fixture()
def keys_dir(tmp_path):
    d = tmp_path / "keys"
    keys.ensure_keypair(d)
    return d


@pytest.fixture()
def cases_dir(tmp_path):
    return tmp_path / "cases"


def test_create_case_creates_a_real_git_repo(cases_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    assert (case_dir / ".git").is_dir()
    assert (case_dir / "case.json").is_file()
    assert (case_dir / "nodes.jsonl").is_file()
    assert (case_dir / "edges.jsonl").is_file()


def test_create_case_makes_an_initial_real_commit(cases_dir):
    import subprocess

    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    case_dir = case_store.case_dir_for(cases_dir, "caso-1")

    log = subprocess.run(["git", "-C", str(case_dir), "log", "--oneline"], capture_output=True, text=True)
    assert "Caso creado" in log.stdout


def test_create_case_raises_if_case_already_exists(cases_dir):
    case_store.create_case(cases_dir, "caso-1", "Primero")

    with pytest.raises(case_store.CaseAlreadyExistsError):
        case_store.create_case(cases_dir, "caso-1", "Segundo")


def test_add_node_persists_and_commits(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    node = models.make_persona(etiqueta="Test", confianza=0.5)

    case_store.add_node(cases_dir, keys_dir, "caso-1", node)

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len(nodes) == 1
    assert nodes[0].id == node.id


def test_add_node_raises_for_unknown_case(cases_dir, keys_dir):
    node = models.make_persona(etiqueta="Test", confianza=0.5)
    with pytest.raises(case_store.CaseNotFoundError):
        case_store.add_node(cases_dir, keys_dir, "no-existe", node)


def test_add_edge_persists_and_commits(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    persona = models.make_persona(etiqueta="a", confianza=0.5)
    cuenta = models.make_cuenta(plataforma="x", handle="@a")
    case_store.add_node(cases_dir, keys_dir, "caso-1", persona)
    case_store.add_node(cases_dir, keys_dir, "caso-1", cuenta)
    edge = models.make_edge(
        tipo=models.EdgeType.USA, origen=persona.id, destino=cuenta.id,
        artefacto_origen="manual", confianza=0.9, derivada_por=models.DerivadaPor.MANUAL,
    )

    case_store.add_edge(cases_dir, keys_dir, "caso-1", edge)

    edges = case_store.read_edges(cases_dir, "caso-1")
    assert len(edges) == 1
    assert edges[0].origen == persona.id


def test_add_edge_rejects_a_reference_to_a_nonexistent_node(cases_dir, keys_dir):
    """Bug real encontrado en testing adversarial (2026-08-13): antes de
    este chequeo, una arista con ids inventados quedaba persistida sin
    ningún error -- una arista huérfana real en el grafo."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    edge = models.make_edge(
        tipo=models.EdgeType.USA, origen="nodo-fantasma-a", destino="nodo-fantasma-b",
        artefacto_origen="manual", confianza=0.9, derivada_por=models.DerivadaPor.MANUAL,
    )

    with pytest.raises(ValueError, match="no existen en el caso"):
        case_store.add_edge(cases_dir, keys_dir, "caso-1", edge)

    assert case_store.read_edges(cases_dir, "caso-1") == []


def test_add_edge_rejects_when_only_one_endpoint_exists(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    persona = models.make_persona(etiqueta="a", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", persona)
    edge = models.make_edge(
        tipo=models.EdgeType.USA, origen=persona.id, destino="nodo-fantasma",
        artefacto_origen="manual", confianza=0.9, derivada_por=models.DerivadaPor.MANUAL,
    )

    with pytest.raises(ValueError, match="no existen en el caso"):
        case_store.add_edge(cases_dir, keys_dir, "caso-1", edge)


# --- case_store.batch: fix real de performance (2026-08-13) ---------------------------

def test_batch_makes_a_single_commit_for_many_nodes(cases_dir, keys_dir):
    import subprocess

    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    case_dir = case_store.case_dir_for(cases_dir, "caso-1")

    with case_store.batch(cases_dir, keys_dir, "caso-1", "ingesta de prueba"):
        for i in range(10):
            case_store.add_node(cases_dir, keys_dir, "caso-1", models.make_persona(etiqueta=f"p{i}", confianza=0.5))

    log = subprocess.run(["git", "-C", str(case_dir), "log", "--oneline"], capture_output=True, text=True)
    # 1 commit de create_case + 1 solo commit para las 10 escrituras del batch (no 10 commits sueltos)
    assert len(log.stdout.strip().splitlines()) == 2
    assert "ingesta de prueba" in log.stdout


def test_batch_still_persists_every_node_and_the_signed_log_stays_intact(cases_dir, keys_dir):
    """El batching agrupa el commit de git -- NO debería afectar en nada al
    log firmado (la fuente de verdad forense real, ver docstring del
    módulo): sigue teniendo una entrada real por nodo, con su cadena de
    hashes intacta."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")

    with case_store.batch(cases_dir, keys_dir, "caso-1", "ingesta de prueba"):
        for i in range(10):
            case_store.add_node(cases_dir, keys_dir, "caso-1", models.make_persona(etiqueta=f"p{i}", confianza=0.5))

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len(nodes) == 10

    nodes_rebuilt, _ = case_store.rebuild_from_log(cases_dir, keys_dir, "caso-1")
    assert {n.id for n in nodes_rebuilt} == {n.id for n in nodes}


def test_batch_deduplicates_nodes_by_id_using_the_in_memory_index(cases_dir, keys_dir):
    """Mismo criterio de idempotencia de add_node fuera de un batch (ver su
    docstring), pero acá el chequeo tiene que resolverse contra el índice
    en memoria del batch, no releyendo nodes.jsonl en cada llamada."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    cuenta = models.make_cuenta(plataforma="x", handle="@a")

    with case_store.batch(cases_dir, keys_dir, "caso-1", "ingesta de prueba"):
        first = case_store.add_node(cases_dir, keys_dir, "caso-1", cuenta)
        second = case_store.add_node(cases_dir, keys_dir, "caso-1", models.make_cuenta(plataforma="x", handle="@a"))

    assert first.id == second.id
    assert len(case_store.read_nodes(cases_dir, "caso-1")) == 1


def test_add_edge_inside_a_batch_still_validates_node_existence(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")

    with pytest.raises(ValueError, match="no existen en el caso"):
        with case_store.batch(cases_dir, keys_dir, "caso-1", "ingesta de prueba"):
            edge = models.make_edge(
                tipo=models.EdgeType.USA, origen="nodo-fantasma-a", destino="nodo-fantasma-b",
                artefacto_origen="manual", confianza=0.9, derivada_por=models.DerivadaPor.MANUAL,
            )
            case_store.add_edge(cases_dir, keys_dir, "caso-1", edge)


# --- _lock_for: bug real de concurrencia, grave (2026-08-13) -------------------------

def test_concurrent_add_node_for_the_same_natural_key_creates_only_one_node(cases_dir, keys_dir):
    """Bug real, grave, encontrado en testing adversarial ("múltiples
    ingestas simultáneas al mismo caso"): sin lock, 20 threads creando el
    MISMO nodo a la vez producían 10 duplicados reales -- confirmado en
    vivo antes de este fix. El chequeo de idempotencia de add_node
    (read-check-write) tenía una carrera de verdad."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")

    def worker():
        case_store.add_node(cases_dir, keys_dir, "caso-1", models.make_cuenta(plataforma="x", handle="@mismo"))

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len(nodes) == 1


def test_concurrent_add_node_for_the_same_natural_key_keeps_the_signed_log_valid(cases_dir, keys_dir):
    """Mismo escenario que el test anterior, pero verificando la falla MÁS
    grave que la carrera producía: antes de este fix, `verify_chain`
    fallaba de verdad después de la carrera ("seq fuera de orden") -- el
    log firmado, la fuente de verdad forense, quedaba corrupto."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")

    def worker():
        case_store.add_node(cases_dir, keys_dir, "caso-1", models.make_cuenta(plataforma="x", handle="@mismo"))

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result = log_module.verify_chain(case_store.case_dir_for(cases_dir, "caso-1") / "log.jsonl", keys_dir)
    assert result.ok is True


def test_concurrent_add_node_for_different_nodes_creates_all_of_them(cases_dir, keys_dir):
    """El lock serializa el MISMO caso, pero no debería perder ni un solo
    nodo legítimo cuando la concurrencia es real (nodos DISTINTOS, no una
    carrera por el mismo id)."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")

    def worker(i):
        case_store.add_node(cases_dir, keys_dir, "caso-1", models.make_cuenta(plataforma="x", handle=f"@user{i}"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len(nodes) == 30
    result = log_module.verify_chain(case_store.case_dir_for(cases_dir, "caso-1") / "log.jsonl", keys_dir)
    assert result.ok is True


def test_retract_node_marks_it_without_deleting(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    node = models.make_persona(etiqueta="Test", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", node)

    case_store.retract_node(cases_dir, keys_dir, "caso-1", node.id, "identidad incorrecta")

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len(nodes) == 1  # sigue estando, no desapareció
    assert nodes[0].retracted is True
    assert nodes[0].retracted_reason == "identidad incorrecta"


def test_retract_edge_never_touches_the_underlying_nodes(cases_dir, keys_dir):
    """Decisión de Damian: mismo_que nunca combina nodos, retractar la
    fusión no puede tocarlos."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    persona_a = models.make_persona(etiqueta="a", confianza=0.5)
    persona_b = models.make_persona(etiqueta="b", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", persona_a)
    case_store.add_node(cases_dir, keys_dir, "caso-1", persona_b)
    fusion = models.make_edge(
        tipo=models.EdgeType.MISMO_QUE, origen=persona_a.id, destino=persona_b.id,
        artefacto_origen="manual", confianza=1.0, derivada_por=models.DerivadaPor.MANUAL,
    )
    case_store.add_edge(cases_dir, keys_dir, "caso-1", fusion)

    case_store.retract_edge(cases_dir, keys_dir, "caso-1", fusion.id, "eran personas distintas")

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len(nodes) == 2
    assert all(not n.retracted for n in nodes)  # los nodos JAMAS se tocaron
    edges = case_store.read_edges(cases_dir, "caso-1")
    assert edges[0].retracted is True


def test_rebuild_from_log_exactly_matches_the_materialized_state(cases_dir, keys_dir):
    """Prueba real del criterio de aceptación de la spec: 'el caso completo
    se puede reconstruir desde cero a partir de los artefactos originales y
    el log' -- reconstruye SOLO desde el log (sin leer nodes.jsonl/
    edges.jsonl) y confirma que coincide exactamente con el estado
    materializado real."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    persona = models.make_persona(etiqueta="a", confianza=0.5)
    cuenta = models.make_cuenta(plataforma="x", handle="@a")
    case_store.add_node(cases_dir, keys_dir, "caso-1", persona)
    case_store.add_node(cases_dir, keys_dir, "caso-1", cuenta)
    edge = models.make_edge(
        tipo=models.EdgeType.USA, origen=persona.id, destino=cuenta.id,
        artefacto_origen="manual", confianza=0.9, derivada_por=models.DerivadaPor.MANUAL,
    )
    case_store.add_edge(cases_dir, keys_dir, "caso-1", edge)
    case_store.retract_node(cases_dir, keys_dir, "caso-1", cuenta.id, "cuenta dada de baja")

    rebuilt_nodes, rebuilt_edges = case_store.rebuild_from_log(cases_dir, keys_dir, "caso-1")
    real_nodes = case_store.read_nodes(cases_dir, "caso-1")
    real_edges = case_store.read_edges(cases_dir, "caso-1")

    assert {n.id: n.to_dict() for n in rebuilt_nodes} == {n.id: n.to_dict() for n in real_nodes}
    assert {e.id: e.to_dict() for e in rebuilt_edges} == {e.id: e.to_dict() for e in real_edges}
    # Confirma explícitamente que la retracción sobrevivió la reconstrucción
    rebuilt_cuenta = next(n for n in rebuilt_nodes if n.id == cuenta.id)
    assert rebuilt_cuenta.retracted is True


def test_rebuild_from_log_refuses_a_tampered_log(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    node = models.make_persona(etiqueta="a", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", node)

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    log_path = case_dir / "log.jsonl"
    import json

    lines = log_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["payload"]["campos"]["confianza"] = 0.99
    log_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupto"):
        case_store.rebuild_from_log(cases_dir, keys_dir, "caso-1")


# --- recuperación de una escritura interrumpida en nodes.jsonl/edges.jsonl (2026-08-13) ---

def test_add_node_recovers_cleanly_after_a_truncated_final_line_in_nodes_jsonl(cases_dir, keys_dir):
    """Bug real, mismo patrón que app/investigation/log.py (ver su
    docstring, 'kill duro a mitad de un write'): antes de este fix, una
    línea truncada al final de nodes.jsonl hacía que la SIGUIENTE
    add_node quedara pegada a esa línea rota, sin separador -- se perdían
    ambas (la vieja truncada Y la nueva, perfectamente válida). Lo
    importante acá es que add_node NO revienta -- que read_nodes() vuelva
    a marcar la línea rota una vez que queda en el medio es el mismo
    comportamiento deliberado de log.py (ver ese test), no un bug."""
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    first = models.make_persona(etiqueta="primera", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", first)

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    nodes_path = case_dir / "nodes.jsonl"
    with nodes_path.open("a", encoding="utf-8") as f:
        f.write('{"id": "roto", "tipo": "Persona", "campos": {"truncado')  # sin '\n' final -- kill duro real

    second = models.make_persona(etiqueta="segunda", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", second)  # no debe reventar -- eso es lo que se prueba acá

    # nodes.jsonl (la vista materializada) ahora tiene la línea rota en el
    # medio -- read_nodes() la marca a propósito (mismo motivo que log.py),
    # pero el LOG real nunca vio esa corrupción (se escribió directo al
    # .jsonl, no vía add_node) -- rebuild_from_log reconstruye limpio.
    nodes_rebuilt, _ = case_store.rebuild_from_log(cases_dir, keys_dir, "caso-1")
    assert {n.id for n in nodes_rebuilt} == {first.id, second.id}


def test_read_jsonl_raises_a_clear_error_for_corruption_that_is_not_the_last_line(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    first = models.make_persona(etiqueta="primera", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", first)

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    nodes_path = case_dir / "nodes.jsonl"
    with nodes_path.open("a", encoding="utf-8") as f:
        f.write('{"id": "roto", "tipo": "Persona", "campos": {"truncado')
    second = models.make_persona(etiqueta="segunda", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", second)  # ahora la línea rota queda en el medio

    with pytest.raises(ValueError, match="no es JSON"):
        case_store.read_nodes(cases_dir, "caso-1")
