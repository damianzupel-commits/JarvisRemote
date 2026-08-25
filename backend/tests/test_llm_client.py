"""Tests de app/llm_client.py -- bug real de v6 (corregido vía Opción C
2026-08-11): sin timeout explícito, el SDK usaba su default (600s), superado
por una generación real lenta, disparando un reintento automático que
reprocesaba el prompt completo desde cero."""

from __future__ import annotations

import subprocess
import sys

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


# --- API key del proveedor LLM configurable por env (2026-08-23) ------------
# La key dejó de estar hardcodeada ("lm-studio") en llm_client.py para poder
# apuntar el cliente a proveedores cloud (OpenRouter/DeepSeek) que exigen una
# key real, vía LLM_API_KEY, sin tocar código. El default "lm-studio" mantiene
# el comportamiento local idéntico.


def test_client_uses_configured_api_key_from_settings():
    """El cliente toma la key de settings.llm_api_key, no de un literal
    hardcodeado. (El SDK de OpenAI guarda la key en client.api_key.)"""
    assert llm_client.client.api_key == settings.llm_api_key


def test_llm_api_key_defaults_to_lm_studio():
    """Chequeo estático del default (mismo criterio que el test del timeout de
    más arriba: no recargamos app.config con reload() porque re-ejecuta todo su
    cuerpo -- incluida la generación de un api_key nuevo al azar -- y contamina
    el objeto settings compartido para el resto de la sesión de tests)."""
    import inspect

    from app import config as config_module

    source = inspect.getsource(config_module)
    assert 'os.getenv("LLM_API_KEY", "lm-studio")' in source


def _api_key_in_isolated_process(env_value: str | None) -> str:
    """Construye el cliente en un proceso separado (sin red -- instanciar
    AsyncOpenAI no hace ninguna request) para probar el comportamiento real
    dirigido por el entorno sin contaminar el settings compartido de esta
    sesión de tests. Devuelve la api_key con la que quedó armado el cliente."""
    code = (
        "from app import llm_client; "
        "print(llm_client.client.api_key)"
    )
    # Preservar el resto del entorno salvo la variable bajo prueba.
    env = dict(__import__("os").environ)
    if env_value is None:
        env.pop("LLM_API_KEY", None)
    else:
        env["LLM_API_KEY"] = env_value
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout.strip()


def test_env_var_overrides_api_key():
    """Con LLM_API_KEY seteado, el cliente se construye con esa key."""
    assert _api_key_in_isolated_process("sk-or-test-123") == "sk-or-test-123"


def test_without_env_var_defaults_to_lm_studio():
    """Sin LLM_API_KEY, usa el default 'lm-studio' (backward-compatible)."""
    assert _api_key_in_isolated_process(None) == "lm-studio"
