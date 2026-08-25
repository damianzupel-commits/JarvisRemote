# 03 · Registro de tools y catálogo completo

## El registro (`app/tools/__init__.py`)

Cada módulo de `tools/` se registra a sí mismo con el decorator `register_tool` al importarse. El agente
pide `openai_tool_schemas()` para el listado en formato *function calling* de OpenAI, y usa
`call_tool(name, args)` para ejecutar la elegida.

### `@dataclass Tool` y `register_tool(name, description, parameters, target="pc")`

`Tool` guarda `name`, `description`, `parameters` (JSON Schema de objeto), `handler` (función sync o
async) y `target`. El decorator registra en `_registry: dict[str, Tool]` y rechaza nombres duplicados.

- `get_tools()` → copia del registro.
- `openai_tool_schemas()` → lista de schemas para el LLM.
- **`target`**: `"pc"` (handler local) o `"phone"` (se despacha al celular por WebSocket). El LLM ve una
  lista plana, no distingue el origen.

### `call_tool(name, arguments)` — el router

1. Si el nombre está en **`_RECORDABLE_TOOL_NAMES`** y `SCREEN_RECORDING_ENABLED` y no hay grabación
   activa → arranca una grabación de pantalla (una sola por turno; errores de ffmpeg nunca bloquean la
   tool real).
2. Si `target == "phone"` → `dispatch_to_phone(name, arguments, timeout)`; si la tool trae su propio
   `timeout` (ej. `phone_run_command`), extiende el timeout de espera del WebSocket a ese valor + 5 s.
3. Si el handler es de un **módulo bloqueante** (`_BLOCKING_MODULES = ("app.tools.desktop",)`) o su
   nombre está en **`_BLOCKING_TOOL_NAMES`** (nmap, sqlmap, captura de paquetes, ZAP, escaneos de
   malware) → corre en un thread aparte con `asyncio.to_thread` para no bloquear el event loop (esas
   tools tienen `subprocess.run`/polling/sleeps reales de segundos o minutos). El resto corre inline
   (y se awaitea si es corrutina).

### Conjuntos especiales

- **`_BLOCKING_MODULES`** — por módulo (cualquier tool nueva de `desktop.py` queda cubierta).
- **`_BLOCKING_TOOL_NAMES`** — por nombre; `network_scan.py` mezcla `nmap_scan` (síncrona, va acá) con
  `phone_nmap_scan` (async, no va), así que no puede clasificarse por módulo.
- **`_RECORDABLE_TOOL_NAMES`** — el pipeline auditoría→fix→test que se graba automáticamente
  (`security_scan_project`, `security_triage_findings`, `security_audit_find_fix_verify`,
  `quality_scan_project`, `code_apply_fix`, `code_run_tests`, `selfrepair_propose_fix`,
  `audit_generate_report`).

### Módulos importados al final (auto-registro)

filesystem, browser, web_forms, desktop, pc_command, phone, reflect, codebase, obsidian, security_scan,
quality_scan, code_edit, test_run, selfrepair, audit_report, network_scan, research, opencode,
cloud_expert, investigation, recording, pentest_sqlmap, pentest_wireshark, pentest_zap, malware,
ingestion.

**Desactivadas (comentadas, NO importadas):** `video_gen` (`generate_video`) e `image_gen`
(`generate_image`) — precaución de hardware real: el 2026-07-27 la PC se apagó físicamente durante un
cómputo de GPU de `generate_video`. No hay sandbox de software contra un problema térmico/de fuente; hay
que resolverlo a nivel hardware antes de reexponerlas.

## Skills (`app/skills.py`) — carga bajo demanda de subconjuntos

En vez de mandar siempre el prompt completo + las 58 tools, `agent` clasifica el mensaje del usuario de
forma **determinística por palabras clave** (nunca una llamada al modelo para decidir esto) y arma un
prompt + subconjunto de tools. Si ningún skill matchea, cae al `SYSTEM_PROMPT` completo + todas las
tools (nunca al revés). Motivación: el prompt-processing inicial de cada turno es la parte más pesada.

