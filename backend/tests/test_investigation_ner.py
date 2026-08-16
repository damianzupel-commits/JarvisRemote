"""Tests de app/investigation/ner.py -- paso 5 del orden de implementación
(spec sección 5, punto 1: NER asistido por modelo, en estado
pendiente-de-confirmación). El cliente del modelo se mockea (mismo criterio
que test_investigation_column_mapping.py); case_store/log corren reales
(git real, firma Ed25519 real), porque lo que importa validar acá es que
una propuesta NUNCA toca el grafo por sí sola y que confirmarla deja rastro
real y verificable."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.investigation import case_store, keys, log as log_module, ner
from app.investigation.models import DerivadaPor, NodeType, make_archivo


@pytest.fixture()
def keys_dir(tmp_path):
    d = tmp_path / "keys"
    keys.ensure_keypair(d)
    return d


@pytest.fixture()
def cases_dir(tmp_path):
    return tmp_path / "cases"


@pytest.fixture()
def archivo_id(cases_dir, keys_dir):
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    archivo = make_archivo(nombre="chat.txt", sha256="a" * 64, tamano=100, mime="text/plain")
    case_store.add_node(cases_dir, keys_dir, "caso-1", archivo)
    return archivo.id


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# --- propose_entities / parseo -------------------------------------------------


@pytest.mark.anyio
async def test_propose_entities_parses_valid_candidates(monkeypatch, archivo_id):
    payload = json.dumps([
        {
            "tipo": "Persona", "campos": {"etiqueta": "Juan Perez", "alias": [], "confianza": 0.7},
            "texto_fuente": "Juan Perez me escribió", "confianza_extraccion": 0.9, "razon": "nombre propio explícito",
        },
    ])

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("Juan Perez me escribió ayer", archivo_id)

    assert len(result.proposals) == 1
    assert result.discarded == []
    proposal = result.proposals[0]
    assert proposal.tipo == NodeType.PERSONA
    assert proposal.status == "pendiente"
    assert proposal.artefacto_origen == archivo_id
    assert proposal.confianza_extraccion == 0.9


@pytest.mark.anyio
async def test_propose_entities_discards_a_malformed_candidate_without_losing_the_rest(monkeypatch, archivo_id):
    payload = json.dumps([
        {"tipo": "Persona", "campos": {"etiqueta": "Juan"}, "texto_fuente": "Juan", "confianza_extraccion": 0.5, "razon": "x"},  # falta confianza/alias
        {"tipo": "Cuenta", "campos": {"plataforma": "telegram", "handle": "@juan"}, "texto_fuente": "@juan", "confianza_extraccion": 0.8, "razon": "x"},
    ])

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("texto", archivo_id)

    assert len(result.proposals) == 1
    assert result.proposals[0].tipo == NodeType.CUENTA
    assert len(result.discarded) == 1
    assert result.discarded[0]["candidate"]["campos"]["etiqueta"] == "Juan"


@pytest.mark.anyio
async def test_archivo_is_never_a_proposable_type(monkeypatch, archivo_id):
    """Regla dura del módulo: NER nunca propone un Archivo (su sha256 tiene
    que salir de un hash real, no de que el modelo lea un nombre en texto)."""
    payload = json.dumps([
        {"tipo": "Archivo", "campos": {"nombre": "x.txt", "sha256": "b" * 64, "tamano": 1, "mime": "text/plain"}, "texto_fuente": "x.txt", "confianza_extraccion": 0.9, "razon": "x"},
    ])

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("el archivo x.txt", archivo_id)

    assert result.proposals == []
    assert len(result.discarded) == 1


@pytest.mark.anyio
async def test_propose_entities_coerces_a_bare_string_into_a_list_field(monkeypatch, archivo_id):
    """Bug real encontrado corriendo esto contra el modelo real (2026-08-12):
    devolvió 'identificadores': '+54 9 11 5555-1234' (un string) en vez de
    una lista -- Dispositivo.identificadores es de tipo lista."""
    payload = json.dumps([
        {"tipo": "Dispositivo", "campos": {"tipo_dispositivo": "teléfono", "identificadores": "+54 9 11 5555-1234"}, "texto_fuente": "el telefono +54 9 11 5555-1234", "confianza_extraccion": 0.9, "razon": "x"},
    ])

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("texto", archivo_id)

    assert len(result.proposals) == 1
    assert result.proposals[0].campos["identificadores"] == ["+54 9 11 5555-1234"]


@pytest.mark.anyio
async def test_propose_entities_discards_a_required_field_left_null(monkeypatch, archivo_id):
    """Bug real encontrado corriendo esto contra el modelo real (2026-08-12):
    devolvió una Persona con 'etiqueta': null (el nombre puesto por error
    en 'alias' en cambio) -- la clave 'etiqueta' estaba presente pero sin
    valor real, models._validate_campos NO lo detecta (solo chequea que la
    clave exista), así que hace falta esta capa extra."""
    payload = json.dumps([
        {"tipo": "Persona", "campos": {"etiqueta": None, "alias": "Juan Perez", "confianza": 1}, "texto_fuente": "Juan Perez", "confianza_extraccion": 1.0, "razon": "x"},
    ])

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("Juan Perez dijo algo", archivo_id)

    assert result.proposals == []
    assert len(result.discarded) == 1
    assert "etiqueta" in result.discarded[0]["reason"]


@pytest.mark.anyio
async def test_propose_entities_allows_an_empty_alias_list_on_a_persona(monkeypatch, archivo_id):
    """alias=[] es un valor real y legítimo (persona sin apodos conocidos) --
    no debe descartarse como si fuera un campo requerido vacío."""
    payload = json.dumps([
        {"tipo": "Persona", "campos": {"etiqueta": "Juan Perez", "alias": [], "confianza": 0.8}, "texto_fuente": "Juan Perez", "confianza_extraccion": 0.9, "razon": "x"},
    ])

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("Juan Perez dijo algo", archivo_id)

    assert len(result.proposals) == 1
    assert result.discarded == []


@pytest.mark.anyio
async def test_propose_entities_raises_on_unparseable_response(monkeypatch, archivo_id):
    async def fake_create(**kwargs):
        return _fake_response("no encontré nada")

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    with pytest.raises(ValueError, match="array JSON"):
        await ner.propose_entities("texto", archivo_id)


@pytest.mark.anyio
async def test_propose_entities_returns_empty_list_for_no_entities(monkeypatch, archivo_id):
    async def fake_create(**kwargs):
        return _fake_response("[]")

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_create)

    result = await ner.propose_entities("texto sin entidades reconocibles", archivo_id)

    assert result.proposals == []
    assert result.discarded == []


# --- persistencia real ----------------------------------------------------------


def _sample_proposal(archivo_id: str) -> ner.EntityProposal:
    return ner.EntityProposal(
        id="prop-1", tipo=NodeType.PERSONA, campos={"etiqueta": "Juan", "alias": [], "confianza": 0.6},
        texto_fuente="Juan dijo...", confianza_extraccion=0.85, razon="nombre propio",
        artefacto_origen=archivo_id, status="pendiente", created_at="2026-08-12T00:00:00+00:00",
    )


def test_save_and_read_proposals_roundtrip(cases_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])

    proposals = ner.read_proposals(cases_dir, "caso-1")

    assert len(proposals) == 1
    assert proposals[0].id == "prop-1"
    assert proposals[0].status == "pendiente"


def test_read_proposals_filters_by_status(cases_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])

    assert len(ner.read_proposals(cases_dir, "caso-1", status="pendiente")) == 1
    assert ner.read_proposals(cases_dir, "caso-1", status="confirmado") == []


def test_save_proposals_raises_for_unknown_case(cases_dir, archivo_id):
    with pytest.raises(case_store.CaseNotFoundError):
        ner.save_proposals(cases_dir, "no-existe", [_sample_proposal(archivo_id)])


def test_confirm_proposal_creates_a_real_node_and_traceability_edge(cases_dir, keys_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])

    node = ner.confirm_proposal(cases_dir, keys_dir, "caso-1", "prop-1")

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert any(n.id == node.id and n.tipo == NodeType.PERSONA for n in nodes)

    edges = case_store.read_edges(cases_dir, "caso-1")
    traceability = next(e for e in edges if e.origen == node.id)
    assert traceability.destino == archivo_id
    assert traceability.derivada_por == DerivadaPor.MODELO
    assert traceability.confianza == 0.85

    proposals = ner.read_proposals(cases_dir, "caso-1")
    assert proposals[0].status == "confirmado"
    assert proposals[0].node_id == node.id


def test_confirm_proposal_is_logged_and_verifiable(cases_dir, keys_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])
    ner.confirm_proposal(cases_dir, keys_dir, "caso-1", "prop-1")

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    entries = log_module.read_entries(case_dir / "log.jsonl")
    ops = [e.op for e in entries]
    assert "confirm_proposal" in ops

    verification = log_module.verify_chain(case_dir / "log.jsonl", keys_dir)
    assert verification.ok is True


def test_confirm_proposal_raises_for_unknown_proposal(cases_dir, keys_dir, archivo_id):
    case_store.create_case(cases_dir, "caso-vacio", "x")
    with pytest.raises(ValueError, match="No existe la propuesta"):
        ner.confirm_proposal(cases_dir, keys_dir, "caso-vacio", "no-existe")


def test_confirm_proposal_raises_if_already_resolved(cases_dir, keys_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])
    ner.confirm_proposal(cases_dir, keys_dir, "caso-1", "prop-1")

    with pytest.raises(ValueError, match="ya fue resuelta"):
        ner.confirm_proposal(cases_dir, keys_dir, "caso-1", "prop-1")


def test_reject_proposal_does_not_create_a_node(cases_dir, keys_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])

    rejected = ner.reject_proposal(cases_dir, keys_dir, "caso-1", "prop-1", "no es una persona real distinguible")

    assert rejected.status == "rechazado"
    assert rejected.resolved_reason == "no es una persona real distinguible"
    # el fixture archivo_id ya deja un nodo Archivo -- lo que importa es que
    # rechazar NO agregue ningún nodo nuevo (ninguna Persona)
    assert all(n.tipo != NodeType.PERSONA for n in case_store.read_nodes(cases_dir, "caso-1"))

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    entries = log_module.read_entries(case_dir / "log.jsonl")
    assert "reject_proposal" in [e.op for e in entries]


def test_reject_proposal_raises_if_already_resolved(cases_dir, keys_dir, archivo_id):
    ner.save_proposals(cases_dir, "caso-1", [_sample_proposal(archivo_id)])
    ner.reject_proposal(cases_dir, keys_dir, "caso-1", "prop-1", "motivo")

    with pytest.raises(ValueError, match="ya fue resuelta"):
        ner.reject_proposal(cases_dir, keys_dir, "caso-1", "prop-1", "otro motivo")
