---
author: jarvis
category: arquitectura-jarvis
created: '2026-08-17T03:27:47.458090+00:00'
tags:
- arquitectura
- seguridad
- sandboxing
- propuesta
title: 'Propuesta: sandboxing en contenedor para pc_run_command y browser'
updated: '2026-08-17T03:27:47.458090+00:00'
---

Diseño propuesto (NO implementado) para acotar el radio de daño de las dos tools de mayor privilegio de Jarvis, sin tocar `desktop_*` (necesita GUI real de Windows, no puede vivir en un container). Investigado y documentado el 2026-08-16, a pedido de Damian, como paso previo a una decisión suya -- no se escribió código de producción para esto todavía.

## Por qué esto y por qué ahora

Dos hechos concretos, verificados contra el código real:

1. **`pc_run_command` es blocklist de texto, no sandbox real** -- lo dice el propio docstring de `backend/app/tools/pc_command.py`: cualquier comando que no matchee un patrón "obviamente destructivo" (format, rm -rf /, shutdown, fork bombs) corre igual, sin restricción adicional.
2. **`FS_ALLOWED_ROOT` (el sandbox de filesystem/cwd) por default es el HOME ENTERO del usuario** (`app/config.py:47`, `Path.home()`), no solo `JarvisRemote/` -- un comando fuera del blocklist ya tiene acceso de lectura/escritura a Documents, Desktop, Downloads, etc. hoy mismo, sin containers de por medio.

El fix de prompt injection del paso 1 reduce la probabilidad de que un comando malicioso llegue a ejecutarse, pero es defensa de UNA capa (el modelo puede fallar en seguir la instrucción, o Damian mismo puede pedir sin querer algo peligroso confiando en que el blocklist lo va a frenar). Esta propuesta es la segunda capa: si algo malicioso o destructivo llega a `pc_run_command`, que el daño quede contenido.

## Mitigación más barata primero (no requiere Docker)

Antes de containerizar nada: achicar `FS_ALLOWED_ROOT` en `backend/.env` de `Path.home()` a la carpeta específica que Jarvis necesita (ej. solo `C:\Users\dam\Documents\JarvisRemote` + las carpetas de proyectos nuevos que cree). Es un cambio de una línea de config, cero riesgo, y ya reduce la superficie real de `pc_run_command`/`fs_write_file` de "todo el home" a "lo que Jarvis de verdad necesita tocar" -- independiente de si se containeriza o no, y no depende de que Damian instale nada.

## Estado real de la infraestructura en esta PC

Verificado el 2026-08-16:
- **Docker: NO instalado** (`docker --version` -> command not found).
- **WSL2: SÍ instalado y configurado** (`wsl --status` -> distro default Ubuntu, versión 2) -- es el prerrequisito que pide Docker Desktop en Windows, así que falta un solo paso (instalar Docker Desktop), no una cadena de dependencias.
- Instalar Docker Desktop necesita un instalador MSI + probablemente un prompt de UAC -- mismo patrón ya visto con nmap (ver `project_nmap_scan_status`), no algo que Jarvis pueda automatizar solo. Le queda a Damian.

## Qué se containeriza y qué NO

**SÍ**: `pc_run_command` (`app/shell_exec.py` + `app/tools/pc_command.py`) y `browser_*` (`app/tools/browser.py`) -- las dos tools que ejecutan código/procesos arbitrarios y no dependen de la GUI de Windows.

**NO**:
- `desktop_*` (pyautogui/pywinauto) -- necesita acceso directo a la sesión gráfica de Windows, no tiene sentido dentro de un container Linux.
- `nmap_scan`/`sqlmap_scan`/`zap_scan`/`packet_capture_*` -- son implementaciones propias en `app/tools/network_scan.py` y `app/pentest/*`, NO pasan por `shell_exec.run_shell_command` ni por `pc_run_command` -- quedan exactamente como están, este cambio no los toca.
- `fs_read_file`/`fs_write_file` -- son I/O simple (no ejecutan código arbitrario), se quedan corriendo en el host tal cual, pero necesitan ver los MISMOS archivos que el container (ver mapeo de filesystem abajo).
- `phone_*` -- ya corren en el celular, no en esta PC, no aplica.

## Mapeo de filesystem

`FS_ALLOWED_ROOT` (el mismo límite que ya usa `filesystem._resolve`, sin inventar un segundo boundary) se bind-mountea al container en un path fijo, ej. `/workspace`. `fs_write_file` (que sigue corriendo en el host) y `pc_run_command` (que pasaría a correr DENTRO del container) terminan viendo el mismo archivo en dos paths distintos (`C:\...\proyecto\archivo.py` en el host, `/workspace/proyecto/archivo.py` en el container) apuntando al mismo inode via el bind mount -- el `cwd` relativo que ya usa `pc_run_command` hoy (relativo a `FS_ALLOWED_ROOT`) se traduce 1:1 a relativo a `/workspace` del lado del container, sin cambiar el contrato de la tool hacia el LLM.

## `shell_exec.py` ya está listo para esto

