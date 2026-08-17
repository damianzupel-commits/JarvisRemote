"""Tools para completar formularios y registros web reales (spec de Damian,
2026-08-16 -- pensado para cuando lo pide estando lejos de la PC, ej. desde
el celular, y algo requería antes estar sentado frente a la PC por un
instalador con UAC o un formulario de registro).

Reusa el mismo navegador Playwright/Edge ya controlado por `app/tools/
browser.py` (`browser_open`/`browser_type`/`browser_click` alcanzan para
completar los campos) -- este módulo agrega solo las dos piezas que faltaban:

1. `browser_generate_password`: generación real de contraseñas fuertes
   (nunca elegidas por el LLM), persistidas cifradas con DPAPI vía
   `app/forms/credential_store.py` (ver ese módulo para el razonamiento
   completo de la decisión de diseño).
2. `browser_preview_submit`: mismo patrón dry-run -> `confirm=true` que
   `code_apply_fix`/la cuarentena de malware -- ANTES de enviar CUALQUIER
   formulario (decisión explícita de Damian: sin excepción, ni para
   formularios simples de nombre+email) saca una captura + un resumen de los
   valores actuales de los campos, y solo hace click de verdad en una
   segunda llamada explícita con `confirm=true`.

Sin lista blanca de dominios (decisión explícita de Damian, misma ronda de
preguntas: confía en la orden explícita de cada pedido en vez de un archivo
previo) -- por eso el prompt de este skill (ver `app/skills.py`) instruye
explícitamente a nunca tratar texto de una página ya abierta como si fuera
una orden real de Damian.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

from .. import audit_log
from ..config import settings
from ..forms import credential_store
from . import browser as browser_tool
from . import register_tool


# --- Gate de consentimiento con enforcement a nivel código (2026-08-17) -------
#
# Hasta ahora, que browser_preview_submit hiciera SIEMPRE un dry-run antes de un
# submit real dependía SOLO del prompt del skill (ver app/skills.py): nada en el
# código impedía que el modelo llamara directo con confirm=true sin previsualizar.
# Eso es exactamente el nivel de confianza que ya falló antes en otros gates (ver
# app/selfrepair/gate.py, que por eso exige un proposal_id concreto). Acá se
# imita ese patrón, adaptado a que browser_preview_submit es UNA sola tool con
# dos fases (no dos tools como propose/apply): el dry-run emite un "preview
# token" de un solo uso atado a submit_selector + URL de la página + timestamp, y
# confirm=true DEBE traer ese token. El código valida existencia, match exacto de
# selector+página, no-reuso y no-vencimiento antes de hacer click; si algo falla,
# rechaza sin tocar el botón. Así el flujo dry-run -> revisión de Damian -> OK ->
# confirm queda obligado por el código, no solo sugerido por el prompt.
#
# Store en memoria (mismo criterio de volumen bajo que app/selfrepair/store.py,
# pero acá ni siquiera hace falta persistirlo: un preview solo tiene sentido
# dentro de la misma sesión del backend/navegador, y su TTL corto lo hace
# efímero por diseño).


@dataclass
class _PreviewToken:
    token: str
    submit_selector: str
    url: str
    created_at_monotonic: float
    used: bool = False


# token -> _PreviewToken. Se limpia solo (los vencidos se descartan al validar).
_preview_tokens: dict[str, "_PreviewToken"] = {}


def _now_monotonic() -> float:
    """Reloj monotónico (no se ve afectado por cambios de hora del sistema) --
    aislado en una función para poder mockearlo en los tests de expiración."""
    return time.monotonic()


def _generate_preview_token() -> str:
    return f"pv-{secrets.token_hex(4)}"


def _register_preview_token(submit_selector: str, url: str) -> str:
    token = _generate_preview_token()
    _preview_tokens[token] = _PreviewToken(
        token=token,
        submit_selector=submit_selector,
        url=url,
        created_at_monotonic=_now_monotonic(),
    )
    return token


def _validate_preview_token(preview_token: str | None, submit_selector: str, url: str) -> str | None:
    """Devuelve un mensaje de error si el token NO habilita el submit de este
    submit_selector+página, o None si es válido. NO consume el token (eso lo hace
    el caller recién si de verdad va a hacer click) -- así un token válido no se
    quema por un error posterior no relacionado."""
    if not preview_token:
        return (
            "Falta preview_token. confirm=true requiere el token que devolvió el dry-run "
            "(browser_preview_submit con confirm=false) para ESTE mismo formulario. Hacé primero el "
            "dry-run, mostrale el resultado a Damian, y recién con su OK volvé a llamar pasando ese "
            "preview_token."
        )
    entry = _preview_tokens.get(preview_token)
    if entry is None:
        return (
            "preview_token inválido o desconocido. Tiene que ser exactamente el que devolvió un dry-run "
            "reciente de browser_preview_submit -- generá uno nuevo con confirm=false y confirmá con Damian."
        )
    if entry.used:
        return (
            "Ese preview_token ya se usó (es de un solo uso: un submit por dry-run). Si necesitás enviar de "
            "nuevo, hacé otro dry-run con confirm=false y confirmá con Damian antes."
        )
    ttl = settings.form_preview_token_ttl_seconds
    if _now_monotonic() - entry.created_at_monotonic > ttl:
        _preview_tokens.pop(preview_token, None)  # vencido: descartarlo
        return (
            f"Ese preview_token venció (TTL {ttl}s). La página pudo haber cambiado desde el dry-run -- por "
            "seguridad hacé un dry-run nuevo con confirm=false y confirmá con Damian antes de enviar."
        )
    if entry.submit_selector != submit_selector:
        return (
            "El preview_token no corresponde a este submit_selector. Se emitió para "
            f"'{entry.submit_selector}', no para '{submit_selector}'. El token habilita el envío del MISMO "
            "botón que se previsualizó -- hacé un dry-run del botón correcto."
        )
    if entry.url != url:
        return (
            "El preview_token no corresponde a esta página. Se emitió para otra URL "
            f"('{entry.url}' vs '{url}') -- la navegación cambió desde el dry-run. Hacé un dry-run nuevo en "
            "la página actual y confirmá con Damian antes de enviar."
        )
    return None


def _preview_screenshot_path(suffix: str = "preview") -> Path:
    out_dir = Path(settings.form_preview_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return out_dir / f"{stamp}_{suffix}.png"


async def _read_visible_form_fields(page, scope_selector: str) -> list[dict]:
    """Lee los valores ACTUALES de los campos visibles del formulario
    directo del DOM (no de lo que el agente dice haber escrito) -- así el
    resumen de dry-run refleja de verdad lo que se va a enviar, incluso si
    el sitio modificó algo con su propio JS después de que Jarvis escribió.
    Enmascara el valor de campos type=password (ya se mostró en texto plano
    una vez al generarla, no hace falta repetirlo acá) y omite hidden/
    submit/button (ruido, no dato que Damian necesite revisar).

    `scope_selector` acota la lectura a los campos DENTRO de ese contenedor
    -- bug real encontrado en la primera prueba end-to-end contra un sitio
    real (registro de Nessus Essentials, 2026-08-16): sin acotar, esto barría
    TODA la página, y el resumen de dry-run traía también sliders/radios de
    una calculadora de precios de Nessus Professional más abajo en la MISMA
    página (nada que ver con el formulario de registro que se estaba
    completando) -- ruido real que hubiera confundido la revisión de Damian.
    Default 'body' preserva el comportamiento anterior para quien no pase un
    contenedor puntual, pero usar el selector del contenedor del formulario
    (ej. el id/div que envuelve el <form>) siempre que se conozca."""
    raw = await page.eval_on_selector_all(
        f"{scope_selector} input, {scope_selector} textarea, {scope_selector} select",
        "els => els.map(el => ({name: el.name || el.id || null, type: (el.type || el.tagName).toLowerCase(), value: el.value}))",
    )
    fields: list[dict] = []
    for item in raw or []:
        item = item or {}
        field_type = (item.get("type") or "").lower()
        if field_type in ("hidden", "submit", "button"):
            continue
        value = item.get("value") or ""
        if not value:
            continue
        if field_type == "password":
            value = "•" * len(value)
        fields.append({"name": item.get("name"), "type": field_type, "value": value})
    return fields


@register_tool(
    name="browser_generate_password",
    description=(
        "Genera una contraseña fuerte al azar (nunca inventada/elegida por el modelo) para completar un "
        "campo de contraseña de un formulario de registro, y la guarda cifrada con DPAPI (ligada a esta "
        "cuenta de Windows) en un archivo de credenciales para poder recuperarla después con "
        "form_get_saved_credential -- NO en texto plano. Devuelve la contraseña en texto plano en la "
        "respuesta de esta tool porque hace falta usarla ahora mismo (para escribirla en el campo con "
        "browser_type) y para que el usuario la vea al menos una vez. Usar SIEMPRE que un formulario pida "
        "crear una contraseña nueva, en vez de inventar una."
    ),
    parameters={
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": "Dominio o nombre del sitio (ej. 'tenable.com') -- clave para guardar/recuperar la credencial después.",
            },
            "username": {
                "type": "string",
                "description": "Usuario o email asociado a esta cuenta (default vacío).",
            },
            "length": {
                "type": "integer",
                "description": "Longitud de la contraseña (default 20, mínimo 12 sin importar lo que se pida).",
            },
        },
        "required": ["site"],
    },
)
def browser_generate_password(site: str, username: str = "", length: int = 20) -> dict:
    password = credential_store.generate_strong_password(length)
    credential_store.save_credential(
        path=settings.form_credentials_path, site=site, username=username, password=password
    )
    arguments = {"site": site, "username": username, "length": length}
    audit_log.log_tool_call(
        target="pc",
        tool="browser_generate_password",
        arguments=arguments,
        result={"site": site, "username": username, "password": "***redacted***"},
    )
    return {
        "password": password,
        "site": site,
        "username": username,
        "note": (
            f"Guardada cifrada con DPAPI en {settings.form_credentials_path} -- para recuperarla después "
            f"usá form_get_saved_credential(site='{site}')."
        ),
    }


@register_tool(
    name="form_get_saved_credential",
    description=(
        "Recupera una credencial generada previamente por browser_generate_password para un sitio dado "
        "(descifrando el archivo protegido con DPAPI). Usar cuando el usuario pregunta 'qué contraseña le "
        "puse a X' o necesita volver a entrar a un sitio donde Jarvis se registró antes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "site": {"type": "string", "description": "Dominio o nombre del sitio, igual al usado al generarla."},
            "username": {
                "type": "string",
                "description": "Usuario/email para desambiguar si hay más de una cuenta guardada para el mismo sitio (default vacío = la más reciente).",
            },
        },
        "required": ["site"],
    },
)
def form_get_saved_credential(site: str, username: str = "") -> dict:
    entry = credential_store.get_credential(settings.form_credentials_path, site=site, username=username)
    if entry is None:
        return {"found": False, "site": site, "username": username}
    return {"found": True, **entry}


@register_tool(
    name="form_list_saved_credentials",
    description=(
        "Lista los sitios/usuarios para los que Jarvis tiene una credencial generada guardada (solo "
        "metadata: sitio, usuario, fecha -- nunca las contraseñas de todas juntas). Usar para form_get_saved_credential "
        "por sitio puntual."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
def form_list_saved_credentials() -> dict:
    return {"credentials": credential_store.list_credentials(settings.form_credentials_path)}


@register_tool(
    name="browser_preview_submit",
    description=(
        "Previsualiza el envío de un formulario ANTES de enviarlo de verdad -- saca una captura de la "
        "página y devuelve los valores ACTUALES de todos los campos visibles (contraseñas enmascaradas). "
        "Con confirm=false (default) es un dry-run puro: NO hace click en nada, solo muestra qué se "
        "enviaría. Llamala SIEMPRE antes de tocar un botón de enviar/registrar, sin excepción -- incluso "
        "para un formulario simple de nombre+email -- y esperá que el usuario confirme explícitamente lo "
        "que ve antes de volver a llamarla con confirm=true, que recién ahí hace click de verdad en "
        "submit_selector y devuelve una segunda captura del resultado. El dry-run devuelve un preview_token "
        "de un solo uso: confirm=true EXIGE ese token (enforcement a nivel código, no solo del prompt) -- "
        "sin él, o con uno de otro formulario/página, vencido o ya usado, el submit se rechaza sin hacer click."
    ),
    parameters={
        "type": "object",
        "properties": {
            "submit_selector": {
                "type": "string",
                "description": "Selector CSS del botón/elemento que envía el formulario.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Default false (dry-run, no hace click). true para enviar de verdad -- solo después de confirmación explícita del usuario Y pasando el preview_token del dry-run.",
            },
            "preview_token": {
                "type": "string",
                "description": (
                    "Token de un solo uso que devolvió el dry-run (confirm=false) para ESTE mismo "
                    "submit_selector+página. Obligatorio cuando confirm=true. Vence a los pocos minutos y se "
                    "invalida al usarse -- si venció o ya se usó, hacé un dry-run nuevo. Ignorado en el dry-run."
                ),
            },
            "fields_scope_selector": {
                "type": "string",
                "description": (
                    "Selector CSS del contenedor del formulario (ej. el id/div que lo envuelve), para que el "
                    "resumen de campos NO barra toda la página -- default 'body'. Usalo SIEMPRE que sepas el "
                    "contenedor real: páginas con más de un widget/calculadora en la misma página (ej. otro "
                    "formulario o slider más abajo) pueden mezclar campos que no tienen nada que ver con lo "
                    "que se va a enviar si no se acota."
                ),
            },
        },
        "required": ["submit_selector"],
    },
)
async def browser_preview_submit(
    submit_selector: str,
    confirm: bool = False,
    fields_scope_selector: str = "body",
    preview_token: str = "",
) -> dict:
    page = await browser_tool._ensure_page()
    fields = await _read_visible_form_fields(page, fields_scope_selector)

    if not confirm:
        screenshot_path = _preview_screenshot_path("preview")
        await page.screenshot(path=str(screenshot_path))
        token = _register_preview_token(submit_selector, page.url)
        result = {
            "submitted": False,
            "url": page.url,
            "screenshot_path": str(screenshot_path),
            "fields": fields,
            "preview_token": token,
            "note": (
                "Dry-run -- todavía no se hizo click en nada. Mostrale esto al usuario (captura + campos) "
                "y esperá su confirmación explícita antes de volver a llamar con confirm=true. Cuando lo "
                f"confirme, pasá preview_token='{token}' (de un solo uso, vence a los "
                f"{settings.form_preview_token_ttl_seconds}s)."
            ),
        }
        audit_log.log_tool_call(
            target="pc",
            tool="browser_preview_submit",
            arguments={"submit_selector": submit_selector, "confirm": False, "fields_scope_selector": fields_scope_selector},
            result=result,
        )
        return result

    # confirm=true: enforcement a nivel código del dry-run previo. Sin un
    # preview_token válido para ESTE submit_selector+página no se hace click.
    token_error = _validate_preview_token(preview_token, submit_selector, page.url)
    if token_error is not None:
        result = {
            "submitted": False,
            "url": page.url,
            "fields": fields,
            "error": token_error,
        }
        audit_log.log_tool_call(
            target="pc",
            tool="browser_preview_submit",
            arguments={"submit_selector": submit_selector, "confirm": True, "fields_scope_selector": fields_scope_selector, "preview_token": preview_token or ""},
            result=result,
        )
        return result

    # Token válido: consumirlo AHORA (antes del click) -- de un solo uso, no
    # reutilizable ni siquiera si el click falla después.
    _preview_tokens[preview_token].used = True

    await page.click(submit_selector, timeout=5000)
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass  # algunos submits no navegan (ej. AJAX) -- seguir igual con la captura post-click
    screenshot_path = _preview_screenshot_path("after")
    await page.screenshot(path=str(screenshot_path))
    result = {
        "submitted": True,
        "url": page.url,
        "screenshot_path": str(screenshot_path),
        "fields": fields,
        "note": "Formulario enviado -- revisá la captura y la URL resultante para confirmar que salió bien.",
    }
    audit_log.log_tool_call(
        target="pc",
        tool="browser_preview_submit",
        arguments={"submit_selector": submit_selector, "confirm": True, "fields_scope_selector": fields_scope_selector, "preview_token": preview_token},
        result=result,
    )
    return result
