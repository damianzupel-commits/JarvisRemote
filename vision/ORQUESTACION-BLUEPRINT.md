# ORQUESTACION-BLUEPRINT.md — Plano definitivo de la arquitectura de orquestación de Jarvis

> **Documento de diseño / plano de construcción (no ejecutable, no es código).**
> Aterriza en el **código REAL** de `backend/app/` la estructura de orquestación
> que Damian ya decidió, para estudiarla y usarla como plano antes de construir.
> Es el paso concreto que sigue a `vision/ORQUESTACION-ESTRUCTURA.md` (el análisis
> y la elección de patrón): acá se define, rol por rol y fase por fase, **qué se
> construye, con qué tools reales, con qué gates, y en qué orden**.
>
> Creado: 2026-08-23. Solo lectura del código; **no toca nada, no commitea, no
> pushea**. Alinea con: `backend/app/agent.py`, `backend/app/skills.py`,
> `backend/app/operation_mode.py`, `backend/app/tools/` (registro real de tools),
> `backend/app/llm_client.py`, `backend/app/network/guardrail.py`, y los diseños
> `lab/ORQUESTACION-REMOTA-DESIGN.md`, `lab/DEFENSA-PRIORIDADES.md`.
> Cruza con la auditoría honesta de `vision/CAPACIDADES-REALES-DE-JARVIS.md` y la
> hoja de ruta de `vision/HACIA-RAPHAEL.md`.
>
> **Regla heredada de los otros docs de visión:** todo apunta a algo real del repo.
> Los nombres de tools, módulos y archivos son **exactos** (verificados por grep
> contra `register_tool(` en `app/tools/`). Donde un rol sugerido no tiene tools
> reales que lo respalden, se dice **FALTA/NO EXISTE** sin maquillarlo. Ningún gate
> ya decidido se debilita.
>
> **Decisiones de Damian que este plano RESPETA y no reabre:**
> 1. Comunicación **hub-and-spoke + pizarra compartida (vault)**: los especialistas
>    NO se hablan entre sí; reportan al orquestador (capataz) y colaboran leyendo/
>    escribiendo el vault. Nada de charla directa entre agentes (estilo CrewAI),
>    por costo y fragilidad con un modelo mediano.
> 2. Estructura **híbrida de 3 capas + router transversal de modelos**
>    (`ORQUESTACION-ESTRUCTURA.md §3`).
> 3. Cada rol/skill con su **caja de tools acotada (menor privilegio)**, aprovechando
>    que `Skill` ya declara `tool_names`.
> 4. **Cerebro nuevo: DeepSeek V4 vía OpenRouter** (API por token), con router de
>    modelos barato/potente.
> 5. **Dos modos**: supervisado (acceso amplio) / autónomo (sandbox), ya en
>    `operation_mode.py`.

---

## 1. Vista general — 3 capas + router + pizarra + modos

El patrón elegido es **híbrido**, con cada estilo en la capa donde rinde. El
orquestador (capataz) es el hub; los roles especialistas son los spokes; el vault
es la pizarra; el router de modelos es transversal; los dos modos de operación
gobiernan el radio de daño.

```
   TRIGGERS (cron / evento / misión encolada / chat / voz)
        │
        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ CAPA A — GRAFO DETERMINÍSTICO (estilo n8n)              [FASE 2-3]     │
 │  scheduler → pasos fijos → push a un canal (celular/escritorio).      │
 │  El flujo está ESCRITO; el LLM solo entra en un nodo que pide criterio.│
 │  Ej: brief matutino del escaneo diario, misión encolada.  Corre       │
 │  AUTÓNOMO por default (sandbox acotado, operation_mode).              │
 └───────────────┬──────────────────────────────────────────────────────┘
                 │ cuando un paso necesita criterio / lenguaje natural
                 ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ CAPA B — EL CAPATAZ / ORQUESTADOR  (agent.py, loop LLM→tool→LLM)      │
 │  ── HUB ──                                                            │
 │  · Planifica la tarea, consulta memoria (jarvis_reflect / obsidian).  │
 │  · classify(message) [skills.py] elige el/los dominio(s) = ROL(es).   │
 │  · Delega sub-tareas acotadas a los ROLES (Capa C), DE A UNO.         │
 │  · Verifica cada resultado (lee la pizarra) y arma la respuesta.      │
 └───────────────┬──────────────────────────────────────────────────────┘
   delega ▲ │ reporta         │  lee/escribe estado
          │ ▼ resultado        ▼
 ┌────────────────────────┐   ┌──────────────────────────────────────────┐
 │ CAPA C — ROLES         │   │  LA PIZARRA — Vault Obsidian (app/obsidian)│
 │ ESPECIALISTAS (spokes) │◀─▶│  backend/obsidian_vault/  (estado + memoria)│
 │  caja de tools acotada │   │  · cada rol escribe su hallazgo/nota        │
 │  (skills.py::tool_names)│  │  · otro rol/el capataz lo lee (search/list) │
 │  NO se hablan entre sí │   │  · sirve de historial en el tiempo         │
 │  (SOLO vía capataz +   │   │  · jarvis_reflect = memoria de procedimiento│
 │   vía pizarra)         │   └──────────────────────────────────────────┘
 └────────────────────────┘

   TRANSVERSAL A TODO:
   ROUTER DE MODELOS (llm_client.py)  [FASE 0]  — elige modelo por señal de
   dificultad (classify) + complejidad; barato (local jarvis-text-v2) vs
   potente (DeepSeek V4 vía OpenRouter, por token); con fallback.

   TRANSVERSAL A TODO:
   MODOS DE OPERACIÓN (operation_mode.py) — SUPERVISADO (root FS amplio) para
   chat/voz en vivo; AUTÓNOMO (sandbox acotado) para Capa A y misiones.
   Fail-safe: el default del proceso es AUTÓNOMO. Guardrail anti-auto-escalada:
   ni el capataz ni un rol pueden subir el modo desde dentro de un turno.
```

**Lo que ya existe hoy (punto de partida real, no de cero):** la Capa B es el loop
de `agent.py`. La selección de rol es `skills.classify()` + `tools_for_active_skills()`
(determinística, por keywords). Los "roles" **ya son las 8 skills** de `skills.py`,
cada una con su `tool_names` y su `prompt_fragment`. La pizarra es el vault de
`app/obsidian/` (ya con embeddings, autoría jarvis/humano, wikilinks). Los modos
están en `operation_mode.py`. **Lo que FALTA construir**: el router de modelos
(hoy es un solo modelo por config), el scheduler general (Capa A) y el push
saliente, y darle a cada skill identidad de "ejecutor invocable" (hoy es el mismo
turno con menos tools, no una sub-invocación con contexto propio).