- **`@dataclass Skill`**: `name`, `trigger_keywords`, `prompt_fragment`, `tool_names`.
- **`CORE_TOOL_NAMES` / `CORE_PROMPT`** — **siempre presentes** sin importar el skill: `jarvis_reflect`,
  `fs_*`, `research_topic`, `obsidian_*`, `recording_start/stop`. `research_topic`/`obsidian_*` viven en
  core porque el gate de `fs_write_file` exige poder llamarlas para desbloquearse.
- **`classify(message) -> set[str]`** — normaliza (minúsculas, sin acentos vía `_normalize`) y matchea
  por substring; puede devolver varios skills o ninguno.
- **`tools_for_active_skills(names)`** — `CORE_TOOL_NAMES ∪` tools de cada skill (siempre superset).
- **`prompt_for_active_skills(names)`** — `CORE_PROMPT` + fragmentos en orden estable (para el cacheo de
  prompt del servidor de inferencia, que solo reusa el prefijo si es byte-a-byte idéntico).

### Los 8 skills y sus disparadores

| Skill | Keywords (muestra) | Tools |
|-------|--------------------|-------|
| `investigation` | "caso de investigación", "evidencia digital", "mapeo de columnas" | las 18 `investigation_*` |
| `security_audit` | "seguridad", "vulnerabilidad", "escane", "auditá", "reparar", "test", "build" | `security_*`, `quality_*`, `code_apply_fix`, `code_run_tests`, `audit_generate_report`, `codebase_*`, `selfrepair_propose_fix`, `pc_run_command` |
| `pentesting` | "pentest", "sqlmap", "nmap", "exploit", "zap", "wireshark" | `nmap_scan`, `phone_nmap_scan`, `sqlmap_scan`, `packet_capture_*`, `zap_scan` |
| `malware_protection` | "malware", "virus", "ransomware", "cuarentena", "me hackearon" | las 11 `malware_*` |
| `code_delegation` | "opencode", "gemini", "mod de fabric", "minecraft" | `opencode_run_task`, `cloud_expert_code`, `cloud_expert_marketing` |
| `desktop_control` | "pantalla", "click", "ventana", "navegador", "formulario"* | `browser_*` (control), `desktop_*` |
| `web_forms` | "formulario", "registrame", "crear cuenta", "sign up" | `browser_generate_password`, `browser_preview_submit`, `form_*` |
| `phone_control` | "celular", "whatsapp", "cámara", "foto", "swipe" | las 12 `phone_*` de UI/archivos |

\* "formulario" dispara tanto `desktop_control` (para tener `browser_open/type/click`) como `web_forms`
(que es disjunto por tools, no por keywords).

---

## Catálogo completo de tools

Todas tienen `target="pc"` salvo donde se indica `target="phone"`. Detalle de la lógica en el archivo
de subsistema correspondiente.

### Filesystem (`filesystem.py`) — sandbox `_resolve`
`fs_list_dir`, `fs_read_file`, `fs_write_file` (con gate de Obsidian + circuito auditado si el archivo
cae en un repo git ya indexado), `fs_create_dir`, `fs_move_path`, `fs_delete_path` (deshabilitada salvo
`FS_ALLOW_DELETE=true`). → [10](10-control-pc-celular.md), sandbox en [14](14-seguridad-transversal.md).

### Navegador (`browser.py`) — Playwright/Chromium
`browser_open`, `browser_click`, `browser_type`, `browser_select_option`, `browser_get_text`,
`browser_screenshot`, `browser_close`. → [10](10-control-pc-celular.md).

### Web forms (`web_forms.py`)
`browser_generate_password` (contraseña al azar, nunca inventada por el modelo; se guarda cifrada DPAPI),
`browser_preview_submit` (dry-run obligatorio → `preview_token` de un solo uso), `form_get_saved_credential`,
`form_list_saved_credentials`. → [09](09-web-forms-credenciales.md).

### Escritorio (`desktop.py`) — pyautogui/pywinauto (módulo bloqueante)
`desktop_screenshot`, `desktop_list_windows`, `desktop_focus_window`, `desktop_click`,
`desktop_click_element`, `desktop_type_text`, `desktop_press_key`, `desktop_move_mouse`, `desktop_scroll`,
`desktop_launch_app`. → [10](10-control-pc-celular.md).

