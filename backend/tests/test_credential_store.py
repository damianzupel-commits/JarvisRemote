"""Tests de app/forms/credential_store.py -- DPAPI real (no mockeada, esta
PC es Windows, mismo criterio que test_investigation_keys.py) para el store
de credenciales generadas al completar formularios web."""

from __future__ import annotations

from app.forms import credential_store


def test_generate_strong_password_default_length():
    password = credential_store.generate_strong_password()
    assert len(password) == 20


def test_generate_strong_password_enforces_minimum_length():
    password = credential_store.generate_strong_password(length=4)
    assert len(password) == 12  # tope duro _MIN_LENGTH, sin importar lo que se pida


def test_generate_strong_password_never_reuses_the_same_value():
    passwords = {credential_store.generate_strong_password() for _ in range(20)}
    assert len(passwords) == 20  # CSPRNG real -- ninguna colisión en 20 generaciones


def test_save_and_get_credential_roundtrip(tmp_path):
    path = tmp_path / "creds.dpapi"
    credential_store.save_credential(path=path, site="tenable.com", username="damian@example.com", password="s3cr3t!")

    entry = credential_store.get_credential(path, site="tenable.com")

    assert entry is not None
    assert entry["site"] == "tenable.com"
    assert entry["username"] == "damian@example.com"
    assert entry["password"] == "s3cr3t!"
    assert "created_at" in entry


def test_get_credential_returns_none_when_not_found(tmp_path):
    path = tmp_path / "creds.dpapi"
    assert credential_store.get_credential(path, site="nunca-guardado.com") is None


def test_credential_file_is_dpapi_encrypted_not_plaintext(tmp_path):
    """Regresión directa del requisito de Damian: NUNCA texto plano en disco,
    mismo antipatrón ya señalado sobre backend/.env."""
    path = tmp_path / "creds.dpapi"
    credential_store.save_credential(path=path, site="tenable.com", username="damian", password="s3cr3t!MuySecreta")

    raw_file_bytes = path.read_bytes()

    assert b"s3cr3t!MuySecreta" not in raw_file_bytes
    assert b"tenable.com" not in raw_file_bytes  # ni siquiera la metadata queda en claro


def test_list_credentials_never_exposes_the_password(tmp_path):
    path = tmp_path / "creds.dpapi"
    credential_store.save_credential(path=path, site="tenable.com", username="damian", password="s3cr3t!")

    entries = credential_store.list_credentials(path)

    assert entries == [{"site": "tenable.com", "username": "damian", "created_at": entries[0]["created_at"]}]
    assert all("password" not in e for e in entries)


def test_get_credential_disambiguates_by_username_when_multiple_entries_for_same_site(tmp_path):
    path = tmp_path / "creds.dpapi"
    credential_store.save_credential(path=path, site="tenable.com", username="cuenta1@example.com", password="pass1")
    credential_store.save_credential(path=path, site="tenable.com", username="cuenta2@example.com", password="pass2")

    entry = credential_store.get_credential(path, site="tenable.com", username="cuenta1@example.com")

    assert entry["username"] == "cuenta1@example.com"
    assert entry["password"] == "pass1"


def test_get_credential_without_username_returns_most_recent(tmp_path):
    path = tmp_path / "creds.dpapi"
    credential_store.save_credential(path=path, site="tenable.com", username="cuenta1@example.com", password="pass1")
    credential_store.save_credential(path=path, site="tenable.com", username="cuenta2@example.com", password="pass2")

    entry = credential_store.get_credential(path, site="tenable.com")

    assert entry["username"] == "cuenta2@example.com"


def test_save_credential_appends_without_losing_previous_entries(tmp_path):
    path = tmp_path / "creds.dpapi"
    credential_store.save_credential(path=path, site="site-a.com", username="u1", password="p1")
    credential_store.save_credential(path=path, site="site-b.com", username="u2", password="p2")

    assert credential_store.get_credential(path, site="site-a.com")["password"] == "p1"
    assert credential_store.get_credential(path, site="site-b.com")["password"] == "p2"
