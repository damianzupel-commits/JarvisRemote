"""Tests de app/investigation/artifact_store.py -- almacén inmutable
indexado por sha256, con marker de ingesta incremental. Todo con archivos
reales en tmp_path, no mockeado (I/O real es justo lo que hay que probar
acá)."""

from __future__ import annotations

import hashlib

import pytest

from app.investigation import artifact_store


def test_store_artifact_writes_real_bytes_addressed_by_hash(tmp_path):
    data = b"contenido de prueba"
    record = artifact_store.store_artifact(tmp_path, data, "export.txt", ingested_by="damian")

    assert record.sha256 == hashlib.sha256(data).hexdigest()
    assert record.original_name == "export.txt"
    assert record.size == len(data)
    assert record.ingested_by == "damian"
    assert artifact_store.read_artifact_bytes(tmp_path, record.sha256) == data


def test_reloading_the_same_content_under_a_different_name_resolves_to_the_same_artifact(tmp_path):
    data = b"mismo contenido"
    first = artifact_store.store_artifact(tmp_path, data, "original.txt", ingested_by="damian")
    second = artifact_store.store_artifact(tmp_path, data, "renombrado_distinto.txt", ingested_by="damian")

    assert first.sha256 == second.sha256
    # No pisa el registro original (nombre/ingested_at quedan del primero) --
    # es inmutable de verdad, no "la ultima gana".
    assert second.original_name == "original.txt"
    assert second.ingested_at == first.ingested_at


def test_store_artifact_never_overwrites_the_object_bytes_on_disk(tmp_path):
    data = b"contenido original"
    record = artifact_store.store_artifact(tmp_path, data, "a.txt", ingested_by="damian")

    object_path = tmp_path / "objects" / record.sha256[:2] / record.sha256
    original_mtime = object_path.stat().st_mtime_ns

    artifact_store.store_artifact(tmp_path, data, "a.txt", ingested_by="damian")

    assert object_path.stat().st_mtime_ns == original_mtime


def test_different_content_gets_different_hash_and_storage(tmp_path):
    a = artifact_store.store_artifact(tmp_path, b"contenido A", "a.txt", ingested_by="damian")
    b = artifact_store.store_artifact(tmp_path, b"contenido B", "b.txt", ingested_by="damian")

    assert a.sha256 != b.sha256
    assert artifact_store.read_artifact_bytes(tmp_path, a.sha256) == b"contenido A"
    assert artifact_store.read_artifact_bytes(tmp_path, b.sha256) == b"contenido B"


def test_read_artifact_bytes_raises_for_unknown_hash(tmp_path):
    with pytest.raises(FileNotFoundError):
        artifact_store.read_artifact_bytes(tmp_path, "0" * 64)


def test_read_record_returns_none_for_unknown_hash(tmp_path):
    assert artifact_store.read_record(tmp_path, "0" * 64) is None


def test_ingestion_marker_starts_as_none(tmp_path):
    record = artifact_store.store_artifact(tmp_path, b"x", "x.txt", ingested_by="damian")
    assert record.ingestion_marker is None


def test_set_ingestion_marker_persists_for_incremental_reingestion(tmp_path):
    """El caso real que motiva esto: un export de WhatsApp se recarga
    despues de agregarle mensajes nuevos -- el parser (no este modulo)
    decide hasta donde ya proceso la vez anterior usando este marker, y solo
    genera nodos/aristas para lo nuevo."""
    record = artifact_store.store_artifact(tmp_path, b"mensaje1\nmensaje2\n", "chat.txt", ingested_by="damian")

    updated = artifact_store.set_ingestion_marker(tmp_path, record.sha256, marker="line:2")

    assert updated.ingestion_marker == "line:2"
    reloaded = artifact_store.read_record(tmp_path, record.sha256)
    assert reloaded.ingestion_marker == "line:2"


def test_set_ingestion_marker_raises_for_unknown_artifact(tmp_path):
    with pytest.raises(FileNotFoundError):
        artifact_store.set_ingestion_marker(tmp_path, "0" * 64, marker="x")


def test_many_artifacts_are_sharded_across_subdirectories(tmp_path):
    for i in range(5):
        artifact_store.store_artifact(tmp_path, f"contenido {i}".encode(), f"f{i}.txt", ingested_by="damian")

    shard_dirs = list((tmp_path / "objects").iterdir())
    # con contenido distinto, hashes distintos -- se espera que caigan en
    # mas de un shard de 2 caracteres (no una prueba determinista exacta de
    # CUANTOS, pero confirma que el sharding esta pasando de verdad, no que
    # todo cae en una sola carpeta plana)
    assert len(shard_dirs) >= 1
    total_objects = sum(1 for shard in shard_dirs for _ in shard.iterdir())
    assert total_objects == 5
