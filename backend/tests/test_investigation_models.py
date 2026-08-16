"""Tests del schema de entidades del módulo de investigación
(app/investigation/models.py) -- spec sección 1."""

from __future__ import annotations

import pytest

from app.investigation import models


def test_make_persona_combines_existence_and_ownership_into_one_confianza():
    node = models.make_persona(etiqueta="Alias visto en 3 fuentes", confianza=0.8, alias=["alias1", "alias2"])

    assert node.tipo == models.NodeType.PERSONA
    assert node.campos["confianza"] == 0.8
    assert node.campos["alias"] == ["alias1", "alias2"]


def test_make_persona_rejects_confianza_out_of_range():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        models.make_persona(etiqueta="x", confianza=1.5)
    with pytest.raises(ValueError):
        models.make_persona(etiqueta="x", confianza=-0.1)


def test_make_persona_defaults_to_a_random_id_no_natural_key():
    a = models.make_persona(etiqueta="Juan", confianza=0.5)
    b = models.make_persona(etiqueta="Juan", confianza=0.5)

    assert a.id != b.id  # nunca se deduplica por nombre -- eso es lo que mismo_que resuelve a mano


def test_make_archivo_id_is_deterministic_by_sha256_not_by_name():
    a = models.make_archivo(nombre="export1.txt", sha256="a" * 64, tamano=100, mime="text/plain")
    b = models.make_archivo(nombre="export2_renombrado.txt", sha256="a" * 64, tamano=100, mime="text/plain")
    c = models.make_archivo(nombre="export1.txt", sha256="b" * 64, tamano=100, mime="text/plain")

    assert a.id == b.id  # mismo hash, distinto nombre -> mismo nodo (reingesta no duplica)
    assert a.id != c.id  # distinto hash -> nodo distinto


def test_make_cuenta_id_is_deterministic_by_platform_and_handle():
    a = models.make_cuenta(plataforma="telegram", handle="@ejemplo")
    b = models.make_cuenta(plataforma="telegram", handle="@ejemplo")
    c = models.make_cuenta(plataforma="whatsapp", handle="@ejemplo")

    assert a.id == b.id
    assert a.id != c.id


def test_make_host_id_is_deterministic_by_ip_or_domain():
    a = models.make_host(ip_o_dominio="192.0.2.10")
    b = models.make_host(ip_o_dominio="192.0.2.10")
    assert a.id == b.id


def test_node_missing_required_field_raises():
    # Simula lo que pasaría si alguien arma 'campos' incompleto a mano en vez
    # de pasar por un make_* -- _validate_campos (lo que cada make_* llama
    # antes de construir el Node) tiene que cortarlo ahí mismo.
    with pytest.raises(ValueError, match="Faltan campos requeridos"):
        models._validate_campos(models.NodeType.CUENTA, {"plataforma": "x"})


def test_node_retract_never_deletes_just_marks():
    node = models.make_persona(etiqueta="x", confianza=0.5)
    original_campos = dict(node.campos)

    node.retract("identidad incorrecta, error de fusión")

    assert node.retracted is True
    assert node.retracted_reason == "identidad incorrecta, error de fusión"
    assert node.retracted_at is not None
    assert node.campos == original_campos  # el dato original queda intacto


def test_node_to_dict_from_dict_roundtrip():
    node = models.make_persona(etiqueta="x", confianza=0.5, alias=["a"])
    node.retract("motivo de prueba")

    restored = models.Node.from_dict(node.to_dict())

    assert restored == node


def test_make_edge_requires_all_mandatory_fields():
    persona = models.make_persona(etiqueta="x", confianza=0.5)
    cuenta = models.make_cuenta(plataforma="telegram", handle="@x")
    archivo = models.make_archivo(nombre="a.txt", sha256="c" * 64, tamano=1, mime="text/plain")

    edge = models.make_edge(
        tipo=models.EdgeType.USA,
        origen=persona.id,
        destino=cuenta.id,
        artefacto_origen=archivo.id,
        confianza=0.9,
        derivada_por=models.DerivadaPor.PARSER,
    )

    assert edge.timestamp is not None
    assert edge.artefacto_origen == archivo.id
    assert edge.derivada_por == models.DerivadaPor.PARSER


def test_make_edge_rejects_confianza_out_of_range():
    with pytest.raises(ValueError):
        models.make_edge(
            tipo=models.EdgeType.USA, origen="a", destino="b", artefacto_origen="c",
            confianza=2.0, derivada_por=models.DerivadaPor.MANUAL,
        )


def test_edge_to_dict_from_dict_roundtrip():
    edge = models.make_edge(
        tipo=models.EdgeType.MISMO_QUE, origen="p1", destino="p2", artefacto_origen="a1",
        confianza=0.95, derivada_por=models.DerivadaPor.MANUAL,
    )
    edge.retract("fusión incorrecta")

    restored = models.Edge.from_dict(edge.to_dict())

    assert restored == edge


def test_edge_retract_never_deletes_the_underlying_nodes():
    """Decisión de Damian (2026-08-12): mismo_que NUNCA combina los nodos --
    retractar la arista tiene que dejar los dos nodos originales intactos,
    solo la arista queda marcada."""
    persona_a = models.make_persona(etiqueta="a", confianza=0.5)
    persona_b = models.make_persona(etiqueta="b", confianza=0.5)
    fusion = models.make_edge(
        tipo=models.EdgeType.MISMO_QUE, origen=persona_a.id, destino=persona_b.id,
        artefacto_origen="manual", confianza=1.0, derivada_por=models.DerivadaPor.MANUAL,
    )

    fusion.retract("Damian determinó que eran personas distintas")

    assert fusion.retracted is True
    assert persona_a.id != persona_b.id  # los nodos nunca se tocaron ni se combinaron