**Matiz sobre "los roles no se hablan":** en la implementación actual esto ya es
verdad por construcción — no hay canal agente↔agente. Un "rol" hoy es simplemente
el conjunto de tools + prompt que el capataz tiene activo. Cuando en la Fase 1 los
roles pasen a ser sub-invocaciones con su propio contexto, la regla se mantiene: un
rol **devuelve su resultado al capataz** y **deja su rastro en la pizarra**; nunca
llama a otro rol. Toda coordinación pasa por el hub o por el vault.

---

## 2. Los roles especialistas (el corazón)

Cada rol agrupa **tools reales ya registradas** en `app/tools/` (verificado por
grep de `register_tool(`). El agrupamiento **no se inventa**: es el que ya define
`skills.py` (`SKILLS` dict + `CORE_TOOL_NAMES`). Por eso "construir los roles" es
en gran parte **formalizar lo que ya existe**, no crear de cero.

**Notación de modo (columna "modo"):** en qué modo de operación tiene sentido que
esa tool corra. **SUP** = solo/preferentemente supervisado (humano en vivo). **AUT**
= puede correr en autónomo (sandbox acotado) porque es reversible o de solo lectura.
**AUT+gate** = puede correr autónomo pero se detiene a pedir confirmación en el paso
irreversible. Esto es una **recomendación de diseño**: hoy el enforcement de modo es
solo sobre el sandbox de filesystem (`effective_fs_roots`), no por-tool — llevarlo a
por-tool es parte del trabajo (ver §6).

### 2.0 CORE — el rol base, SIEMPRE presente

No es un rol seleccionable: sus tools están en **todas** las invocaciones sin
importar qué skill matchee (`CORE_TOOL_NAMES`), por el acoplamiento del gate de
Obsidian de `fs_write_file` (ver docstring de `skills.py` y `agent.py::_obsidian_gate_error`).

| Tool real | Qué hace | Modo |
|---|---|---|
| `jarvis_reflect` | Memoria de procedimiento append-only (query/save) | AUT |
| `fs_read_file`, `fs_list_dir` | Lectura de filesystem (dentro de `effective_fs_roots`) | AUT |
| `fs_write_file`, `fs_create_dir`, `fs_move_path`, `fs_delete_path` | Escritura/mutación de FS (sandbox por modo) | AUT (acotado por sandbox) / SUP (root amplio) |
| `research_topic` | Investigación web puntual | AUT |
| `obsidian_search_notes`, `obsidian_save_note`, `obsidian_list_notes` | La **pizarra**: leer/escribir/listar notas del vault | AUT |
| `recording_start`, `recording_stop` | Control manual de grabación de pantalla (cross-cutting) | AUT |

**Gate propio:** `fs_write_file` está bloqueado hasta que en el turno se consultó
`obsidian_search_notes`/`research_topic` al menos una vez (gate anti-alucinación de
`_obsidian_gate_error`), y **bloqueado siempre** sobre el propio código de Jarvis
(`backend/`) — eso va por `selfrepair_propose_fix`. El sandbox de FS lo fija el modo
(`effective_fs_roots`): HOME amplio en SUPERVISADO, proyecto + `FS_ALLOWED_ROOTS` en
AUTÓNOMO.

### 2.1 Rol: Auditor de Código / Seguridad

- **(a) Responsabilidad.** El núcleo maduro y validado del repo: indexar un
  proyecto, escanear seguridad y calidad, triar, aplicar fixes reversibles (un
  commit por fix), correr tests, cerrar con informe. También proponer fixes al
  **propio** backend de Jarvis (dry-run).
- **(b) Tools reales** (skill `security_audit`, `_SECURITY_AUDIT_TOOL_NAMES`):

  | Tool | Función | Modo |
  |---|---|---|
  | `security_scan_project` | Semgrep/Bandit/Trivy/cppcheck/clang-tidy | AUT |
  | `security_get_finding` | Ver el código real de un hallazgo | AUT |
  | `security_triage_findings` | Triage de hallazgos | AUT |
  | `security_audit_find_fix_verify` | Ciclo atómico apply+commit+verify | AUT+gate |
  | `quality_scan_project`, `quality_get_finding` | Ruff/mypy | AUT |
  | `code_apply_fix` | Fix reversible (dry-run→confirm) | AUT+gate |
  | `code_run_tests` | Corre la suite real | AUT |
  | `audit_generate_report` | Cierre del ciclo | AUT |
  | `codebase_index_project`, `codebase_search_symbol`, `codebase_file_outline` | Grafo de código | AUT |
  | `selfrepair_propose_fix` | Propone fix al backend propio (SOLO dry-run) | AUT (propone) / SUP (aplicar) |
  | `pc_run_command` | Shell real (instalar deps, correr build/tests) | **SUP** (o AUT+gate) |
- **(c) Gates.** `code_apply_fix` es dry-run por default; aplicar de verdad requiere
  `confirm=true`. `selfrepair_propose_fix` **solo propone** (genera `proposal_id`
  `sf-xxxxxxxx`); aplicar exige que Damian escriba ese id a mano (`fs_write_file`
  sobre `backend/` está bloqueado siempre). `pc_run_command` **no es sandbox**: es
  blocklist de patrones destructivos + auditoría; radio de daño = `FS_ALLOWED_ROOT`.
- **(d) Modo.** Todo el escaneo/triage/report es AUT (solo lectura o reversible con
  commit). `pc_run_command` es el punto más invasivo: recomendado **SUPERVISADO**, o
  AUTÓNOMO con la mitigación pendiente de achicar `FS_ALLOWED_ROOT` primero.

### 2.2 Rol: Pentester / Red-team (lab)

- **(a) Responsabilidad.** Pentesting **ACTIVO** real contra sistemas de red,
  exclusivamente dentro del scope autorizado.
- **(b) Tools reales** (skill `pentesting`, `_PENTEST_TOOL_NAMES`):

  | Tool | Función | Modo |
  |---|---|---|
  | `nmap_scan` | Recon desde la PC | AUT+gate (scope) |
  | `phone_nmap_scan` | Recon desde el celular conectado | AUT+gate (scope) |
  | `sqlmap_scan` | Inyección SQL real (payloads) | **SUP** / AUT+gate |
  | `zap_scan` | OWASP ZAP (spider pasivo / full activo) | **SUP** / AUT+gate |
  | `packet_capture_scan` | Captura de tráfico (host_filter obligatorio) | **SUP** / AUT+gate |
  | `packet_capture_analyze` | Analiza un .pcap ya existente (sin gate de target) | AUT |
- **(c) Gates.** **Guardrail no negociable** (`app/network/guardrail.py::resolve_and_authorize`):
  todo target se valida contra `backend/authorized_targets.yaml` (solo RFC1918 /
  loopback / rango Tailscale por default). **Ni las tools ni el LLM pueden escribir
  ese archivo** — solo Damian, a mano, fuera del chat. "El usuario dijo que sí" NUNCA
  autoriza. `packet_capture_scan` exige `host_filter` no vacío. No hay gate separado
  "escanear" vs "explotar": estar en la lista alcanza para todo.
