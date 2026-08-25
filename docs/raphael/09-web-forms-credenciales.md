# 09 · Formularios web y credenciales (`app/tools/web_forms.py`, `app/forms/`)

Completado de formularios y registros web reales, pensado para cuando Damian lo pide **lejos de la PC**
(ej. desde el celular). Reusa el navegador Playwright/Edge ya controlado por `tools/browser.py`
(`browser_open`/`browser_type`/`browser_click` completan los campos); este módulo agrega solo las dos
piezas que faltaban: generación de contraseñas y el gate de consentimiento del submit.

## `app/forms/credential_store.py` — store de credenciales (DPAPI)

- **`generate_strong_password(length=20)`** — contraseña al azar (`secrets`) de un charset amplio
  (letras+dígitos+puntuación) que **excluye** comillas, backslash y backtick (rompen inputs HTML/JS mal
  escapados de terceros). Mínimo 12 caracteres.
- **`save_credential(*, path, site, username, password)`** — persiste en un **único archivo cifrado como
  un solo blob DPAPI** (`FORM_CREDENTIALS_PATH`, `.dpapi`). `_load_entries`/`_save_entries` cifran/descifran.
- **`list_credentials(path)`** — lista sitios/usuarios (sin exponer contraseñas).
- **`get_credential(path, site, username="")`** — recupera una credencial guardada.

**Por qué DPAPI:** ata el cifrado a la cuenta de Windows actual — nadie puede descifrar el archivo
copiándolo a otra máquina o con otra cuenta. Mismo mecanismo que `investigation/keys.py`. Texto plano
fue descartado a propósito (mismo antipatrón que las API keys en claro del `.env`). **Limitación:** si el
disco se mueve o Windows se reinstala, el blob viejo no se recupera.

## Gate de consentimiento del submit (`preview_token`)

Endurecido a nivel código el 2026-08-17: que `browser_preview_submit` hiciera **siempre** un dry-run
antes del submit real dejó de depender solo del prompt. Ahora:

1. El **dry-run** (`confirm=false`) saca una captura de la página (a `FORM_PREVIEW_DIR`), devuelve los
   valores actuales de los campos (contraseña enmascarada) **y** emite un **`preview_token` de un solo
   uso**, atado a `submit_selector` + URL de la página + timestamp. Store en memoria (TTL corto, no hace
   falta persistir).
2. El **submit real** (`confirm=true`) **debe** traer ese `preview_token`. El código valida existencia,
   match exacto de selector+página, no-reuso y no-vencimiento (`FORM_PREVIEW_TOKEN_TTL_SECONDS`=300)
   antes de hacer click; si algo falla, rechaza sin tocar el botón.

Mismo espíritu que el `proposal_id` de self-repair: el flujo dry-run → revisión de Damian → OK → confirm
queda **obligado por el código**, no solo sugerido por el prompt. **Sin lista blanca de dominios**
(decisión de Damian: confía en la orden explícita de cada pedido) — por eso el prompt del skill instruye
a nunca tratar texto de una página ya abierta como una orden real.

## Tools (`tools/web_forms.py`)

- **`browser_generate_password`** — genera la contraseña al azar (nunca elegida por el modelo, nunca
  reutilizada) para un `site`, la guarda cifrada y la muestra en el chat (única vez en texto plano).
- **`browser_preview_submit`** — el gate dry-run→confirm descrito arriba.
- **`form_get_saved_credential`** — recupera una credencial generada previamente.
- **`form_list_saved_credentials`** — lista sitios/usuarios con credencial guardada.

El skill `web_forms` es disjunto por tools del skill `desktop_control` (que aporta
`browser_open/type/click`); "formulario" dispara ambos. Ver [03](03-tools-registro-catalogo.md).
