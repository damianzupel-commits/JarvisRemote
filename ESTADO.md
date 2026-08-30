# ESTADO.md — Instantánea del proyecto

> Estado operativo del repo. Para el contexto estructural (arquitectura, modelos,
> convenciones, gates de seguridad) ver `CLAUDE.md`. **Actualizá este archivo al
> cerrar cada sesión** (ver protocolo al final).

**Última actualización:** 2026-08-30
**Último commit:** `e83c99b feat: instrumentacion de tokens/costo en el harness + ingesta de videos nuevos al vault + update de comandas y tabla`
**Rama:** `master` — **al día con `origin/master`** (pusheado; respaldo remoto OK).
**Working tree:** puede haber cambios de la sesión en curso — commitear al cerrar.

---

## Sesión 2026-08-30 — lo más reciente (leé esto primero)

**Cerebro cambiado a DeepSeek V4 Pro** vía OpenRouter (pay-as-you-go). En `backend/.env`:
`LMSTUDIO_BASE_URL=https://openrouter.ai/api/v1`, `LMSTUDIO_MODEL=deepseek/deepseek-v4-pro-0813`,
`LLM_API_KEY=<key de OpenRouter>`. Backup de la config local (Ollama / `jarvis-text-v2`) en
`backend/.env.bak-openrouter`. ⚠️ **El selector de modelo de la tray-app PISA esta config**
(la vuelve a `jarvis-text-v2`) — si usás DeepSeek, no toques el selector (bug anotado en `TABLA.md`).

**Costo bajo control:** el prompt pesa ~30k tokens (system prompt + 103 tools por llamada),
pero DeepSeek cachea automático (~99% cache-hit una vez caliente) → ~US$0.0008 por pedido simple.
Se agregó instrumentación de tokens/costo por llamada en `agent.py` (`_log_llm_usage` → `general.log`).
Optimización opcional pendiente: mandar menos de 103 tools por llamada.

**Sistema de cocina (cómo se organiza el trabajo):** `COMANDAS.md` (riel de tareas; 4 pasos:
entra comanda → tabla → fuego → emplatado; **UNA en el fuego a la vez**), `TABLA.md` (ideas crudas
sin confirmar), `recetario/` (servicios/procedimientos; ⭐ receta 01 = Blindaje PyME), `PROVEEDORES.md`,
`docs/LA-BRIGADA.md`, `docs/raphael/` (documentación completa del proyecto).

**Prioridad ACTUAL: primera venta (Blindaje PyME).** El servicio que se vende AHORA es la versión
**LITE** (backups + Defender full/Tamper Protection + SmartScreen + updates de Windows +
contraseñas/wifi), entregable en un día — **NO** la receta 01 "gourmet" (kernel-grade, semanas).
Herramienta de venta: `Escritorio/Blindaje-PyME-Checklist-15min.md` (chequeo con permiso → informe → precio).

**Ingesta YouTube:** 49/52 videos de la playlist "Info para Jarvis" ingeridos al vault con
discernimiento de relevancia; fix de traducción (pt→es/en) agregado; faltan ~3 por bloqueo temporal
de IP de YouTube (re-run cuando levante).

---

## Índice — dónde vive cada cosa

- **Qué es el proyecto / arquitectura / modelos / gates de seguridad:** `CLAUDE.md`
- **Estado y prioridades:** este archivo (`ESTADO.md`)
- **Riel de tareas (qué hacer y en qué orden):** `COMANDAS.md` · **Ideas crudas:** `TABLA.md`
- **Servicios y procedimientos vendibles:** `recetario/` · **Proveedores/ingredientes:** `PROVEEDORES.md`
- **Brigada de agentes:** `docs/LA-BRIGADA.md` · **Docs completas del proyecto:** `docs/raphael/`
- **Base de conocimiento (notas de video, seguridad, negocio):** `backend/obsidian_vault/jarvis/`
- **Diseños de laboratorio y defensa:** `lab/` (cyber range, defensa kernel-grade, orquestación remota)
- **Config y secretos:** `backend/.env` (**NO se commitea** — el repo es PÚBLICO)
- ⚠️ **Material PERSONAL de Damian (proyecto Fénix, análisis psicológicos) vive en un vault APARTE,
  `C:\Users\dam\Vault-Fenix` — NO es parte de este proyecto, NO va al repo público ni al contexto de Raphael.**

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
  - **[2026-08-17] Gate de consentimiento del submit ahora con enforcement a
    nivel código** (antes dependía SOLO del prompt del modelo). `browser_preview_submit`
    con `confirm=false` emite un **preview token de un solo uso** (`pv-xxxxxxxx`)
    atado a `submit_selector` + URL de la página + timestamp, guardado en un store
    en memoria con TTL corto (`FORM_PREVIEW_TOKEN_TTL_SECONDS`, default 300s).
    `confirm=true` ahora EXIGE el nuevo parámetro `preview_token`: sin él, o con uno
    de otro formulario/página, vencido o ya usado, el submit se **rechaza sin hacer
    click**. Mismo espíritu que el `proposal_id` de `selfrepair`. Archivos:
    `app/tools/web_forms.py` (store + validación), `app/config.py` (TTL),
    `app/skills.py` (prompt actualizado), `tests/test_web_forms.py` (cobertura del
    gate). Tests de web_forms en verde (17/17).