- **(d) Modo.** Recon (`nmap`) puede ir AUT dentro de scope. Las que envían payloads
  reales (`sqlmap`, `zap full`, captura) son las de mayor invasividad: recomendado
  SUPERVISADO, o AUTÓNOMO sólo dentro del cyber range (`labnet`, aislado) por el
  patrón de `ORQUESTACION-REMOTA-DESIGN.md` (misión con `necesita-confirmación`).

### 2.3 Rol: Defensor / Antimalware

- **(a) Responsabilidad.** Detección real (YARA + ClamAV + heurística) sobre la PC,
  MÁS auto-protección de la propia instalación de Jarvis (integridad + proceso).
- **(b) Tools reales** (skill `malware_protection`, `_MALWARE_TOOL_NAMES`):

  | Tool | Función | Modo |
  |---|---|---|
  | `malware_scan_path` | Escanea archivo/carpeta puntual | AUT |
  | `malware_full_scan_run`, `malware_full_scan_status` | Escaneo completo (minutos) / estado | AUT |
  | `malware_list_findings` | Ver detectado | AUT |
  | `malware_quarantine_restore` | Restaurar falso positivo | AUT+gate |
  | `malware_quarantine_delete` | Borrado DEFINITIVO (dry-run→confirm) | AUT+gate |
  | `malware_check_integrity` | FIM de archivos críticos de Jarvis | AUT |
  | `malware_rebuild_integrity_baseline` | Acepta cambios como nuevo baseline | **SUP** (confirmación) |
  | `malware_check_process` | Vigilancia del proceso propio | AUT |
  | `malware_check_sysmon_experimental` | Capa EDR experimental (apagada) | AUT |
  | `malware_verify_log` | Verifica el log firmado Ed25519 | AUT |
- **(c) Gates.** Cuarentena es reversible por default (mueve, no borra). `malware_quarantine_delete`
  con `confirm=true` solo por confirmación explícita de un hallazgo puntual.
  `malware_rebuild_integrity_baseline` NUNCA para silenciar una violación sin OK de
  Damian. Reusa el store firmado Ed25519 + DPAPI de `investigation/`.
- **(d) Modo.** Escaneo y detección: AUT (el escaneo diario ya corre solo en
  background). Las dos acciones que "aceptan" o "borran" (baseline / delete
  definitivo) son las que piden confirmación. **Límite honesto:** el watcher
  conductual **detecta pero no contiene** (no tiene el PID para matar el proceso);
  la contención real es el diseño kernel-grade de `DEFENSA-PRIORIDADES.md` (❌ sin
  código).

### 2.4 Rol: Investigación / Forense

- **(a) Responsabilidad.** Análisis de enlaces y evidencia digital sobre material
  que **Damian ya tiene legítimamente**. Es el subsistema con test end-to-end real.
- **(b) Tools reales** (skill `investigation`, `_INVESTIGATION_TOOL_NAMES` — 18):
  `investigation_create_case`, `investigation_propose_column_mapping`,
  `investigation_ingest_csv`, `investigation_propose_entities`,
  `investigation_list_pending_proposals`, `investigation_confirm_proposal`,
  `investigation_reject_proposal`, `investigation_ingest_whatsapp_export`,
  `investigation_ingest_telegram_export`, `investigation_ingest_server_log`,
  `investigation_ingest_image`, `investigation_describe_image`,
  `investigation_ingest_document`, `investigation_propose_fusion`,
  `investigation_list_pending_fusions`, `investigation_confirm_fusion`,
  `investigation_reject_fusion`, `investigation_export_report`. Todas AUT salvo los
  pasos que escriben al grafo, que son **AUT+gate** (confirmación de Damian).
- **(c) Gates.** Todo lo que toca el grafo es **pendiente-de-confirmación**: el
  modelo **propone** (mapeo de columnas, entidades, fusiones) y **nunca escribe** sin
  `investigation_confirm_*`. Log append-only firmado Ed25519 (DPAPI). Cada salida del
  modelo queda etiquetada como generada por él, con referencia al artefacto origen.
- **(d) Modo.** Ingesta y propuestas: AUT. Confirmaciones: siempre con Damian en el
  loop (por diseño, no por modo).
- **⚠️ Sobre "OSINT":** el rol sugerido "Investigación/OSINT" **NO tiene respaldo de
  OSINT real**. El alcance del módulo es **no negociable**: NUNCA scraping, NUNCA
  agregadores de datos personales/padrones/filtraciones, NUNCA deanonimizar ni
  geolocalizar personas, NUNCA salir a buscar por su cuenta. Lo más parecido a
  "investigación web" es `research_topic` (en CORE), que es genérico, no OSINT de
  personas. **Conclusión honesta: no definir un rol OSINT.** Este rol es Forense, y
  su gate central es "solo material que Damian ya tiene".

### 2.5 Rol: Conocimiento / Vault (Bibliotecario) — vive en CORE

- **(a) Responsabilidad.** Gestionar la **pizarra**/memoria: guardar y recuperar
  notas, alimentar el contexto de otros roles, journaling.
- **(b) Tools reales.** No es una skill aparte: son las tools de CORE
  `obsidian_search_notes`, `obsidian_save_note`, `obsidian_list_notes`,
  `research_topic`, `jarvis_reflect`. **Están siempre disponibles** para todos los
  roles y para el capataz (por diseño, ver §2.0).
- **(c) Gates.** Ninguno destructivo (guardar/leer notas). El vault distingue autoría
  jarvis/humano; los embeddings los sirve LM Studio local (:1234) con fallback a
  keyword si no está levantado.
- **(d) Modo.** AUT siempre. Es la infraestructura de coordinación (§4), no un
  ejecutor de acciones peligrosas.

### 2.6 Rol: Sistema / PC-Escritorio-Navegador

- **(a) Responsabilidad.** El "cuerpo digital": lanzar programas, mouse/teclado/
  ventanas, y navegador. Incluye el sub-rol de **formularios web**.
- **(b) Tools reales.** Skill `desktop_control` (`_DESKTOP_CONTROL_TOOL_NAMES`):
  `desktop_click`, `desktop_click_element`, `desktop_focus_window`,
  `desktop_launch_app`, `desktop_list_windows`, `desktop_move_mouse`,
  `desktop_press_key`, `desktop_screenshot`, `desktop_scroll`, `desktop_type_text`,
  y del navegador `browser_open`, `browser_click`, `browser_type`,
  `browser_get_text`, `browser_screenshot`, `browser_close`, `browser_select_option`.
  Skill `web_forms` (`_WEB_FORMS_TOOL_NAMES`): `browser_generate_password`,
  `browser_preview_submit`, `form_get_saved_credential`, `form_list_saved_credentials`.
  (Las dos skills son **disjuntas por tools** a propósito; `browser_open/type/click`
  viven en `desktop_control` y los triggers de "formulario" activan ambas —
  ver comentario en `skills.py` y `test_skills_are_pairwise_disjoint`.)
