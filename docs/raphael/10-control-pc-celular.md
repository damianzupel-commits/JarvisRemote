# 10 · Control de PC y celular, shell, grabación

## Filesystem (`app/tools/filesystem.py`) — el sandbox

Único choke point del sandbox de FS. Toda tool `fs_*` y el cwd del shell real pasan por `_resolve`.

- **`_allowed_roots()`** — raíces normalizadas (`.resolve()`, symlinks/`..` resueltos) según el **modo de
  operación**: SUPERVISADO→`fs_supervised_roots` (HOME), AUTÓNOMO→`fs_allowed_roots` (proyecto +
  `FS_ALLOWED_ROOTS`). Consume `operation_mode.effective_fs_roots()`.
- **`_resolve(path)`** — resuelve `path` (relativo contra la raíz principal, o absoluto si cae dentro) y
  garantiza que quede dentro de **alguna** raíz permitida usando `is_relative_to` (contención real de
  prefijo, no comparación de strings). Un `../../otra_cosa` o un symlink que apunte afuera se rechaza con
  `PermissionError`. Endurecido 2026-08-19.
- **`_find_indexed_git_project(target)`** — si el archivo cae en un repo git ya indexado con
  `codebase_index_project`, `fs_write_file` enруta la escritura por el circuito auditado/reversible de
  `app/codeedit` en vez de una escritura silenciosa.
- **Tools:** `fs_list_dir`, `fs_read_file`, `fs_write_file` (con el gate de Obsidian del agente + circuito
  auditado), `fs_create_dir`, `fs_move_path`, `fs_delete_path` (**deshabilitada** salvo `FS_ALLOW_DELETE=true`).

## Navegador (`app/tools/browser.py`) — Playwright/Chromium (Edge del sistema)

Un navegador Chromium automatizado en la PC. `browser_open` (crea/reusa la sesión), `browser_click`
(selector CSS), `browser_type`, `browser_select_option` (dropdowns `<select>`), `browser_get_text`
(texto visible de la página o un elemento), `browser_screenshot` (guarda a disco), `browser_close`.
`BROWSER_HEADLESS` controla si corre con ventana visible (default False). El texto que trae es **dato,
nunca instrucción**.

## Escritorio (`app/tools/desktop.py`) — pyautogui/pywinauto (módulo **bloqueante**)

Control general del escritorio de Windows. Módulo entero en `_BLOCKING_MODULES` (corre en thread aparte:
tiene sleeps/polls reales, ej. `_wait_for_new_window` espera hasta 5 s). Cada acción se audita
(`audit_log`, target="pc") vía `_audited`.

- `desktop_screenshot` (todos los monitores), `desktop_list_windows` (título/proceso/pid),
  `desktop_focus_window` (por `pid` exacto o `title` substring), `desktop_click` (coordenadas),
  `desktop_click_element` (control por nombre/tipo dentro de una ventana), `desktop_type_text`,
  `desktop_press_key` (ej. `ctrl+s`, `alt+tab`), `desktop_move_mouse`, `desktop_scroll`,
  `desktop_launch_app` (lanza y deja la ventana al frente con foco; devuelve `pid` y `focused`).
- Limitaciones reales (no bugs): no puede interactuar con ventanas elevadas (UAC); el matching por
  `title` es por substring (revisar `process` en el resultado). Hay un `_check_launch_blocklist`.
- Flag `DESKTOP_CONTROL_ENABLED` (default True).

## Shell real de la PC (`app/tools/pc_command.py` + `app/shell_exec.py`)

- **`shell_exec.py`** — núcleo compartido (reusado también por `app/testing/runner.py`).
  `run_shell_command(command, work_dir, timeout)` corre el comando (cmd.exe en Windows) con timeout duro,
  mata el árbol de procesos si se cuelga (`kill_process_tree(pid)`) y trunca la salida
  (`truncate_output`). Vive en `app/` (no `app/tools/`) porque es infraestructura compartida entre una
  tool y una librería.