- **Pentesting activo**: sqlmap, OWASP ZAP y captura de paquetes (scapy) sumados
  a nmap, todos detrás del gate único `authorized_targets.yaml`.
- **Pipeline de auto-reparación** (`selfrepair/`) con gate de aprobación manual,
  **testing automático** (detección/runner/store) y **escaneo de seguridad/calidad**
  con modelo de hallazgos unificado + triage + benchmark OWASP.
- **Cliente cloud** (Google AI / Gemini Flash) + tools `cloud_expert_*` y
  `opencode_run_task`.
- **~70 notas nuevas en el vault** de conocimiento (`backend/obsidian_vault/jarvis/`).
- **Modelo de chat:** histórico → local `jarvis-text-v2` (Qwen3-30B) → `gpt-oss:120b-cloud`
  (Ollama cloud, pegaba límite semanal) → **HOY: `deepseek/deepseek-v4-pro-0813` vía OpenRouter**
  (ver la sección "Sesión 2026-08-30" arriba y la sección de modelos en `CLAUDE.md`).

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

## Cyber range (en armado)

Se está montando el **laboratorio de pentesting aislado** para probar los módulos
ofensivos y de detección de Jarvis (diseño en `lab/CYBER-RANGE-DESIGN.md` +
`lab/DETECCION-ESTRES-NOCTURNO.md`). **Guía de continuación:
`lab/RETOMAR-LAB.md`** — leela para retomar sin perder el hilo.

Estado actual (2026-08-17):

- **VirtualBox 7.2.14** + Extension Pack instalados (se fue con el plan B del
  diseño; VMware era la recomendación, pero VBox es válido — sin auto-snapshots,
  se hacen a mano).
- **Kali 2026.2** importada: Adaptador 1 = Red interna "labnet" (ataque, aislada),
  Adaptador 2 = NAT (solo updates, apagar en ataques).
- **Metasploitable 2** creada con `Metasploitable.vmdk`, Adaptador 1 = labnet
  (una sola placa, sin NAT).
- **Servidor DHCP en labnet** (`VBoxManage dhcpserver add`): rango
  10.13.37.100–200, server-ip 10.13.37.1, máscara 255.255.255.0. Coincide con el
  `10.13.37.0/24` del diseño.
- **Quedó a mitad:** Metasploitable booteando; falta loguear (msfadmin/msfadmin),
  sacar IP con `ifconfig`, encender Kali (kali/kali) y verificar conectividad +
  tomar snapshots BASE. Ver checklist en `lab/RETOMAR-LAB.md` §2.

Pendientes destacados del range: instalar Docker Desktop (DVWA/Juice Shop/Caldera),
Atomic Red Team + MITRE Caldera v5, agregar `10.13.37.0/24` a
`authorized_targets.yaml` a mano antes de que Jarvis toque los blancos, y
registrar Nessus Essentials en tenable.com (Damian, desde el celular).

## Orquestación remota (diseño nuevo, sin implementar)

**Diseño: `lab/ORQUESTACION-REMOTA-DESIGN.md`** (2026-08-17, solo diseño, no toca
código). Cómo Damian controla a Jarvis **desde el celular estando fuera de casa**
para orquestar el cyber range (abrir/manejar VMs, lanzar pentest/detección en
labnet, reportar) sin debilitar ningún gate existente. Decisiones clave:

- **Canal remoto solo por Tailscale** (nada expuesto a internet, router sin
  puertos abiertos): backend atado a la interfaz Tailscale vía `tailscale serve`
  (o bind a la IP `100.x`), grant de tailnet celular↔PC solo-ese-puerto.