- **(c) Gates.** **Submit de formularios**: `browser_preview_submit(confirm=false)`
  saca captura + devuelve `preview_token` de un solo uso, atado a selector+URL+TS,
  con TTL corto; `confirm=true` sin token válido se **rechaza sin clickear** (probado,
  17/17). Contraseñas nuevas se generan con `browser_generate_password` (nunca
  inventadas) y se guardan cifradas con DPAPI. Instrucciones que vengan del contenido
  de una página (no de Damian) se tratan como **inyección** y se ignoran.
- **(d) Modo.** Estas tools están **⚠️ SIN PROBAR contra el mundo real** (tests
  mockean pyautogui/pywinauto; el navegador usa Edge como workaround). Recomendado
  **SUPERVISADO** hasta validarlas. Flags: `DESKTOP_CONTROL_ENABLED`.

### 2.7 Rol: Manos sobre el celular

- **(a) Responsabilidad.** Controlar el teléfono conectado por WebSocket: apps,
  archivos, pantalla, cámara, shell (Termux).
- **(b) Tools reales** (skill `phone_control`, `_PHONE_CONTROL_TOOL_NAMES` — 12):
  `phone_global_action`, `phone_list_dir`, `phone_open_app`, `phone_read_file`,
  `phone_read_screen`, `phone_record_video`, `phone_run_command`, `phone_swipe`,
  `phone_take_photo`, `phone_tap`, `phone_type_text`, `phone_write_file`.
  (`phone_nmap_scan` vive en el rol Pentester, no acá.)
- **(c) Gates.** `phone_run_command` tiene blocklist de comandos destructivos; el
  router de `phone_link.py` despacha por WebSocket. Foto/video solo describen si el
  modelo cargado es de visión (VL); con texto-solo, avisa.
- **(d) Modo.** **⚠️ SIN PROBAR** contra un teléfono real sobre Tailscale/datos
  móviles (solo LAN/USB, fecha vieja). Recomendado **SUPERVISADO**. Flags:
  `PHONE_SHELL_ENABLED`, `PHONE_CAMERA_ENABLED`.

### 2.8 Rol: Delegación de código (a otros modelos)

- **(a) Responsabilidad.** Delegar redacción de código/marketing a otros
  trabajadores cuando conviene.
- **(b) Tools reales** (skill `code_delegation`, `_CODE_DELEGATION_TOOL_NAMES`):
  `opencode_run_task` (OpenCode → Ollama local), `cloud_expert_code`,
  `cloud_expert_marketing` (Gemini Flash, borrador).
- **(c) Gates.** `cloud_expert_*` exigen `confirm_non_sensitive=true` explícito —
  NUNCA en proyecto real de cliente / código propietario / dato sensible (mandan
  texto a la nube de Google). Devuelven solo borrador; el ciclo de auditar/testear
  sigue siendo del capataz.
- **(d) Modo.** AUT para proyectos nuevos/de prueba; el gate de sensibilidad es lo
  que importa, no el modo.
- **Nota de solapamiento con el router (§5):** este rol es delegación **elegida por
  el modelo vía tool-call**; el router de modelos de la Fase 0 es delegación
  **decidida por el backend** de forma determinística. Conviven: el router elige qué
  modelo atiende cada llamada del capataz/rol; `code_delegation` sigue siendo para
  cuando el capataz decide explícitamente tercerizar una tarea grande y autocontenida.

### 2.9 Rol: Ingesta

- **(a) Responsabilidad.** Traer conocimiento externo al vault (hoy: playlists de
  YouTube → notas resumidas, idempotente por video-ID). Validado por Damian
  (2026-08-19).
- **(b) Tools reales.** `youtube_ingest_playlist` (`app/tools/ingestion.py`).
- **(c/d) Gate/modo.** AUT; escribe al vault con el formato exacto de nota.
- **⚠️ HALLAZGO REAL (gap de cableado):** `youtube_ingest_playlist` **está registrada**
  (`ingestion` se importa en `app/tools/__init__.py`) **pero NO está asignada a
  ningún skill ni a CORE en `skills.py`**. Consecuencia: solo se ofrece al modelo por
  el camino fail-safe "todo" (cuando `classify()` no matchea ningún skill). Además, el
  test `test_every_registered_tool_is_accounted_for_in_core_or_exactly_one_skill`
  solo exceptúa `generate_video`/`generate_image`, así que **este rol necesita, como
  primer paso de construcción, una skill `ingesta` propia** (con `trigger_keywords`
  como "playlist", "youtube", "ingestá la playlist") que agrupe `youtube_ingest_playlist`.
  Es la pieza más barata de este blueprint y cierra un hueco real.

### 2.10 Fuera de los roles (registradas pero desactivadas)

`generate_image`, `generate_video` (ComfyUI): **NO importadas** en
`app/tools/__init__.py` (por eso no se registran en producción), desactivadas a
propósito por un riesgo de hardware real (apagado físico de la PC el 2026-07-27
durante cómputo de GPU). **No forman parte de ningún rol** hasta resolver el tema
eléctrico/térmico a nivel hardware.

### Resumen de roles → tools reales

| Rol | Skill real | Nº tools | Tool(s) más sensibles | Modo recomendado |
|---|---|---|---|---|
| CORE (base) | — (siempre) | 13 | `fs_write_file`, `fs_delete_path` | AUT (sandbox por modo) |
| Auditor Código/Seguridad | `security_audit` | 14 | `pc_run_command`, `code_apply_fix` | AUT + `pc_run_command` SUP |
| Pentester/Red-team | `pentesting` | 6 | `sqlmap_scan`, `zap_scan`, `packet_capture_scan` | SUP / AUT solo en labnet |
| Defensor/Antimalware | `malware_protection` | 11 | `malware_quarantine_delete`, `_rebuild_integrity_baseline` | AUT + delete/baseline gate |
| Investigación/Forense | `investigation` | 18 | `investigation_confirm_*` (escriben grafo) | AUT + confirmación |
| Conocimiento/Vault | CORE (obsidian_*+research+reflect) | (en CORE) | ninguna destructiva | AUT |
| Sistema/PC-Escritorio | `desktop_control` (+ `web_forms`) | 17 (+4) | submit de formularios | SUP (sin validar) |
| Manos-celular | `phone_control` | 12 | `phone_run_command` | SUP (sin validar) |
| Delegación de código | `code_delegation` | 3 | `cloud_expert_*` (nube) | AUT + gate de sensibilidad |
| Ingesta | **FALTA skill** (`youtube_ingest_playlist` suelta) | 1 | — | AUT |

