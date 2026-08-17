# ESTADO.md — Instantánea del proyecto

> Estado operativo del repo. Para el contexto estructural (arquitectura, modelos,
> convenciones, gates de seguridad) ver `CLAUDE.md`. **Actualizá este archivo al
> cerrar cada sesión** (ver protocolo al final).

**Última actualización:** 2026-08-17
**Último commit:** `33fe302 docs: actualiza READMEs con los modulos nuevos (malware, selfrepair, testing)`
**Rama:** `master` — 39 commits locales por delante de `origin/master` (sin pushear).
**Working tree:** limpio.

---

## En qué se estaba trabajando (últimas sesiones)

El trabajo reciente (ver últimos ~15 commits) fue una tanda grande de features
que quedaron integradas y commiteadas:

- **Módulo de protección antimalware** (`backend/app/malware/`, spec 2026-08-16):
  YARA + ClamAV + heurística conductual + FIM + monitor del proceso propio +
  cuarentena reversible. Integrado al agente y con tests. Sysmon quedó como capa
  experimental **apagada** por default.
- **Completado de formularios web** con credential store cifrado (DPAPI) +
  `shell_exec`, con dry-run + preview obligatorio antes de cualquier submit.
- **Pentesting activo**: sqlmap, OWASP ZAP y captura de paquetes (scapy) sumados
  a nmap, todos detrás del gate único `authorized_targets.yaml`.
- **Pipeline de auto-reparación** (`selfrepair/`) con gate de aprobación manual,
  **testing automático** (detección/runner/store) y **escaneo de seguridad/calidad**
  con modelo de hallazgos unificado + triage + benchmark OWASP.
- **Cliente cloud** (Google AI / Gemini Flash) + tools `cloud_expert_*` y
  `opencode_run_task`.
- **~70 notas nuevas en el vault** de conocimiento (`backend/obsidian_vault/jarvis/`).
- **Cambio de modelo de chat a `gpt-oss:120b-cloud`** (Ollama cloud) en
  `backend/.env` — antes corría local en `jarvis-text-v2` (Qwen3-30B-A3B). Ver
  la sección de modelos en `CLAUDE.md`.

## Lo más reciente y todavía sin cerrar

Las últimas notas del vault (`arquitectura-jarvis`, 2026-08-16/17) documentan una
**decisión de diseño pendiente que necesita el input de Damian**, no código:

### Sandboxing en contenedor para `pc_run_command` y `browser` (PROPUESTO, no implementado)

Nota completa:
`backend/obsidian_vault/jarvis/propuesta-sandboxing-en-contenedor-para-pc-run-command-y-browser.md`.

Contexto: `pc_run_command` es una blocklist de texto, no un sandbox real, y
`FS_ALLOWED_ROOT` por default es el **HOME entero**. La propuesta acota el radio
de daño metiendo `pc_run_command` + `browser_*` en un container Linux (Docker),
**sin tocar** `desktop_*` (necesita GUI de Windows) ni las tools de pentesting
(no pasan por `shell_exec`).

Estado de la infraestructura (verificado 2026-08-16):
- **Docker: NO instalado.** WSL2: sí (prerrequisito listo). Falta un solo paso:
  Damian instala Docker Desktop (MSI + UAC, no automatizable por Jarvis).

**Mitigación barata pendiente (cero riesgo, no requiere Docker):** achicar
`FS_ALLOWED_ROOT` en `backend/.env` de `Path.home()` a solo
`C:\Users\dam\Documents\JarvisRemote` + carpetas de proyectos que Jarvis cree.
Cambio de una línea que ya reduce muchísimo la superficie de ataque.

**Dos decisiones de arquitectura que Damian tiene que tomar antes de implementar:**
1. ¿El backend FastAPI entero corre dentro del container (más simple de razonar,
   pero complica `desktop_*`/`phone_*` que sí o sí van en el host) o solo un
   container "worker" que el backend en host controla vía `docker exec`?
2. ¿Vale el costo de RAM/CPU de Docker Desktop siempre corriendo (la PC ya tuvo
   apagados por consumo) o el container se levanta solo bajo demanda?

## Próximos pasos sugeridos

1. **Respaldo remoto**: pushear los 39 commits locales a `origin` (público). No
   se pusheó todavía a la espera de tu OK (ver abajo). Este es el paso más
   urgente para no volver a perder trabajo.
2. **Mitigación barata de sandbox**: achicar `FS_ALLOWED_ROOT` en `backend/.env`
   (independiente de Docker, cero riesgo).
3. **Decidir el enfoque de sandboxing en contenedor** (las 2 preguntas de arriba)
   e instalar Docker Desktop si se aprueba.
4. **Verificar el modelo activo**: confirmar que `gpt-oss:120b-cloud` es el que se
   quiere dejar por default, o volver a `jarvis-text-v2` local. Correr
   `ollama list` en la PC para confirmar qué está realmente instalado (no se pudo
   verificar desde esta sesión, ver nota abajo).
5. Correr la suite de tests (`cd backend && pytest`) para confirmar que todo sigue
   en verde tras la última tanda de features.

## Notas / cabos sueltos

- **`ollama list` no se pudo correr desde esta sesión** (la sesión de la IA corre
  en un sandbox Linux aislado, sin acceso al Ollama de la PC). Los nombres de
  modelos en `CLAUDE.md` salen del código y la config real (`.env`,
  `.env.example`, Modelfiles), no de `ollama list`. Confirmá el modelo local
  instalado corriendo `ollama list` vos mismo.
- **Generación de video/imagen (ComfyUI) apagada** por consumo de energía real de
  la PC (apagados observados). Ver comentario en `app/tools/__init__.py`.
- **Bug de Playwright en esta PC**: el Chromium bundleado no arranca (firma SxS /
  antivirus Reason/RAV) — `browser.py` usa `channel="msedge"` como workaround.

---

## Estado del respaldo remoto

- **Remoto:** `origin` = `https://github.com/damianzupel-commits/JarvisRemote.git`
- **Accesible:** sí (verificado con `git ls-remote`).
- **Visibilidad:** **PÚBLICO** (confirmado en GitHub el 2026-08-17).
- **Sin pushear:** los 39 commits locales (incluido el commit de docs de hoy)
  siguen solo en local, a la espera del OK de Damian para pushear a un repo
  público. `origin/master` está en `cfb6d09` (el remoto muestra 42 commits).

---

## Protocolo de cierre de sesión

**Al terminar cualquier sesión de trabajo en este repo:**

1. Actualizá este `ESTADO.md`: fecha, último commit, en qué quedaste, qué quedó a
   medias, próximos pasos.
2. Commiteá los cambios con un mensaje `docs:` (ej.
   `docs: actualiza ESTADO tras <lo que hiciste>`).
3. Si corresponde y Damian lo autorizó, pusheá a `origin` para no perder trabajo.
   Recordá que el repo es **público**: no commitees secretos.
