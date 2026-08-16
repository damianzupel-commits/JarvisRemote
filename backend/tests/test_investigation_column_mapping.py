"""Tests de app/investigation/column_mapping.py. El cliente del modelo se
mockea (mismo criterio que test_security_triage.py) -- lo que se prueba acá
es la lógica real: la firma de columnas para reutilización, guardar/cargar
un mapeo confirmado, y el parseo tolerante de la propuesta del modelo."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.investigation import column_mapping
from app.investigation.models import NodeType


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_source_signature_is_stable_for_the_same_columns():
    a = column_mapping.source_signature(["nombre", "handle"])
    b = column_mapping.source_signature(["nombre", "handle"])
    assert a == b


def test_source_signature_differs_for_different_columns():
    a = column_mapping.source_signature(["nombre", "handle"])
    b = column_mapping.source_signature(["nombre", "telefono"])
    assert a != b


def test_save_and_load_mapping_roundtrip(tmp_path):
    columns = ["nombre", "usuario_telegram"]
    column_mapping.save_mapping(
        tmp_path, columns, NodeType.CUENTA,
        column_mapping={"usuario_telegram": "handle"}, defaults={"plataforma": "telegram"},
    )

    loaded = column_mapping.load_saved_mapping(tmp_path, columns)

    assert loaded is not None
    assert loaded["node_type"] == "Cuenta"
    assert loaded["column_mapping"] == {"usuario_telegram": "handle"}
    assert loaded["defaults"] == {"plataforma": "telegram"}


def test_load_saved_mapping_returns_none_when_never_saved(tmp_path):
    assert column_mapping.load_saved_mapping(tmp_path, ["a", "b"]) is None


def test_a_different_column_set_does_not_reuse_a_saved_mapping(tmp_path):
    column_mapping.save_mapping(tmp_path, ["a", "b"], NodeType.CUENTA, {"a": "handle"})

    assert column_mapping.load_saved_mapping(tmp_path, ["a", "b", "c"]) is None


def test_save_mapping_overwrites_a_previous_confirmation_for_the_same_columns(tmp_path):
    columns = ["nombre"]
    column_mapping.save_mapping(tmp_path, columns, NodeType.PERSONA, {"nombre": "etiqueta"})
    column_mapping.save_mapping(tmp_path, columns, NodeType.PERSONA, {"nombre": "alias"})

    loaded = column_mapping.load_saved_mapping(tmp_path, columns)
    assert loaded["column_mapping"] == {"nombre": "alias"}


@pytest.mark.anyio
async def test_propose_mapping_parses_a_clean_json_response(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response('{"columns": {"usuario_telegram": "handle"}, "reasoning": "coincide con handle"}')

    monkeypatch.setattr(column_mapping.client.chat.completions, "create", fake_create)

    proposal = await column_mapping.propose_mapping(
        NodeType.CUENTA, ["usuario_telegram", "columna_rara"], [{"usuario_telegram": "@ejemplo", "columna_rara": "x"}]
    )

    assert proposal.columns == {"usuario_telegram": "handle"}
    assert proposal.unmapped_columns == ["columna_rara"]
    assert "handle" in proposal.reasoning or proposal.reasoning


@pytest.mark.anyio
async def test_propose_mapping_ignores_columns_the_model_invented():
    proposal = column_mapping._parse_proposal(
        NodeType.CUENTA, ["real_col"],
        '{"columns": {"real_col": "handle", "columna_que_no_existe": "handle"}}',
    )

    assert proposal.columns == {"real_col": "handle"}


@pytest.mark.anyio
async def test_propose_mapping_raises_on_unparseable_response(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response("no puedo ayudarte con eso")

    monkeypatch.setattr(column_mapping.client.chat.completions, "create", fake_create)

    with pytest.raises(ValueError, match="JSON parseable"):
        await column_mapping.propose_mapping(NodeType.CUENTA, ["a"], [{"a": "1"}])


@pytest.mark.anyio
async def test_propose_mapping_sends_real_sample_rows_and_target_fields(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"columns": {}, "reasoning": "x"}')

    monkeypatch.setattr(column_mapping.client.chat.completions, "create", fake_create)

    await column_mapping.propose_mapping(
        NodeType.PERSONA, ["nombre_completo"], [{"nombre_completo": "Juan Perez"}]
    )

    user_msg = captured["messages"][1]["content"]
    assert "Juan Perez" in user_msg
    assert "Persona" in user_msg
    assert "etiqueta" in user_msg  # campo real del schema de Persona
    assert captured["temperature"] == 0