Total de tools reales registradas en producción: **97** (99 con `generate_*`, que
no se importan). Roles con respaldo real: los 8 skills + CORE + ingesta (pendiente
de skill). Rol sin respaldo real: **OSINT** (no existe; el módulo forense lo prohíbe).

---

## 3. El capataz (orquestador)

El capataz **ya existe**: es el loop de `agent.py` (`run_agent` →
`_run_agent_turn` → `_run_agent_turn_inner`). El plano no lo reemplaza; lo
formaliza como hub y le agrega la delegación explícita a roles.

### 3.1 Cómo planifica y decide a quién delegar (hoy, real)

1. **Selección de perfil.** `run_agent` maneja el cambio de perfil con comando
   explícito (`/modo investigacion`) vía `_system_prompt_for_profile` /
   `_tools_for_profile`. `default` (seguridad/código) vs `research` (científico). Es
   cambio de contexto, no una segunda instancia (12 GB de VRAM no da para dos modelos
   grandes a la vez).
2. **Selección de rol (solo perfil `default`).** `skills.classify(message)` —
   **determinística por keywords, sin llamar al modelo** — devuelve el/los skill(s)
   que matchean. Puede devolver varios (un pedido toca varios dominios) o ninguno.
3. **Armado del contexto acotado.** Si matcheó: `tools_for_active_skills()` =
   `CORE ∪ tools de cada skill`, y `prompt_for_active_skills()` = `CORE_PROMPT +
   fragmentos`, en orden estable (para el cache de prompt del server de inferencia).
   Si NO matcheó: **fail-safe** → `SYSTEM_PROMPT` completo + todas las tools (nunca
   "de menos").
4. **Ejecución del loop.** `while iteration < effective_max_iterations`:
   llama al modelo (`tool_choice="auto"`), ejecuta la tool que elija (`call_tool`
   rutea a PC o celular), agrega el resultado al historial, repite hasta texto final
   o tope. El tope arranca en `max_agent_iterations` (chat/auditoría normal) y **sube
   una sola vez** a `max_agent_iterations_code_task` cuando el turno usa `fs_write_file`
   (se confirma que es tarea de creación de código).
5. **Protección de contexto.** `_trim_history` (por cantidad de mensajes),
   `_trim_history_by_budget` (por presupuesto de tokens reales) y `_cap_tool_result`
   (acota un solo resultado grande). Sincronizados con `MODEL_CONTEXT_TOKENS`.
6. **Manejo de error del LLM.** `_create_chat_completion` ya reintenta con backoff
   **solo** fallas transitorias de red (`_is_transient_llm_error`: `APIConnectionError`
   sí; `APITimeoutError` no, salvo `LLM_RETRY_ON_TIMEOUT`, porque un timeout local
   suele ser generación lenta, no red). **Matiz respecto de `CAPACIDADES §6.2`:** la
   capa de red **sí** reintenta; lo que falta es **fallback entre modelos/proveedores**
   (eso lo agrega el router, §5).
7. **Verificación.** El propio prompt de `security_audit` obliga a leer el resultado
   REAL (`finding_resolved`, `tests.passed`), no a asumir. Los gates de código
   (`_obsidian_gate_error`, detección de loops de reescritura idéntica) frenan modos
   de falla reales del modelo.

### 3.2 Cómo se convierte en hub explícito (lo que se construye)

Hoy el "rol" es el mismo turno con menos tools. El plano lo evoluciona a
**delegación como sub-invocación** (Fase 1), sin romper nada:

- El capataz, ante una sub-tarea de dominio cerrado, **invoca un ejecutor** con
  (a) su `prompt_fragment` de rol, (b) su `tool_names` acotado, (c) su modelo por
  defecto vía el router, y (d) su propio presupuesto de contexto.
- El ejecutor corre un mini-loop, **devuelve su resultado al capataz** y **deja su
  rastro en la pizarra** (una nota en el vault). **No llama a otro ejecutor.**
- El capataz **verifica** (lee el resultado y/o la nota del vault), decide el
  siguiente paso, y delega de nuevo — **de a uno**, nunca N ejecutores en paralelo
  deliberando (costo × N con DeepSeek por token; y más superficie de falla con un
  modelo mediano).
- **Orden de delegación:** lo fija el capataz por planificación en lenguaje natural,
  apoyado en `jarvis_reflect`/`obsidian_search_notes` (memoria) antes de empezar una
  tarea ambigua. No hay un planificador de grafo separado en Capa B; el grafo
  determinístico vive en Capa A (§1) para lo repetitivo/programado.

### 3.3 Cómo arma el resultado

El capataz compone la respuesta final a partir de (a) los resultados que le
devolvieron los roles y (b) lo que quedó escrito en la pizarra. Cierra guardando en
`jarvis_reflect` lo no trivial que valga recordar, y —cuando corresponde— una nota
de vault con el trabajo hecho (que además sirve de historial, §4). En flujos de
Capa A, el "armado" es el brief/push saliente (§7, Fase 2).

---

## 4. La pizarra (vault como estado compartido)

La pizarra es el vault Obsidian real (`app/obsidian/`, `backend/obsidian_vault/`).
Es a la vez **estado compartido entre roles** (dentro de una tarea) y **memoria/
historial en el tiempo** (entre tareas y entre conversaciones que no comparten
historial de chat).

### 4.1 Por qué el vault y no un bus de mensajes

Porque **ya existe y ya resuelve el problema**: notas .md reales con frontmatter
YAML y wikilinks, búsqueda semántica por embeddings + coseno (fallback keyword),
autoría separada jarvis/humano, y perfiles distintos (seguridad vs investigación
científica, `obsidian_vault_investigacion/`). Un rol no necesita hablarle a otro:
**escribe lo que encontró; el que lo necesita lo busca.** Esto calza exactamente con
la decisión de "nada de charla directa entre agentes".

### 4.2 Protocolo concreto (qué escribe cada rol, dónde, cómo se lee)

- **Escritura (todos los roles + el capataz):** vía las tools de CORE
  `obsidian_save_note` (nota nueva con título, contenido, tags/wikilinks) y
  `jarvis_reflect(action='save', ...)` (aprendizaje/decisión con `tipo` y `contexto`).
  Cada rol deja su **hallazgo** como nota, no como mensaje a otro rol. Ejemplos por
  rol:
  - Auditor: nota "auditoría de `<proyecto>` — hallazgos y fixes aplicados"
    (+ `audit_generate_report` para el informe formal).
  - Pentester: nota de recon/resultado **dentro del scope**; el detalle sensible
    (targets) NO va al repo público — el vault es local.
  - Defensor: hallazgo de malware ya queda en el store firmado; la nota resume.
  - Forense: cada caso es su propio repo git; `investigation_export_report` genera
    MD+PDF. La pizarra general referencia el caso, no duplica evidencia.
