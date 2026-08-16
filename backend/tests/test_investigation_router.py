"""Tests de app/routers/investigation.py -- el endpoint que consumirá la
futura pestaña de investigación de la tray-app. TestClient real (mismo
criterio que test_codebase_router.py), datos reales de un caso real."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.investigation import case_store, keys
from app.investigation.models import DerivadaPor, EdgeType, make_edge, make_evento, make_host, make_persona
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {settings.api_key}"}


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "investigation_cases_dir", str(tmp_path / "cases"))
    monkeypatch.setattr(settings, "investigation_keys_dir", str(tmp_path / "keys"))
    keys.ensure_keypair(tmp_path / "keys")


def test_get_case_graph_requires_auth():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    resp = client.get("/api/investigation/caso-1/graph")
    assert resp.status_code == 401


def test_get_case_graph_for_unknown_case_returns_404():
    resp = client.get("/api/investigation/no-existe/graph", headers=AUTH)
    assert resp.status_code == 404


def test_get_case_graph_returns_nodes_with_centrality_and_confidence():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", a)
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", b)
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", c)
    edge1 = make_edge(tipo=EdgeType.USA, origen=a.id, destino=b.id, artefacto_origen="manual", confianza=0.8, derivada_por=DerivadaPor.MANUAL)
    edge2 = make_edge(tipo=EdgeType.USA, origen=b.id, destino=c.id, artefacto_origen="manual", confianza=0.6, derivada_por=DerivadaPor.MANUAL)
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge1)
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge2)

    resp = client.get("/api/investigation/caso-1/graph", headers=AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["nodes"]) == 3
    assert len(body["edges"]) == 2
    by_id = {n["id"]: n for n in body["nodes"]}
    # b es el nodo puente real (a-b-c) -- betweenness mayor que a y c
    assert by_id[b.id]["centrality"] > by_id[a.id]["centrality"]
    assert by_id[a.id]["confidence"] is not None
    # los 3 estan conectados en una sola cadena -- misma comunidad para los 3
    assert by_id[a.id]["community"] == by_id[b.id]["community"] == by_id[c.id]["community"]


def test_get_case_graph_separates_disconnected_clusters_into_different_communities():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    d = make_persona(etiqueta="d", confianza=0.5)
    for n in (a, b, c, d):
        case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", n)
    edge_ab = make_edge(tipo=EdgeType.USA, origen=a.id, destino=b.id, artefacto_origen="manual", confianza=0.8, derivada_por=DerivadaPor.MANUAL)
    edge_cd = make_edge(tipo=EdgeType.USA, origen=c.id, destino=d.id, artefacto_origen="manual", confianza=0.8, derivada_por=DerivadaPor.MANUAL)
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge_ab)
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge_cd)

    resp = client.get("/api/investigation/caso-1/graph", headers=AUTH)

    by_id = {n["id"]: n for n in resp.json()["nodes"]}
    assert by_id[a.id]["community"] == by_id[b.id]["community"]
    assert by_id[c.id]["community"] == by_id[d.id]["community"]
    assert by_id[a.id]["community"] != by_id[c.id]["community"]


def test_get_case_graph_excludes_retracted_nodes_and_edges():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", a)
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", b)
    case_store.retract_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", b.id, "error")

    resp = client.get("/api/investigation/caso-1/graph", headers=AUTH)

    body = resp.json()
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["id"] == a.id


def test_list_cases_returns_real_created_cases():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "Primer caso")
    case_store.create_case(settings.investigation_cases_dir, "caso-2", "Segundo caso")

    resp = client.get("/api/investigation/cases", headers=AUTH)

    assert resp.status_code == 200
    titles = {c["titulo"] for c in resp.json()["cases"]}
    assert titles == {"Primer caso", "Segundo caso"}


def test_list_cases_empty_when_no_cases_dir_yet():
    resp = client.get("/api/investigation/cases", headers=AUTH)
    assert resp.json()["cases"] == []


def test_get_case_timeline_for_unknown_case_returns_404():
    resp = client.get("/api/investigation/no-existe/timeline", headers=AUTH)
    assert resp.status_code == 404


def test_get_case_timeline_returns_sorted_entries():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    e1 = make_evento(timestamp_utc="2026-08-12T12:00:00+00:00", descripcion="segundo", fuente="x")
    e2 = make_evento(timestamp_utc="2026-08-12T08:00:00+00:00", descripcion="primero", fuente="x")
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", e1)
    case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", e2)

    resp = client.get("/api/investigation/caso-1/timeline", headers=AUTH)

    assert resp.status_code == 200
    descriptions = [entry["description"] for entry in resp.json()["entries"]]
    assert descriptions == ["primero", "segundo"]


def test_get_case_timeline_filters_by_entity_id():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    c = make_persona(etiqueta="c", confianza=0.5)
    for n in (a, b, c):
        case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", n)
    edge_ab = make_edge(tipo=EdgeType.USA, origen=a.id, destino=b.id, artefacto_origen="x", confianza=0.8, derivada_por=DerivadaPor.MANUAL, timestamp="2026-08-12T10:00:00+00:00")
    edge_bc = make_edge(tipo=EdgeType.USA, origen=b.id, destino=c.id, artefacto_origen="x", confianza=0.8, derivada_por=DerivadaPor.MANUAL, timestamp="2026-08-12T11:00:00+00:00")
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge_ab)
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge_bc)

    resp = client.get("/api/investigation/caso-1/timeline", headers=AUTH, params={"entity_id": a.id})

    assert len(resp.json()["entries"]) == 1


def test_get_case_timeline_surfaces_real_contradictions():
    case_store.create_case(settings.investigation_cases_dir, "caso-1", "x")
    persona = make_persona(etiqueta="p", confianza=0.5)
    host_a = make_host(ip_o_dominio="10.0.0.1")
    host_b = make_host(ip_o_dominio="10.0.0.2")
    for n in (persona, host_a, host_b):
        case_store.add_node(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", n)
    edge_a = make_edge(tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_a.id, artefacto_origen="x", confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:00:00+00:00")
    edge_b = make_edge(tipo=EdgeType.APARECE_EN, origen=persona.id, destino=host_b.id, artefacto_origen="x", confianza=0.9, derivada_por=DerivadaPor.PARSER, timestamp="2026-08-12T10:01:00+00:00")
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge_a)
    case_store.add_edge(settings.investigation_cases_dir, settings.investigation_keys_dir, "caso-1", edge_b)

    resp = client.get("/api/investigation/caso-1/timeline", headers=AUTH)

    contradictions = resp.json()["contradictions"]
    assert len(contradictions) == 1
    assert contradictions[0]["entity_id"] == persona.id