### Shell PC (`pc_command.py`)
`pc_run_command` (shell real vía `shell_exec`; flag `PC_SHELL_ENABLED` + blocklist de patrones
destructivos + auditoría; cwd sandboxeado por `filesystem._resolve`). → [10](10-control-pc-celular.md).

### Celular (`phone.py`) — `target="phone"` salvo indicado
UI/archivos (target=phone): `phone_open_app`, `phone_list_dir`, `phone_read_file`, `phone_write_file`,
`phone_tap`, `phone_swipe`, `phone_type_text`, `phone_read_screen`, `phone_global_action`.
Ejecutadas en el backend (target=pc) pero que despachan al celular: `phone_run_command`,
`phone_take_photo`, `phone_record_video`. → [10](10-control-pc-celular.md).

### Reflexión (`reflect.py`)
`jarvis_reflect` (memoria de criterio propia, JSONL; `action=query|save`, con `tipo` y `contexto`).
→ [08](08-conocimiento-obsidian.md).

### Codebase (`codebase.py`)
`codebase_index_project`, `codebase_search_symbol`, `codebase_file_outline`. → [04](04-auditoria-codigo.md).

### Obsidian (`obsidian.py`)
`obsidian_save_note`, `obsidian_search_notes`, `obsidian_list_notes`. → [08](08-conocimiento-obsidian.md).

### Seguridad de código (`security_scan.py`)
`security_scan_project` (Semgrep/Bandit/cppcheck/clang-tidy/Trivy), `security_get_finding`,
`security_audit_find_fix_verify` (aplica+commit+verifica atómico), `security_triage_findings`.
→ [04](04-auditoria-codigo.md).

### Calidad (`quality_scan.py`)
`quality_scan_project` (Ruff/mypy/ESLint/tsc/detekt), `quality_get_finding`. → [04](04-auditoria-codigo.md).

### Edición y tests (`code_edit.py`, `test_run.py`, `audit_report.py`)
`code_apply_fix` (dry-run→confirm, cada fix su commit git), `code_run_tests`, `audit_generate_report`.
→ [04](04-auditoria-codigo.md).

### Self-repair (`selfrepair.py`)
`selfrepair_propose_fix` (solo propone, genera `proposal_id` formato `sf-xxxxxxxx`). → [04](04-auditoria-codigo.md).

### Red / pentesting (`network_scan.py`, `pentest_*.py`)
`nmap_scan`, `phone_nmap_scan` (desde el celular vía Termux), `sqlmap_scan`, `packet_capture_scan`,
`packet_capture_analyze`, `zap_scan`. Todas gateadas por `authorized_targets.yaml`. → [06](06-pentesting-red.md).

### Malware (`malware.py`)
`malware_scan_path`, `malware_full_scan_run`, `malware_full_scan_status`, `malware_list_findings`,
`malware_quarantine_restore`, `malware_quarantine_delete` (dry-run→confirm), `malware_check_integrity`,
`malware_rebuild_integrity_baseline`, `malware_check_process`, `malware_check_sysmon_experimental`,
`malware_verify_log`. → [05](05-malware-defensa.md).

### Investigación forense (`investigation.py`)
18 tools `investigation_*`: crear caso, mapeo de columnas, ingesta (CSV, WhatsApp, Telegram, server log,
imagen, documento), NER (proponer/listar/confirmar/rechazar), fusión de identidades, describir imagen,
exportar informe. → [07](07-investigacion-forense.md).

### Investigación web y delegación (`research.py`, `opencode.py`, `cloud_expert.py`)
`research_topic` (navega páginas reales con Edge, guarda notas trazables), `opencode_run_task` (delega a
la CLI OpenCode), `cloud_expert_code` / `cloud_expert_marketing` (Gemini Flash; requieren
`confirm_non_sensitive=true`). → [08](08-conocimiento-obsidian.md).

### Ingesta (`ingestion.py`)
`youtube_ingest_playlist` (playlist → transcripción → resumen LLM → nota en el vault). → [08](08-conocimiento-obsidian.md).

### Grabación (`recording.py`)
`recording_start`, `recording_stop` (control manual; el resto es automático). → [10](10-control-pc-celular.md).

### Desactivadas (no registradas)
`generate_image` (Flux.1 Schnell / ComfyUI), `generate_video` (Wan 2.2 / ComfyUI).