- **Formato/carpeta:** notas de Jarvis en `backend/obsidian_vault/jarvis/`
  (autoría jarvis), con frontmatter y wikilinks (convención ya usada por las notas de
  la playlist "Info para Jarvis" y por estos docs de visión). El perfil científico
  usa `obsidian_vault_investigacion/`.
- **Lectura (todos + capataz):** `obsidian_search_notes` (semántica; hacer la query
  **específica** para que una nota puntual no la tape otra genérica — regla del
  `CORE_PROMPT`) y `obsidian_list_notes`. El capataz consulta la pizarra **antes** de
  planificar (memoria) y **después** de delegar (verificación).
- **Memoria de procedimiento:** `jarvis_reflect` (JSONL append-only, `tipo` ∈
  {decision_arquitectura, preferencia_usuario, leccion_aprendida, ruido}, `contexto`
  = subsistema). Es la continuidad de criterio entre conversaciones que no comparten
  historial.

### 4.3 La pizarra como historial en el tiempo

Cada nota queda fechada y buscable: la suma de notas ES el historial del trabajo de
Jarvis. Un flujo de Capa A (brief matutino) **lee la pizarra** para armar "esto pasó
anoche". Una misión remota (`ORQUESTACION-REMOTA-DESIGN.md §7`) **escribe su nota de
cierre** con link al celular. El bucle nocturno de detección destila reglas y las
propone — su rastro también vive acá. Regla: **si vale para el futuro, va a la
pizarra; si es efímero, no.**

### 4.4 Gate de la pizarra

La única fricción es el gate anti-alucinación: `fs_write_file` de un archivo de
código exige haber consultado Obsidian/`research_topic` primero
(`_obsidian_gate_error`). Sobre las notas del vault en sí no hay gate destructivo
(guardar/leer). El vault es local y **no se pushea** con secretos (el `.gitignore`
cubre lo sensible; los targets de pentesting nunca van al repo público).

---

## 5. El router de modelos

El cambio más rentable con la transición a **DeepSeek V4 por token vía OpenRouter**:
cada llamada cuesta plata, así que rutear barato/potente es palanca de costo directa,
no adorno. Va **detrás de la interfaz única** que ya existe: `app/llm_client.py`
habla un endpoint OpenAI-compatible y no le importa qué hay detrás (por eso
`LMSTUDIO_MODEL` pudo migrar de LM Studio a Ollama cloud sin tocar el cliente).

### 5.1 La señal de dificultad ya la produce `skills.py`

Regla de oro: **la decisión de ruteo NO la toma un modelo** (pagaría el costo que se
evita). Se decide en el backend con señales baratas ya disponibles:

- **`skills.classify()` es la señal de complejidad de dominio.** Tarea de dominio
  cerrado y guiado (escanear, aplicar fix, ingestar CSV) → **modelo barato**. Tarea
  abierta/ambigua/de planificación (auditar y proponer, diseñar) → **modelo potente**.
- **Señales adicionales sin costo:** si el turno usó `fs_write_file` (subió el tope a
  `max_agent_iterations_code_task` → tarea de código grande), si viene de un trigger
  de Capa A vs chat interactivo, nº de pasos estimados.

| Tipo de tarea | Modelo | Por qué |
|---|---|---|
| Flujo guiado, dominio cerrado (escaneo, fix, ingesta) | Barato (local `jarvis-text-v2`) | El andamiaje de skills ya compensa al modelo |
| Abierta/ambigua, multi-paso, planificación (el capataz planificando) | Potente (**DeepSeek V4 / OpenRouter**, por token) | Es donde el criterio importa |
| Redacción/resumen de un nodo de Capa A (brief) | Barato | Acotado y verificable |
| Embeddings del vault | El de siempre (LM Studio local :1234) | Ya está aparte por diseño; NO se toca |

### 5.2 Lógica de ruteo, fallback y OpenRouter

- **Ubicación:** capa fina de selección + fallback dentro de `llm_client.py` (o un
  wrapper delante). El resto de `agent.py` no cambia.
- **OpenRouter:** endpoint OpenAI-compatible (`https://openrouter.ai/api/v1`), API
  key por token en `.env` (nunca en el repo público; el `.gitignore` ya cubre `.env`).
  DeepSeek V4 se pide por su slug de OpenRouter. Mismo cliente OpenAI-compatible que
  ya usa el proyecto para Ollama/Gemini — no hay cliente nuevo.
- **Fallback (cierra el agujero de `CAPACIDADES §6.2`):** cadena barato→potente y
  potente→contención. Si DeepSeek V4 falla/timeout/rate-limit → cae al secundario
  (otro proveedor de OpenRouter, o el local `jarvis-text-v2` como red offline).
  Reusar `_is_transient_llm_error` para distinguir **error de red** (rotar/reintentar)
  de **error de lógica** (no reintentar el mismo prompt a ciegas). Esto **extiende** el
  retry de red que ya existe con un salto de modelo, que hoy NO hay.
- **`MODEL_CONTEXT_TOKENS` pasa a ser por-modelo.** Hoy es una sola variable; con
  varios modelos hay que sincronizar `num_ctx` real por cada uno (advertencia de
  `CLAUDE.md`) para que `_trim_history_by_budget` pode con el presupuesto correcto.
- **Construir dentro vs LiteLLM/Omniroute:** para la v1, **dentro** (son 2-3 modelos,
  no 290; el insumo de decisión ya está en `skills.py`). LiteLLM self-hosted es la
  evolución si crece. **Omniroute-gratis: NO** en producción (sus proveedores libres
  entrenan con tus datos — inaceptable con datos de pentest/forense); sirve solo de
  referencia de diseño.

---

## 6. Los gates y la seguridad

Ningún gate ya decidido se debilita. La orquestación es **infraestructura de
ejecución**; los gates siguen exactamente donde están. Cómo se preservan:

### 6.1 Menor privilegio por rol

Aprovechar que `Skill` **ya declara `tool_names`**: un rol solo ve su caja de tools.
Hoy esto es real dentro de un turno (`tools_for_active_skills` filtra el schema que
se le manda al modelo). En la Fase 1, cuando un rol es una sub-invocación, el
principio se refuerza: el ejecutor **físicamente no tiene** en su schema las tools de
otros roles. El fail-safe se mantiene: ante clasificación nula, se cae a "todo", nunca
a "de menos" (para no dejar al modelo sin una tool que necesitaba).

### 6.2 Consentimiento e irreversibilidad (patrones que NO cambian)

- **`authorized_targets.yaml`** — control técnico de scope de pentest
  (`network/guardrail.py`). Ni tools ni LLM lo escriben; solo Damian a mano. Ningún
  camino remoto/misión lo amplía.
