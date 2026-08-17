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

from pathlib import Path
from datetime import datetime, timezone

from .. import audit_log
from ..config import settings
from ..forms import credential_store
from . import browser as browser_tool
from . import register_tool


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
        "submit_selector y devuelve una segunda captura del resultado."
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
                "description": "Default false (dry-run, no hace click). true para enviar de verdad -- solo después de confirmación explícita del usuario.",
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
async def browser_preview_submit(submit_selector: str, confirm: bool = False, fields_scope_selector: str = "body") -> dict:
    page = await browser_tool._ensure_page()
    fields = await _read_visible_form_fields(page, fields_scope_selector)

    if not confirm:
        screenshot_path = _preview_screenshot_path("preview")
        await page.screenshot(path=str(screenshot_path))
        result = {
            "submitted": False,
            "url": page.url,
            "screenshot_path": str(screenshot_path),
            "fields": fields,
            "note": (
                "Dry-run -- todavía no se hizo click en nada. Mostrale esto al usuario (captura + campos) "
                "y esperá su confirmación explícita antes de volver a llamar con confirm=true."
            ),
        }
        audit_log.log_tool_call(
            target="pc",
            tool="browser_preview_submit",
            arguments={"submit_selector": submit_selector, "confirm": False, "fields_scope_selector": fields_scope_selector},
            result=result,
        )
        return result

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
        arguments={"submit_selector": submit_selector, "confirm": True, "fields_scope_selector": fields_scope_selector},
        result=result,
    )
    return result
