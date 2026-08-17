"""Tests de app/obsidian/profile.py -- el override de vault/embeddings por
contexto (contextvars) usado por el perfil de investigación (ver app/agent.py).
No mockeado: escribe notas reales en dos vaults temporales distintos y
confirma que quedan separados de verdad, incluyendo bajo concurrencia real
de asyncio (dos tareas corriendo al mismo tiempo, cada una con su propio
perfil activo, sin que se pisen)."""

from __future__ import annotations

import asyncio

import pytest

from app.obsidian import embeddings, profile, vault


@pytest.fixture(autouse=True)
def _default_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "default_vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "default_embeddings.json"))
    return tmp_path


def test_without_active_profile_uses_the_default_vault(tmp_path):
    note = vault.save_note(title="Nota default", content="x", author="jarvis")

    assert (tmp_path / "default_vault" / "jarvis" / f"{note.id.split('/', 1)[1]}.md").is_file()


def test_use_profile_redirects_save_note_to_the_override_vault(tmp_path):
    research = profile.VaultProfile(
        vault_path=str(tmp_path / "research_vault"),
        embeddings_path=str(tmp_path / "research_embeddings.json"),
    )

    with profile.use_profile(research):
        note = vault.save_note(title="Nota de investigacion", content="x", author="jarvis")

    slug = note.id.split("/", 1)[1]
    assert (tmp_path / "research_vault" / "jarvis" / f"{slug}.md").is_file()
    assert not (tmp_path / "default_vault" / "jarvis" / f"{slug}.md").is_file()


def test_profile_override_is_scoped_only_to_the_with_block(tmp_path):
    research = profile.VaultProfile(
        vault_path=str(tmp_path / "research_vault"), embeddings_path=str(tmp_path / "research_embeddings.json")
    )

    with profile.use_profile(research):
        vault.save_note(title="Durante el perfil", content="x", author="jarvis")

    # Afuera del 'with', se vuelve a guardar en el vault default -- el
    # override no se queda pegado.
    note_after = vault.save_note(title="Despues del perfil", content="x", author="jarvis")
    slug_after = note_after.id.split("/", 1)[1]
    assert (tmp_path / "default_vault" / "jarvis" / f"{slug_after}.md").is_file()


def test_profiles_do_not_leak_across_concurrent_asyncio_tasks(tmp_path):
    """Bug que este diseño evita a propósito: si el override fuera una
    variable global mutable en vez de un ContextVar, dos conversaciones
    concurrentes (ej. celular + PC al mismo tiempo) podrían pisarse el vault
    activo entre sí. Esto lo prueba de verdad con dos tareas de asyncio
    corriendo en simultáneo, no solo secuencialmente."""
    research_a = profile.VaultProfile(
        vault_path=str(tmp_path / "vault_a"), embeddings_path=str(tmp_path / "emb_a.json")
    )
    research_b = profile.VaultProfile(
        vault_path=str(tmp_path / "vault_b"), embeddings_path=str(tmp_path / "emb_b.json")
    )

    async def _save_in_profile(prof, title, barrier):
        with profile.use_profile(prof):
            await barrier.wait()  # fuerza que las dos tareas se solapen de verdad
            return vault.save_note(title=title, content="x", author="jarvis")

    async def _run():
        barrier = asyncio.Barrier(2)
        note_a, note_b = await asyncio.gather(
            _save_in_profile(research_a, "Nota A", barrier),
            _save_in_profile(research_b, "Nota B", barrier),
        )
        return note_a, note_b

    note_a, note_b = asyncio.run(_run())

    slug_a = note_a.id.split("/", 1)[1]
    slug_b = note_b.id.split("/", 1)[1]
    assert (tmp_path / "vault_a" / "jarvis" / f"{slug_a}.md").is_file()
    assert (tmp_path / "vault_b" / "jarvis" / f"{slug_b}.md").is_file()
    assert not (tmp_path / "vault_a" / "jarvis" / f"{slug_b}.md").is_file()
    assert not (tmp_path / "vault_b" / "jarvis" / f"{slug_a}.md").is_file()


def test_embeddings_index_also_redirects_to_the_override_path(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)  # sin LM Studio en el test
    research = profile.VaultProfile(
        vault_path=str(tmp_path / "research_vault"), embeddings_path=str(tmp_path / "research_embeddings.json")
    )

    with profile.use_profile(research):
        embeddings.save_index({"jarvis/foo": [0.1, 0.2]})

    assert (tmp_path / "research_embeddings.json").is_file()
    assert not (tmp_path / "default_embeddings.json").is_file()