- **`dry-run → confirm=true`** — cuarentena (mover, no borrar; delete definitivo solo
  con confirm), `code_apply_fix`.
- **`preview_token`** de un solo uso, atado a selector+URL+TTL — submit de formularios.
- **`proposal_id`** (`sf-xxxxxxxx`) — self-repair: aplicar exige que Damian escriba el
  id; `fs_write_file` sobre `backend/` bloqueado siempre.
- **Gate de Obsidian** (`_obsidian_gate_error`) — anti-alucinación en escritura de código.
- **Flags por capacidad** — `DESKTOP_CONTROL_ENABLED`, `PC_SHELL_ENABLED`,
  `PHONE_SHELL_ENABLED`, `NMAP_ENABLED`, `SCREEN_RECORDING_ENABLED`, etc.
- **Blocklist + auditoría** de `pc_run_command` (no es sandbox; radio = `FS_ALLOWED_ROOT`).
- **Audit log firmado Ed25519 (DPAPI)** — traza inalterable, reusada por
  investigación y malware; los diseños de misiones/`vm_control`/`ssh_guest` la reusan.

### 6.3 Los dos modos en la orquestación

- **SUPERVISADO**: chat/voz en vivo, root FS amplio (`fs_supervised_roots`). Potencia
  de siempre, con humano para frenar.
- **AUTÓNOMO**: default del proceso (fail-safe), sandbox acotado (`fs_allowed_roots`).
  Los flujos de Capa A (cron, misiones) corren AUTÓNOMOS — es su caso de uso.
- **Guardrail anti-auto-escalada**: ni el capataz ni un rol pueden subir a
  SUPERVISADO desde dentro de un turno (`operating_as` lo rechaza si
  `_agent_turn_active`). El modo lo fija el punto de entrada, no Jarvis en runtime.
- **Trabajo pendiente (honesto):** hoy el modo solo gobierna el **sandbox de
  filesystem** (`effective_fs_roots`). La columna "modo" de §2 (qué tool sensible
  puede correr AUT vs SUP) es una **recomendación de diseño que todavía no está
  cableada por-tool**. Cablearlo — que en AUTÓNOMO ciertas tools (`pc_run_command`,
  `sqlmap_scan`, submit de formularios) se detengan a pedir confirmación o queden
  deshabilitadas — es parte de la Fase 1 (ver §7). Es la mejora que hace que "menor
  privilegio por rol" también aplique a **acciones**, no solo a filesystem.

---

## 7. Plan de construcción por fases

De menor a mayor riesgo. Cada fase es útil sola y no depende de la siguiente.
Criterio de "listo" heredado del repo: **tests en verde (`cd backend && pytest`),
auditoría registrando, ningún gate debilitado.**

### Fase 0 — Router de modelos con fallback (lo más rentable ya)

Capa fina en `llm_client.py`: elige modelo por señal de `skills.classify` +
complejidad (§5.1), con cadena de fallback (§5.2) reusando `_is_transient_llm_error`.
Integrar OpenRouter/DeepSeek V4 como potente; `jarvis-text-v2` local como barato/
contención. `MODEL_CONTEXT_TOKENS` pasa a ser por-modelo.

- **Listo cuando:** una tarea guiada usa el barato y una abierta el potente
  (verificable en logs); si el primario falla/timeout, cae al secundario sin cortar el
  turno; el costo por token baja de forma medible; tests del router en verde.
- **NO romper:** el reintento de red existente; los tres podadores de contexto; el
  cache de prompt (prompt byte-a-byte estable). El embeddings server (:1234) NO se toca.

### Fase 1 — Roles/skills como ejecutores + menor privilegio por acción

(a) Cerrar el **gap de la Ingesta**: crear la skill `ingesta` para
`youtube_ingest_playlist` (hoy suelta, §2.9). (b) Convertir las skills en ejecutores
invocables como sub-tarea con contexto acotado (§3.2), cada uno con su modelo por
defecto vía el router. (c) Cablear el modo por-acción (§6.3): en AUTÓNOMO, las tools
sensibles marcadas SUP se detienen/piden confirmación.

- **Listo cuando:** el capataz delega una sub-tarea de dominio cerrado a un ejecutor
  con tools/prompt reducidos y verifica el resultado (leyendo la pizarra) antes de
  seguir; `youtube_ingest_playlist` matchea su skill y pasa el test de completitud; el
  chat de siempre no cambia cuando no hay delegación; una tool SUP no corre sola en
  AUTÓNOMO sin gate.
- **NO romper:** el fail-safe de clasificación nula (cae a "todo"); la disjunción de
  skills (`test_skills_are_pairwise_disjoint`); CORE siempre presente (gate de
  Obsidian); los perfiles `default`/`research`.

### Fase 2 — Scheduler general + primer flujo de Capa A (brief + push)

Scheduler de tareas del agente (lo que `HACIA-RAPHAEL` Etapa 6 marca FALTA) y **un**
flujo determinístico de estreno: el **brief matutino** del escaneo diario que ya
corre (`malware/fullscan.py`), empujado al celular por el canal de `phone_link.py`.
El LLM solo redacta el resumen (nodo barato vía router); el flujo lo pone el diseño.

- **Listo cuando:** a una hora fija, sin intervención, Jarvis lee la pizarra, arma el
  brief y lo empuja; corre AUTÓNOMO con sandbox acotado; si toca algo gated, se detiene.
- **NO romper:** el escaneo diario existente; el guardrail anti-auto-escalada (el job
  corre AUTÓNOMO, nunca escala); el WebSocket 1:1 de `phone_link.py`.

### Fase 3 — Cola de misiones como grafo (generalizar `ORQUESTACION-REMOTA-DESIGN`)

Unificar la cola de misiones (`ORQUESTACION-REMOTA-DESIGN.md §7`) con el scheduler:
una misión es un tipo de flujo de Capa A, con sus estados (encolada → corriendo →
necesita-confirmación → completada/fallida) y el gate `necesita-confirmación` intacto
(OK remoto atado a cada paso, estilo `preview_token`/`proposal_id`). Worker en
background; updates que sobreviven desconexión; nota de cierre en la pizarra. (El
camino remoto depende de Tailscale/SSH — Fases 2-4 de la orquestación remota; en
local se puede antes.)

- **Listo cuando:** una misión se modela como flujo del scheduler, se detiene en cada
  paso gated y espera OK de un solo uso, deja nota en el vault; ninguna confirmación
  remota amplía `authorized_targets.yaml`; una acción peligrosa (§9.3 del diseño
  remoto) nunca corre sin confirmación.
- **NO romper:** ningún gate; el aislamiento de `labnet`; el audit log firmado.

### Fase 4 — Fábrica de composición de skills (con gate de aprobación)