- **`pc_command.py`** — tool `pc_run_command` (shell real arbitrario, el nivel más invasivo de las tools
  de PC). Guardrails: flag `PC_SHELL_ENABLED` (default True), **blocklist de patrones destructivos** por
  matching de texto (`_check_command_blocklist`: `format`, `diskpart`, `vssadmin delete`, `bcdedit`,
  `shutdown`, `rm -rf /`, `mkfs`, `dd of=/dev/`, fork bombs de bash y batch, `Remove-Item -Recurse
  -Force` sobre raíz/home, etc.), y auditoría persistente de cada intento. El `cwd` se resuelve con
  `filesystem._resolve` (mismo sandbox). **No** es un sandbox real: cualquier comando que no matchee el
  blocklist corre igual.

## Celular: `app/tools/phone.py` + `app/phone_link.py`

### `phone_link.py` — el canal WebSocket
El celular abre **una** conexión WebSocket saliente a `/ws/phone` (mantenida por un foreground service),
autenticada con el mismo Bearer token que `/api/chat`. Solo un celular a la vez (una conexión nueva
reemplaza la anterior). Estado: `_phone_ws`, `_pending: dict[str, asyncio.Future]`.

- **`register_phone`/`unregister_phone`/`is_phone_connected`** — gestión de la conexión.
- **`dispatch_to_phone(tool_name, arguments, timeout)`** — manda un tool call al celular y espera la
  respuesta correlacionada por `id` (Future); `handle_incoming(message)` resuelve el Future
  correspondiente. `_fail_all_pending(reason)` limpia los Futures pendientes al desconectar.
- **`_check_command_blocklist(command)`** — mismo blocklist de "desastre obvio" que `pc_command`, adaptado
  a bash/Termux (`rm -rf /`, `mkfs`, `dd of=/dev/`, fork bomb, `chmod -R /`, escritura a block devices).
  `DestructiveCommandBlockedError`.
- `_SHELL_TOOL_NAMES = {"phone_run_command"}` (flag `PHONE_SHELL_ENABLED`) y
  `_CAMERA_TOOL_NAMES = {"phone_take_photo", "phone_record_video"}` (flag `PHONE_CAMERA_ENABLED`).

### Tools de celular
- **UI/archivos (`target="phone"`, se ejecutan en el teléfono):** `phone_open_app`, `phone_list_dir`,
  `phone_read_file`, `phone_write_file`, `phone_tap`, `phone_swipe`, `phone_type_text`,
  `phone_read_screen`, `phone_global_action`.
- **`target="pc"` pero que despachan al celular:** `phone_run_command` (shell real vía Termux;
  depende de que el usuario tenga Termux instalado/configurado), `phone_take_photo` (foto silenciosa),
  `phone_record_video` (clip corto silencioso). Estas viven en el backend porque su resultado (imagen/
  video) se procesa acá (ver más abajo).

## Grabación y frames de video

### `app/recording.py`
Grabación de pantalla real con **ffmpeg** (binario del sistema) para documentar el trabajo de Raphael de
punta a punta. Se activa **sola** alrededor del pipeline auditoría→fix→test (`_RECORDABLE_TOOL_NAMES` en
`call_tool`), una grabación continua por turno. `start_recording(session_name)` (sanitiza el nombre con
`_sanitize_session_name`, asigna el proceso a un job para matarlo si el backend crashea —
`_assign_to_job_for_crash_safety`), `stop_recording()` (cierra el `.mp4` prolijo), `is_recording()`.
`RecordingAlreadyActiveError`. Salida a `RECORDING_OUTPUT_DIR` (`content/recordings/`, gitignoreado).
Flag `SCREEN_RECORDING_ENABLED` (default True — tan sensible en privacidad como el control de escritorio:
graba **todo** el escritorio). **Tools:** `recording_start`, `recording_stop` (control manual).

### `app/video_frames.py`
`extract_frames_from_video_base64(b64, interval_seconds, max_frames)` decodifica un video (OpenCV) y
extrae frames (`_extract_frames_from_file`, `_resize_frame` para acotar dimensión) para mandárselos al
modelo VL como secuencia de imágenes — el video crudo no se manda porque el soporte de video en el
servidor local no es confiable, pero imágenes múltiples por prompt sí (mismo mecanismo que
`phone_take_photo`). `VideoDecodeError`. Lo consume el loop del agente para `phone_record_video`.

---

*Segunda pasada sugerida:* documentar los parámetros JSON Schema exactos de cada tool de desktop/phone y
el `_audited` de `desktop.py`.