Dato a favor encontrado al revisar el código: `run_shell_command`/`kill_process_tree` (`app/shell_exec.py`) YA están escritos con un branch explícito `sys.platform == "win32"` vs. el resto (taskkill vs. `os.killpg`+`SIGKILL`, `CREATE_NEW_PROCESS_GROUP` solo en Windows). Corriendo dentro de un container Linux, automáticamente toma la rama Linux -- no hace falta reescribir esa lógica, solo cambiar CÓMO se lanza el proceso (via `docker exec` en vez de `subprocess.Popen` directo).

## `browser.py`: qué cambia

Hoy usa `channel="msedge"` (el Edge del sistema, no el Chromium que trae Playwright) por un bug real de Windows: el Chromium bundleado de Playwright no arranca en esta PC por un problema de firma/manifiesto SxS (antivirus Reason/RAV) -- ver el comentario largo en `browser.py::_ensure_page`. Ese bug es específico de ESTE Windows con ESTE antivirus: dentro de un container Linux no existe ese problema (es un entorno totalmente distinto), así que adentro del container se podría volver al Chromium estándar de Playwright sin el workaround de `channel="msedge"`. Detalle a favor, no un blocker.

**Importante, ya verificado en la sesión de hoy**: `browser.py` lanza SIEMPRE un contexto nuevo sin cookies (`_browser.new_context()`) -- nunca reusa el perfil de Chrome/Edge real de Damian ni queda logueado en ninguna cuenta. Containerizarlo no pierde ninguna sesión que hoy no tenga -- es una ventaja para este cambio puntual, no una limitación nueva.

## Limitaciones reales (no las escondo)

- **Docker Desktop en Windows corre containers Linux por default** (vía el backend WSL2 que ya está instalado). Cualquier tarea que de verdad necesite algo NATIVO de Windows dentro de `pc_run_command` (compilar un .exe con MSVC, correr un script de PowerShell que dependa de módulos de Windows, tocar el registro) NO va a funcionar dentro de un container Linux -- sería una regresión funcional real para ese subconjunto de tareas, no algo que se pueda ignorar. Mitigación posible: un flag opcional para correr ciertos comandos "fuera del container, en el host, con confirmación explícita" en vez de sandboxear el 100% de los casos.
- Docker Desktop en Windows tiene su propio costo de RAM/CPU corriendo en background -- en una PC que ya tuvo apagados por consumo de energía real (ver el comentario sobre `generate_video`/`generate_image` desactivadas en `app/tools/__init__.py`), vale la pena medir el impacto antes de dejarlo siempre corriendo.
- Que las tools obviamente destructivas del blocklist actual (`format`, `vssadmin delete`, etc.) directamente NO EXISTAN dentro de un container Linux es una ventaja lateral (ni hace falta blocklistearlas ahí), pero implica que ese blocklist específico de Windows se vuelve irrelevante para el path containerizado -- habría que mantenerlo igual para el fallback nativo si se agrega la opción de arriba.

## Pasos de implementación, si Damian aprueba el enfoque

1. Achicar `FS_ALLOWED_ROOT` ya (mitigación barata, sin Docker, ver arriba) -- independiente del resto.
2. Damian instala Docker Desktop (WSL2 backend, ya tiene el prerrequisito) -- paso manual, un instalador + UAC.
3. Imagen base chica (`python:3.12-slim` + Node si hace falta + Playwright con sus deps de Chromium) con `/workspace` como bind mount target.
4. Reescribir `run_shell_command` para que, si `settings.pc_shell_sandboxed=true` (flag nuevo, default false hasta validar), despache el comando via `docker exec` al container persistente en vez de `subprocess.Popen` directo -- mismo timeout/truncado/kill-de-árbol que hoy, cambia solo el "dónde" corre.
5. Migrar `browser._ensure_page` a lanzar el Chromium DENTRO del container (¿vía un puerto de depuración remota de Playwright expuesto del container al host, o corriendo el server de FastAPI entero dentro del container? -- esto necesita una decisión de arquitectura más grande que no tomé acá, ver "decisión pendiente" abajo).
6. Tests: correr la suite real de `test_pc_command.py`/`test_browser_tool.py` contra el container antes de activar el flag por default.

## Decisión pendiente de Damian

Dos preguntas de diseño que no puedo resolver sin su input:
- **¿El backend de FastAPI entero corre dentro de un container** (más simple de razonar, pero significa mover TODO Jarvis a Docker, no solo dos tools -- afecta `desktop_*`/`phone_*` que si o si necesitan quedarse en el host, complicando el split), **o solo un container "worker" separado que el backend en host controla vía `docker exec`/API** (más trabajo de plumbing, pero dejaría el resto de Jarvis sin tocar)? La propuesta de arriba asume la segunda opción por ser la de menor impacto en lo que ya funciona, pero es una decisión real de arquitectura, no un detalle menor.
- **¿Vale la pena el costo de RAM/CPU de Docker Desktop corriendo siempre** en esta PC dado el historial de apagados por consumo, **o conviene que el container se levante solo bajo demanda** (más lento en el primer `pc_run_command` de cada sesión, pero no consume nada en reposo)?

## Notas relacionadas
- [[Índice: arquitectura-jarvis]]