"""Tests de app/investigation/fusion.py -- paso 7 del orden de
implementación (spec sección 3: fusión de identidades, requiere
confirmación explícita). El cliente del modelo se mockea (mismo criterio
que ner.py/column_mapping.py); case_store/log corren reales."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.investigation import case_store, fusion, keys, log as log_module
from app.investigation.models import DerivadaPor, EdgeType, NodeType, make_cuenta, make_host, make_persona


@pytest.fixture()
def keys_dir(tmp_path):
    d = tmp_path / "keys"
    keys.ensure_keypair(d)
    return d


@pytest.fixture()
def cases_dir(tmp_path):
    d = tmp_path / "cases"
    case_store.create_case(d, "caso-1", "Caso de prueba")
    return d


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# --- propose_fusion --------------------------------------------------------------

@pytest.mark.anyio
async def test_propose_fusion_parses_a_clean_response(monkeypatch):
    a = make_persona(etiqueta="Juan Perez", confianza=0.6)
    b = make_persona(etiqueta="J. Perez", confianza=0.6)

    async def fake_create(**kwargs):
        return _fake_response('{"confianza": 0.85, "razon": "mismo nombre con variante de escritura"}')

    monkeypatch.setattr(fusion.client.chat.completions, "create", fake_create)

    proposal = await fusion.propose_fusion(a, b)

    assert proposal.node_a_id == a.id
    assert proposal.node_b_id == b.id
    assert proposal.confianza == 0.85
    assert proposal.status == "pendiente"
    assert "variante" in proposal.razon


@pytest.mark.anyio
async def test_propose_fusion_raises_for_mismatched_node_types():
    persona = make_persona(etiqueta="a", confianza=0.5)
    host = make_host(ip_o_dominio="10.0.0.1")

    with pytest.raises(ValueError, match="tipos distintos"):
        await fusion.propose_fusion(persona, host)


@pytest.mark.anyio
async def test_propose_fusion_raises_on_unparseable_response(monkeypatch):
    a = make_cuenta(plataforma="x", handle="@a")
    b = make_cuenta(plataforma="y", handle="@b")

    async def fake_create(**kwargs):
        return _fake_response("no puedo evaluar eso")

    monkeypatch.setattr(fusion.client.chat.completions, "create", fake_create)

    with pytest.raises(ValueError, match="JSON parseable"):
        await fusion.propose_fusion(a, b)


@pytest.mark.anyio
async def test_propose_fusion_raises_for_out_of_range_confianza(monkeypatch):
    a = make_cuenta(plataforma="x", handle="@a")
    b = make_cuenta(plataforma="y", handle="@b")

    async def fake_create(**kwargs):
        return _fake_response('{"confianza": 1.5, "razon": "x"}')

    monkeypatch.setattr(fusion.client.chat.completions, "create", fake_create)

    with pytest.raises(ValueError, match="fuera de rango"):
        await fusion.propose_fusion(a, b)


@pytest.mark.anyio
async def test_propose_fusion_sends_real_fields_of_both_nodes(monkeypatch):
    captured = {}
    a = make_persona(etiqueta="Juan Perez", confianza=0.6)
    b = make_persona(etiqueta="J. Perez", confianza=0.6)

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"confianza": 0.5, "razon": "x"}')

    monkeypatch.setattr(fusion.client.chat.completions, "create", fake_create)

    await fusion.propose_fusion(a, b)

    user_msg = captured["messages"][1]["content"]
    assert "Juan Perez" in user_msg
    assert "J. Perez" in user_msg
    assert captured["temperature"] == 0


# --- persistencia real -------------------------------------------------------------

def _sample_proposal(node_a_id: str, node_b_id: str) -> fusion.FusionProposal:
    return fusion.FusionProposal(
        id="fusion-1", node_a_id=node_a_id, node_b_id=node_b_id, confianza=0.8,
        razon="misma persona, nombre con variante", status="pendiente", created_at="2026-08-12T00:00:00+00:00",
    )


def test_save_and_read_proposals_roundtrip(cases_dir):
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)

    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))

    proposals = fusion.read_proposals(cases_dir, "caso-1")
    assert len(proposals) == 1
    assert proposals[0].id == "fusion-1"


def test_read_proposals_filters_by_status(cases_dir):
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))

    assert len(fusion.read_proposals(cases_dir, "caso-1", status="pendiente")) == 1
    assert fusion.read_proposals(cases_dir, "caso-1", status="confirmado") == []


def test_save_proposal_raises_for_unknown_case(cases_dir):
    with pytest.raises(case_store.CaseNotFoundError):
        fusion.save_proposal(cases_dir, "no-existe", _sample_proposal("a", "b"))


def test_confirm_fusion_creates_a_real_mismo_que_edge_without_merging_nodes(cases_dir, keys_dir):
    a = make_persona(etiqueta="Juan Perez", confianza=0.6)
    b = make_persona(etiqueta="J. Perez", confianza=0.6)
    case_store.add_node(cases_dir, keys_dir, "caso-1", a)
    case_store.add_node(cases_dir, keys_dir, "caso-1", b)
    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))

    edge = fusion.confirm_fusion(cases_dir, keys_dir, "caso-1", "fusion-1")

    assert edge.tipo == EdgeType.MISMO_QUE
    assert edge.origen == a.id
    assert edge.destino == b.id
    assert edge.derivada_por == DerivadaPor.MODELO
    assert edge.confianza == 0.8

    # los DOS nodos originales siguen existiendo, intactos -- nunca se fusionan en uno.
    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert len([n for n in nodes if n.tipo == NodeType.PERSONA]) == 2
    assert any(n.id == a.id and n.campos["etiqueta"] == "Juan Perez" for n in nodes)
    assert any(n.id == b.id and n.campos["etiqueta"] == "J. Perez" for n in nodes)

    proposals = fusion.read_proposals(cases_dir, "caso-1")
    assert proposals[0].status == "confirmado"
    assert proposals[0].edge_id == edge.id


def test_confirm_fusion_is_logged_and_verifiable(cases_dir, keys_dir):
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", a)
    case_store.add_node(cases_dir, keys_dir, "caso-1", b)
    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))

    fusion.confirm_fusion(cases_dir, keys_dir, "caso-1", "fusion-1")

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    entries = log_module.read_entries(case_dir / "log.jsonl")
    assert "confirm_fusion" in [e.op for e in entries]
    verification = log_module.verify_chain(case_dir / "log.jsonl", keys_dir)
    assert verification.ok is True


def test_confirm_fusion_raises_for_unknown_proposal(cases_dir, keys_dir):
    with pytest.raises(ValueError, match="No existe la propuesta de fusión"):
        fusion.confirm_fusion(cases_dir, keys_dir, "caso-1", "no-existe")


def test_confirm_fusion_raises_if_already_resolved(cases_dir, keys_dir):
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", a)
    case_store.add_node(cases_dir, keys_dir, "caso-1", b)
    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))
    fusion.confirm_fusion(cases_dir, keys_dir, "caso-1", "fusion-1")

    with pytest.raises(ValueError, match="ya fue resuelta"):
        fusion.confirm_fusion(cases_dir, keys_dir, "caso-1", "fusion-1")


def test_reject_fusion_does_not_create_an_edge(cases_dir, keys_dir):
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", a)
    case_store.add_node(cases_dir, keys_dir, "caso-1", b)
    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))

    rejected = fusion.reject_fusion(cases_dir, keys_dir, "caso-1", "fusion-1", "son personas distintas")

    assert rejected.status == "rechazado"
    assert rejected.resolved_reason == "son personas distintas"
    assert case_store.read_edges(cases_dir, "caso-1") == []

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    entries = log_module.read_entries(case_dir / "log.jsonl")
    assert "reject_fusion" in [e.op for e in entries]


def test_reject_fusion_raises_if_already_resolved(cases_dir, keys_dir):
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store.add_node(cases_dir, keys_dir, "caso-1", a)
    case_store.add_node(cases_dir, keys_dir, "caso-1", b)
    fusion.save_proposal(cases_dir, "caso-1", _sample_proposal(a.id, b.id))
    fusion.reject_fusion(cases_dir, keys_dir, "caso-1", "fusion-1", "motivo")

    with pytest.raises(ValueError, match="ya fue resuelta"):
        fusion.reject_fusion(cases_dir, keys_dir, "caso-1", "fusion-1", "otro motivo")
