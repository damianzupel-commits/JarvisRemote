"""Tests de app/llm_client.py -- bug real de v6 (corregido vía Opción C
2026-08-11): sin timeout explícito, el SDK usaba su default (600s), superado
por una generación real lenta, disparando un reintento automático que
reprocesaba el prompt completo desde cero."""

from __future__ import annotations

from app import llm_client
from app.config import settings


def test_client_has_an_explicit_timeout_configured():
    assert llm_client.client.timeout is not None
    assert float(llm_client.client.timeout) == settings.llm_request_timeout_seconds


def test_client_disables_automatic_retries():
    """max_retries=0 -- reintentar automáticamente contra un servidor local de
    un solo proceso no tiene ningún beneficio real (no hay rate-limiting ni
    error transitorio de red), solo reprocesa el prompt completo para nada."""
    assert llm_client.client.max_retries == 0


def test_timeout_setting_defaults_to_1800_seconds():
    """Chequeo estático del default (en vez de recargar app.config con un env
    var distinto): reload() de un módulo compartido re-ejecuta TODO su cuerpo
    -- incluida la generación de un api_key nuevo al azar -- y contamina el
    objeto `settings` que ya tienen importado otros módulos para el resto de
    la sesión de tests. Confirmado real: un primer intento con reload() hizo
    que un test de otro archivo (test_phone_link.py) se colgara, porque
    terminó usando settings sin mockear."""
    import inspect

    from app import config as config_module

    source = inspect.getsource(config_module)
    assert 'os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "1800")' in source