El componente que detecta patrones de tools repetidos y **propone** una skill/rol
nuevo (`HACIA-RAPHAEL §6.3`), que Damian aprueba con un `proposal_id` de un solo uso.
Última por mayor radio: una skill auto-creada que luego se ejecuta sola es "un arma
cargada" — **solo propone, nunca activa sin firma**.

- **Listo cuando:** Jarvis detecta una cadena recurrente (del audit log +
  `jarvis_reflect`), redacta la propuesta (nombre, `tool_names`, `trigger_keywords`,
  `prompt_fragment`) y **no** la incorpora a `SKILLS` sin aprobación explícita; una
  propuesta rechazada no deja rastro ejecutable.
- **NO romper:** el gate de aprobación (mismo patrón que self-repair); la disjunción y
  completitud de skills (una skill compuesta nueva no puede pisar tools de otra).

---

## 8. Límites honestos

**Lo más importante, sin maquillar:** la orquestación consciente **no convierte a un
modelo mediano en uno de frontera.** El techo de `CAPACIDADES §6.1` sigue en pie —
un 30B/120B (o DeepSeek V4 por token) **ejecuta flujos guiados, no delibera** sobre
tareas abiertas, ambiguas, de muchos pasos con criterio encadenado. Ahí el modelo va
a fallar de las mismas formas que el código ya parchea (loops de reescritura,
archivos abandonados, soluciones inventadas). Ninguna arquitectura lo arregla; un
multi-agente mal hecho lo **amplifica** — por eso este plano **rechaza** la charla
directa entre agentes y delega **de a uno, verificando**.

**Lo que este plano SÍ gana, y es real:**

- **Costo.** El router (Fase 0) es plata directa: barato para lo guiado, caro solo
  donde importa. Con facturación por token de OpenRouter, se paga solo.
- **Robustez.** El fallback de modelos cierra el agujero "el cloud se cayó /
  rate-limit" que hoy corta el turno (hoy solo se reintenta la red, no se salta de
  modelo).
- **Eficiencia y certeza.** Acotar contexto+tools por rol (menor privilegio) hace cada
  llamada más barata y más certera — el modelo mediano rinde **mejor** con el problema
  recortado. Es justo para lo que el andamiaje de skills existe.
- **Alcance sin criterio nuevo.** Scheduler + push + misiones (Fases 2-3) dan trabajo
  desatendido y proactividad **en flujos determinísticos** — donde no hace falta
  criterio, solo constancia. Ahí un modelo mediano alcanza, porque el flujo lo pone el
  diseño.
- **Memoria de procedimiento.** La fábrica de skills (Fase 4) evita redescubrir la
  misma rutina — recombinación con nombre, no inteligencia emergente.

**Dónde el humano sigue siendo necesario (no negociable):**

- **Editar `authorized_targets.yaml`** — el único que amplía el scope de pentest.
- **Firmar lo irreversible** — `confirm=true` de cuarentena definitiva y de fixes,
  `proposal_id` de self-repair y de la fábrica de skills, OK remoto de misiones.
- **Validar el mundo real** — control de PC/celular/navegador y el resto del
  pentesting activo están **⚠️ SIN PROBAR** end-to-end (tests mockeados); hasta
  validarlos (y cerrar el cyber range, e instalar Tailscale, y achicar
  `FS_ALLOWED_ROOT`), operan mejor SUPERVISADOS. La orquestación **no** los convierte
  en confiables por sí sola.
- **Contención real de malware** — el watcher detecta pero no contiene (falta el
  kernel-grade de `DEFENSA-PRIORIDADES.md`, ❌ sin código). La autonomía desatendida
  sobre defensa es prematura hasta eso.

**La regla que no cambia:** delegá tareas **acotadas y verificables**, no objetivos
abiertos. La orquestación mueve la frontera de "qué es acotado" (más flujos entran),
baja el costo y sube la robustez — pero **no delega criterio que el modelo no
tiene.** Eso, y no un grafo elegante, es lo que hace que "Jarvis hace y yo corrijo"
siga siendo verdad a mayor escala.

---

## Referencias (código real, verificado por grep 2026-08-23)

- `backend/app/agent.py` — capataz: `run_agent`/`_run_agent_turn`/`_run_agent_turn_inner`,
  `classify`+`tools_for_active_skills`, `_is_transient_llm_error`+`_create_chat_completion`
  (retry de red), `_obsidian_gate_error`, `_trim_history`/`_trim_history_by_budget`/`_cap_tool_result`,
  tope dinámico `max_agent_iterations`→`max_agent_iterations_code_task`, perfiles
  `default`/`research`.
- `backend/app/skills.py` — `Skill(name, trigger_keywords, prompt_fragment, tool_names)`,
  `CORE_TOOL_NAMES`, `SKILLS` (8 skills), `classify` determinístico,
  `tools_for_active_skills`, `prompt_for_active_skills`.
- `backend/app/tools/__init__.py` — registro real (`register_tool`, `get_tools`,
  `openai_tool_schemas`, `call_tool` router pc/phone), `generate_*` NO importadas.
- `backend/app/tools/*.py` — 97 tools reales registradas (nombres exactos en §2).
- `backend/app/operation_mode.py` — SUPERVISED/AUTONOMOUS, fail-safe, `effective_fs_roots`,
  guardrail anti-auto-escalada (`operating_as`/`agent_turn_active`).
- `backend/app/llm_client.py` — endpoint OpenAI-compatible único (donde va el router).
- `backend/app/network/guardrail.py` — `resolve_and_authorize` (scope de pentest,
  `authorized_targets.yaml`).
- `backend/app/obsidian/` + `backend/obsidian_vault/` — la pizarra (vault, embeddings,
  autoría jarvis/humano, perfiles).
- `backend/tests/test_skills.py` — completitud (toda tool en CORE o exactamente un
  skill, salvo `generate_*`), disjunción, gate de Obsidian en CORE.

### Diseños y visión del repo

- `vision/ORQUESTACION-ESTRUCTURA.md` — elección del patrón híbrido 3 capas + router.
- `vision/CAPACIDADES-REALES-DE-JARVIS.md` — estados VALIDADO/⚠️SIN PROBAR/❌DISEÑO,
  techo del modelo (§6.1), reintentos (§6.2).
- `vision/HACIA-RAPHAEL.md` — Etapa 6 (push+scheduler, FALTA), §6 (composición de skills).
- `lab/ORQUESTACION-REMOTA-DESIGN.md` — cola de misiones (§7), `vm_control`/`ssh_guest`,
  confirmaciones remotas, Tailscale.
- `lab/DEFENSA-PRIORIDADES.md` — respuesta kernel-grade (contención real, aún ❌).
- `CLAUDE.md` — modelos en uso, `LMSTUDIO_MODEL`, `MODEL_CONTEXT_TOKENS`, gates.
