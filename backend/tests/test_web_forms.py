"""Tests de app/tools/web_forms.py -- generación/guarda de contraseñas
(DPAPI real, ver test_credential_store.py) y el dry-run->confirm=true de
browser_preview_submit (Playwright mockeado, mismo criterio que
test_browser_tool.py: nunca un browser real en la suite)."""

from __future__ import annotations

import pytest

from app.forms import credential_store
from app.tools import web_forms


@pytest.fixture(autouse=True)
def _isolate_credentials_and_previews(tmp_path, monkeypatch):
    monkeypatch.setattr(web_forms.settings, "form_credentials_path", str(tmp_path / "creds.dpapi"))
    monkeypatch.setattr(web_forms.settings, "form_preview_dir", str(tmp_path / "previews"))
    yield


class _FakePage:
    def __init__(self, field_values):
        self.url = "https://example.com/register"
        self._field_values = field_values
        self.screenshot_calls: list[str] = []
        self.click_calls: list[str] = []
        self.wait_for_load_state_called = False
        self.eval_on_selector_all_calls: list[str] = []

    async def eval_on_selector_all(self, selector, script):
        self.eval_on_selector_all_calls.append(selector)
        return self._field_values

    async def screenshot(self, path):
        self.screenshot_calls.append(path)

    async def click(self, selector, timeout=5000):
        self.click_calls.append(selector)

    async def wait_for_load_state(self, state, timeout=5000):
        self.wait_for_load_state_called = True


def _patch_page(monkeypatch, page):
    async def _fake_ensure_page():
        return page

    monkeypatch.setattr(web_forms.browser_tool, "_ensure_page", _fake_ensure_page)


# ---- browser_generate_password ----------------------------------------


def test_browser_generate_password_returns_plaintext_and_persists_it():
    result = web_forms.browser_generate_password(site="tenable.com", username="damian@example.com")

    assert len(result["password"]) == 20
    assert result["site"] == "tenable.com"

    saved = credential_store.get_credential(web_forms.settings.form_credentials_path, site="tenable.com")
    assert saved["password"] == result["password"]


def test_browser_generate_password_respects_custom_length():
    result = web_forms.browser_generate_password(site="tenable.com", length=30)
    assert len(result["password"]) == 30


# ---- form_get_saved_credential / form_list_saved_credentials ----------


def test_form_get_saved_credential_found_after_generation():
    web_forms.browser_generate_password(site="tenable.com", username="damian@example.com")

    result = web_forms.form_get_saved_credential(site="tenable.com")

    assert result["found"] is True
    assert result["username"] == "damian@example.com"


def test_form_get_saved_credential_not_found():
    result = web_forms.form_get_saved_credential(site="nunca-registrado.com")
    assert result == {"found": False, "site": "nunca-registrado.com", "username": ""}


def test_form_list_saved_credentials_metadata_only():
    web_forms.browser_generate_password(site="tenable.com", username="damian@example.com")

    result = web_forms.form_list_saved_credentials()

    assert len(result["credentials"]) == 1
    assert result["credentials"][0]["site"] == "tenable.com"
    assert "password" not in result["credentials"][0]


# ---- browser_preview_submit --------------------------------------------


@pytest.mark.anyio
async def test_browser_preview_submit_dry_run_never_clicks(monkeypatch):
    page = _FakePage([
        {"name": "full_name", "type": "text", "value": "Damian Zupel"},
        {"name": "email", "type": "email", "value": "damian@example.com"},
        {"name": "password", "type": "password", "value": "s3cr3tPass!"},
    ])
    _patch_page(monkeypatch, page)

    result = await web_forms.browser_preview_submit(submit_selector="#submit")

    assert result["submitted"] is False
    assert page.click_calls == []
    assert len(page.screenshot_calls) == 1
    fields_by_name = {f["name"]: f for f in result["fields"]}
    assert fields_by_name["full_name"]["value"] == "Damian Zupel"
    assert fields_by_name["password"]["value"] == "•" * len("s3cr3tPass!")  # nunca en claro


@pytest.mark.anyio
async def test_browser_preview_submit_with_confirm_clicks_and_returns_after_screenshot(monkeypatch):
    page = _FakePage([{"name": "email", "type": "email", "value": "damian@example.com"}])
    _patch_page(monkeypatch, page)

    result = await web_forms.browser_preview_submit(submit_selector="#submit", confirm=True)

    assert result["submitted"] is True
    assert page.click_calls == ["#submit"]
    assert len(page.screenshot_calls) == 1
    assert page.wait_for_load_state_called is True


@pytest.mark.anyio
async def test_browser_preview_submit_defaults_to_scanning_the_whole_body(monkeypatch):
    page = _FakePage([{"name": "email", "type": "email", "value": "damian@example.com"}])
    _patch_page(monkeypatch, page)

    await web_forms.browser_preview_submit(submit_selector="#submit")

    assert page.eval_on_selector_all_calls == ["body input, body textarea, body select"]


@pytest.mark.anyio
async def test_browser_preview_submit_scopes_field_reading_when_scope_selector_given(monkeypatch):
    """Regresión del bug real encontrado en la primera prueba end-to-end contra
    un sitio real (registro de Nessus Essentials, 2026-08-16): sin acotar, el
    resumen de dry-run barría TODA la página y mezclaba campos de OTRO widget
    (una calculadora de precios más abajo en la misma página) que no tenían
    nada que ver con el formulario que se estaba completando."""
    page = _FakePage([{"name": "email", "type": "email", "value": "damian@example.com"}])
    _patch_page(monkeypatch, page)

    await web_forms.browser_preview_submit(submit_selector="#submit", fields_scope_selector="#try-form")

    assert page.eval_on_selector_all_calls == ["#try-form input, #try-form textarea, #try-form select"]


@pytest.mark.anyio
async def test_browser_preview_submit_excludes_hidden_and_empty_fields(monkeypatch):
    page = _FakePage([
        {"name": "csrf_token", "type": "hidden", "value": "abc123"},
        {"name": "submit_btn", "type": "submit", "value": "Enviar"},
        {"name": "middle_name", "type": "text", "value": ""},
        {"name": "email", "type": "email", "value": "damian@example.com"},
    ])
    _patch_page(monkeypatch, page)

    result = await web_forms.browser_preview_submit(submit_selector="#submit")

    names = {f["name"] for f in result["fields"]}
    assert names == {"email"}