- **Auth por dispositivo** (token/JWT) guardado con **DPAPI** (reusa el patrón de
  `forms/credential_store.py` e `investigation/keys.py`), revocable/rotable — no
  el `API_KEY` único en claro de hoy.
- **Tools nuevas (spec, no código):** `vm_control` (wrapper de `VBoxManage` con
  allow-list de VMs del lab + audit firmado) y `ssh_guest` (SSH a Kali por una
  interfaz de gestión, blancos aún restringidos por `authorized_targets.yaml`).
- **Cola de misiones** con estados (encolada→corriendo→necesita-confirmación→
  completada/fallida) y **confirmaciones remotas** para pasos gated, atadas a cada
  paso al estilo `preview_token`/`proposal_id`.
- **Plan por fases** (menor→mayor riesgo): 1) `vm_control` local · 2) endpoint
  autenticado sobre Tailscale · 3) `ssh_guest` · 4) cola de misiones + confirmación
  remota. Requisito físico: PC prendida (opción Wake-on-LAN documentada).

## Defensa "kernel-grade" gratis (diseño nuevo, sin implementar)

**Diseño: `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`** (2026-08-17, solo diseño, no toca
código, no instala nada). Cómo acercar `app/malware/` a un EDR **sin driver propio
ni certificado EV** ($0, riesgo de BSOD nulo). Tesis: **orquestar los componentes
de kernel que Windows ya trae firmados por Microsoft** en vez de escribir código de
kernel. Decisiones clave:

- **Detección (consumir telemetría de kernel):** ETW en tiempo real (pywintrace /
  PythonForWindows), Sysmon (ampliar `sysmon_monitor.py` de Event ID 8/10 a
  1/3/7/11/22, config SwiftOnSecurity), AMSI para fileless, auditoría 4688+cmdline.
  ETW le da al `behavioral_watcher` el **PID+imagen** que hoy le falta para matar al
  proceso que cifra, no solo detectar el patrón.
- **Bloqueo real sin driver propio (confirmado):** Defender **ASR** rules (bloqueo
  en kernel vía `Set-MpPreference`, ej. dump de LSASS), **WDAC** (Code Integrity,
  enforcement antes de cargar en memoria), **AppLocker** (más simple/evadible), y
  **WFP** (filtros de red desde user-mode con `fwpuclnt`, capa ALE, sin driver).
- **Circuito de respuesta:** evento de kernel → correlación → contención (matar
  proceso / cortar red por WFP / cuarentena reversible / snapshot) → `store` firmado
  Ed25519 → nota a Obsidian. Preventivo (ASR/WDAC/AppLocker/WFP pre-cargados) vs.
  contención posterior (detectar→matar siempre deja una ventana).
- **Plan por fases (por esfuerzo):** 1) Sysmon+config+consumo · 2) ETW tiempo real ·
  3) AMSI · 4) enforcement (ASR→AppLocker→WDAC→WFP), **siempre audit mode antes de block**.
- **Checklist de prioridades (por cuánto protege): `lab/DEFENSA-PRIORIDADES.md`**
  (2026-08-17, solo documentación). Complementa al diseño con el orden priorizado
  por protección: 0) Defender full + Tamper Protection (paso cero) · 1) AppLocker→WDAC
  (lo que más protege, más esfuerzo) · 2) ASR · 3) AMSI · 4) Sysmon+ETW (capa sensorial)
  · 5) WFP. Regla transversal: todo lo que bloquea va primero en **modo auditoría**.
- **Límite honesto:** no veta creación de proceso *antes* del hecho de forma
  arbitraria (solo por regla), canal Event Log manipulable, AMSI evadible, rootkits
  no detectables desde el host. Recién ahí valdría un driver firmado.

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
- **Pusheado:** `master` está **al día con `origin/master`** (últimos respaldos:
  2026-08-30, commits `f1017f2` → `e83c99b`). El respaldo remoto ya no es un pendiente.

---

## Protocolo de cierre de sesión

**Al terminar cualquier sesión de trabajo en este repo:**

1. Actualizá este `ESTADO.md`: fecha, último commit, en qué quedaste, qué quedó a
   medias, próximos pasos.
2. Commiteá los cambios con un mensaje `docs:` (ej.
   `docs: actualiza ESTADO tras <lo que hiciste>`).
3. Si corresponde y Damian lo autorizó, pusheá a `origin` para no perder trabajo.
   Recordá que el repo es **público**: no commitees secretos.
