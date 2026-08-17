"""Tests de app/security/triage_reference.py -- lookup DETERMINÍSTICO
(categoría -> note_id fijo) de la referencia curada, no búsqueda semántica.
Diseño 2026-08-11 tras el primer resultado real del triage (score 44.0% ->
37.6%, empeoró): el modelo confundía mitigaciones entre categorías distintas
de vulnerabilidad."""

from __future__ import annotations

import pytest

from app.obsidian import embeddings, vault
from app.security import triage_reference


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "vault"


def test_get_reference_returns_none_before_notes_are_created():
    assert triage_reference.get_reference_for_category("trustbound") is None


def test_ensure_reference_notes_creates_all_three_curated_categories():
    note_ids = triage_reference.ensure_reference_notes()

    assert len(note_ids) == 3
    for category in ("trustbound", "ldapi", "pathtraver"):
        assert f"jarvis/triage-referencia-{category}" in note_ids


def test_get_reference_returns_real_content_after_notes_exist():
    triage_reference.ensure_reference_notes()

    content = triage_reference.get_reference_for_category("trustbound")

    assert content is not None
    assert "CWE-501" in content
    assert "HTML-escaping" in content
    assert "NO mitiga" in content


def test_get_reference_returns_none_for_a_category_without_a_curated_note():
    triage_reference.ensure_reference_notes()

    assert triage_reference.get_reference_for_category("xss") is None
    assert triage_reference.get_reference_for_category("sqli") is None


def test_get_reference_returns_none_for_none_category():
    assert triage_reference.get_reference_for_category(None) is None


def test_ensure_reference_notes_is_idempotent_and_reflects_manual_edits():
    """Si Damian edita la nota a mano en Obsidian, el próximo triage tiene
    que usar la versión editada -- get_reference_for_category no debe
    cachear en memoria."""
    triage_reference.ensure_reference_notes()

    note = vault.read_note("jarvis/triage-referencia-trustbound")
    vault.save_note(
        title=note.title, content="Contenido editado a mano por Damian.",
        author="jarvis", tags=note.tags, category=note.category, note_id=note.id,
    )

    assert triage_reference.get_reference_for_category("trustbound") == "Contenido editado a mano por Damian."


def test_curated_notes_are_saved_with_the_expected_author_and_tags():
    triage_reference.ensure_reference_notes()

    note = vault.read_note("jarvis/triage-referencia-ldapi")
    assert note.author == "jarvis"
    assert "triage-referencia" in note.tags
    assert "ldapi" in note.tags
