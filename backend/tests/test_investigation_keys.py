"""Tests de app/investigation/keys.py -- generación, protección DPAPI real
(no mockeada: esta PC es Windows, DPAPI está de verdad disponible) y
firma/verificación Ed25519 real de la clave de firma del log."""

from __future__ import annotations

import pytest

from app.investigation import keys


def test_ensure_keypair_creates_both_files(tmp_path):
    keys.ensure_keypair(tmp_path)

    assert (tmp_path / "signing_key.dpapi").is_file()
    assert (tmp_path / "signing_key.pub").is_file()


def test_ensure_keypair_is_idempotent_does_not_regenerate(tmp_path):
    keys.ensure_keypair(tmp_path)
    private_before = keys.load_private_key(tmp_path)

    keys.ensure_keypair(tmp_path)  # segunda llamada, no debería tocar nada
    private_after = keys.load_private_key(tmp_path)

    from cryptography.hazmat.primitives import serialization

    raw_before = private_before.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    raw_after = private_after.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    assert raw_before == raw_after


def test_private_key_file_is_dpapi_encrypted_not_plaintext_key_material(tmp_path):
    keys.ensure_keypair(tmp_path)

    raw_file_bytes = (tmp_path / "signing_key.dpapi").read_bytes()
    private_key = keys.load_private_key(tmp_path)

    from cryptography.hazmat.primitives import serialization

    plain_key_bytes = private_key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    # El archivo en disco NO debe contener los 32 bytes crudos de la clave
    # tal cual -- eso confirmaría que DPAPI de verdad la está envolviendo,
    # no que se está guardando en texto plano con otro nombre.
    assert plain_key_bytes not in raw_file_bytes


def test_public_key_is_plaintext_readable_without_dpapi(tmp_path):
    keys.ensure_keypair(tmp_path)

    public_key = keys.load_public_key(tmp_path)

    from cryptography.hazmat.primitives import serialization

    raw_pub = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    assert (tmp_path / "signing_key.pub").read_bytes() == raw_pub


def test_load_private_key_without_ensure_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        keys.load_private_key(tmp_path)


def test_load_public_key_without_ensure_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        keys.load_public_key(tmp_path)


def test_sign_and_verify_roundtrip_real(tmp_path):
    keys.ensure_keypair(tmp_path)
    private_key = keys.load_private_key(tmp_path)
    public_key = keys.load_public_key(tmp_path)

    signature = keys.sign(private_key, b"contenido real de una entrada de log")

    assert keys.verify(public_key, b"contenido real de una entrada de log", signature) is True


def test_verify_rejects_tampered_data(tmp_path):
    keys.ensure_keypair(tmp_path)
    private_key = keys.load_private_key(tmp_path)
    public_key = keys.load_public_key(tmp_path)

    signature = keys.sign(private_key, b"contenido original")

    assert keys.verify(public_key, b"contenido MODIFICADO", signature) is False


def test_verify_rejects_signature_from_a_different_keypair(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    keys.ensure_keypair(dir_a)
    keys.ensure_keypair(dir_b)

    signature_from_a = keys.sign(keys.load_private_key(dir_a), b"mensaje")
    public_key_b = keys.load_public_key(dir_b)

    assert keys.verify(public_key_b, b"mensaje", signature_from_a) is False
