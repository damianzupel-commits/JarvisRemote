# ORQUESTACION-ESTRUCTURA.md — Estructura de orquestación consciente para Jarvis

> Documento de **análisis y propuesta de diseño** (no ejecutable, no es código).
> Parte de cinco notas que Damian guardó de su playlist "Info para Jarvis"
> (ingeridas al vault el 2026-08-18/19) sobre orquestación de agentes, ruteo de
> modelos y automatización de flujos, y las cruza con **cómo está armado Jarvis
> hoy** para proponer una **estructura de orquestación consciente** concreta.
>
> Creado: 2026-08-23. Alinea con: `CLAUDE.md` (arquitectura, modelos, gates),
> `vision/CAPACIDADES-REALES-DE-JARVIS.md` (auditoría honesta de qué anda),
> `vision/HACIA-RAPHAEL.md` (visión y hoja de ruta, sobre todo §6 composición de
> skills y la Etapa 5), `lab/ORQUESTACION-REMOTA-DESIGN.md` (cola de misiones),
> y el código real: `backend/app/agent.py`, `backend/app/skills.py`,
> `backend/app/operation_mode.py`.
>
> **Regla heredada de los otros docs de visión:** todo apunta a algo real del
> repo. Donde algo no existe, se dice **FALTA** sin maquillarlo. No debilita
> ningún gate ya decidido. No toca código.

---

## 1. Qué sacó Jarvis de cada nota (concreto, citando el video)

Las cinco notas viven en `backend/obsidian_vault/jarvis/`. Cada una aporta una
pieza distinta del rompecabezas de orquestación; ninguna es "la" respuesta sola.

### 1.1 Omniroute — ruteo y fallback de modelos (dos videos)

Dos notas apuntan a la **misma herramienta** (aparece transcripta como
"Omniroute" / "Omnirroot"), lo que dice que a Damian el tema le importa:

- **"Ejecuté Claude Code con Modelos Gratis (OmniRoute)"** (`o7hPSFNVBjo`,
  Mert Durmazer) — *integracion-automatica-de-modelos-de-ia-gratuitos-con-omniroute-...*.
- **"NUNCA más te quedes a medias con CLAUDE CODE, usa el proyecto #1 de GITHUB"**
  (`p31sfv8CI5A`, ZETA) — *solucion-para-evitar-limites-de-tokens-en-ia-omnirroot-...*.

**Enfoque concreto que proponen:** un **panel local de distribución de modelos**
(un router) que se pone delante del cliente (Claude Code, Cursor, Hermes) y expone
un único endpoint OpenAI-compatible, mientras por detrás gestiona +290 proveedores
(muchos gratuitos). Las ideas rescatables para Jarvis son cuatro, en orden de
utilidad real:

1. **Fallback automático por proveedor.** Si un modelo falla o pega el rate-limit,
   el router pasa al siguiente "en milisegundos" sin cortar el flujo. Esto es
   directamente el talón de Aquiles que `CAPACIDADES-REALES-DE-JARVIS.md §6.2`
   marca: *"el loop no reintenta"* y *"cloud depende de estar logueado y de la
   red"*.
2. **Combos con estrategia** (prioridad, aleatorio, minimizar costo, fusión de
   respuestas). El que nos sirve es **minimizar costo / prioridad**: barato
   primero, caro solo si hace falta.
3. **Un único punto de acceso local** — el cliente no cambia. Calca lo que ya pasa
   en Jarvis: `app/llm_client.py` habla con un endpoint OpenAI-compatible
   (`127.0.0.1:11434/v1`) y no le importa qué hay detrás (por eso `LMSTUDIO_MODEL`
   pudo pasar de LM Studio a Ollama cloud sin tocar el cliente, ver `CLAUDE.md`).
4. **Monitoreo de uso/costo** para ejecutar flujos 24/7.

**Salvedad de la propia nota (score 4/5):** los proveedores gratuitos pueden
**entrenar con tus datos** — inaceptable para un proyecto de pentesting con datos
sensibles. El valor para Jarvis es **el patrón de router con fallback**, no
"conectar 290 modelos gratis".

### 1.2 n8n — grafo de flujos disparados por eventos

- **"Introduction to N8N, automate your workflows"** (`yP0PM-fpnXo`, midudev) —
  *automatizacion-de-alertas-diarias-sobre-carreras-de-running-con-n8n*.

**Enfoque concreto:** n8n es un orquestador **visual de flujos** (nodos + aristas)
disparado por eventos. El ejemplo de la nota: *trigger programado 8:00 AM →
HTTP request a una API → transformar datos (JavaScript) → enviar Gmail*. Lo
relevante para Jarvis es el **modelo mental**, no la herramienta:

- **Trigger programado** (cron) — Jarvis hoy no lo tiene general; `HACIA-RAPHAEL.md`
  Etapa 6 lo marca como **FALTA** (*"scheduler general de tareas del agente"*, hoy
  solo el escaneo diario de malware corre por intervalo hardcodeado).
- **Lógica condicional + transformación entre pasos**, con salida a un canal
  (mail). Es exactamente la forma del **push proactivo** que falta (brief matutino,
  alerta que llega sin abrir el chat).
- **Flujo determinístico y declarativo**: los pasos están fijos, no los decide un
  LLM en runtime. Esa es la diferencia clave con el loop del agente (§3).

### 1.3 Agent Reach — acceso autenticado a sitios con login

- **"Agent Reach"** (`ImLUT5S_l9Q`, Vera Badías) —
  *agent-reach-acceso-libre-a-sitios-con-login-para-agentes-de-ia-sin-codigo*.

**Enfoque concreto:** una skill gratis/open-source que le da a un agente acceso a
sitios detrás de login (X, Reddit, YouTube, GitHub) **reusando las cookies del
navegador** — autenticación persistente, sin pedir tokens a mano. Casos de uso de
la nota: recolectar tendencias, generar leads, validar ideas de producto entre
Reddit y X en un flujo automatizado.

**Qué es para Jarvis:** esto **no es orquestación**, es una **capacidad de sensor**
(una tool más), pero encaja acá porque hoy Jarvis ya tiene `browser.py` (Playwright
vía Edge del sistema) y `web_forms`/`forms/` con credential store DPAPI. Agent
Reach es una **fuente de datos autenticada** que un flujo de orquestación podría
consumir (ej. un flujo OSINT). Se anota como tool candidata, no como patrón
estructural — y con una nota de seguridad: reusar cookies de sesión es
sensible, va detrás del mismo criterio de credenciales cifradas que ya usa
`forms/credential_store.py`.

### 1.4 One-Person AI Business — el *para qué*, no el *cómo*

- **"How to Build a One Person AI Business (Using Claude Code)"** (`LVAHYV4Xrto`,
  Nate Herk) — *como-construir-un-negocio-de-ia-con-un-solo-persona-...*.

**Enfoque concreto:** consultoría de IA unipersonal apalancada en Claude Code,
alineando cada automatización a uno de tres objetivos (más clientes, más valor por
cliente, menos costo operativo), con una escalera de servicios que empieza chica y
sube por confianza demostrada.

**Qué aporta a la orquestación:** no es técnico, es **criterio de priorización**.
La lección transferible: **una orquestación se justifica por el trabajo que
elimina, no por lo elegante que es el grafo.** Antes de multiplicar agentes,
preguntarse qué flujo repetitivo real de Damian (auditar un repo, correr el bucle
nocturno, atender una misión remota) se automatiza de punta a punta. Conecta con la
composición de skills de `HACIA-RAPHAEL.md §6`: cristalizar los patrones que **de
hecho se repiten**, no los que suenan bien.

### 1.5 Síntesis de las notas

| Nota (video) | Aporte a la orquestación | Ya existe algo en Jarvis |
|---|---|---|
| Omniroute (x2) | **Router de modelos con fallback** + estrategia costo/prioridad, endpoint único local | `llm_client.py` (endpoint único), `cloud_expert`/`opencode` (delegación puntual) — pero **sin router ni fallback** |
| n8n | **Grafo de flujos determinístico** disparado por cron/eventos + push a un canal | **FALTA** scheduler general y push saliente (Etapa 6 de HACIA-RAPHAEL) |
| Agent Reach | **Tool** de acceso autenticado (sensor de datos), no estructura | `browser.py`, `web_forms`, `forms/` con DPAPI |
| One-Person AI Business | **Criterio**: automatizar el flujo repetitivo real, no el elegante | `HACIA-RAPHAEL §6` (cristalizar patrones que se repiten) |

---

## 2. Cómo está orquestado Jarvis HOY

Antes de proponer, hay que ser exacto sobre el punto de partida, porque buena parte
de lo que las notas "proponen" Jarvis **ya lo tiene en forma embrionaria**.

- **Patrón actual: agente único con tool-calling.** `app/agent.py` corre el loop
  clásico LLM → tool → LLM hasta respuesta en texto o tope de iteraciones (10
  normal, 50 en tareas de código). ~50-58 tools registradas en `app/tools/`. No
  hay multi-agente, no hay subagentes, no hay grafo.
- **"Orquestación" que ya existe = ruteo por skills, determinístico.** `skills.py`
  clasifica el mensaje del usuario **por keywords (substring, sin modelo en el
  medio)** y le ofrece al modelo solo el subconjunto de `prompt_fragment` + tools
  del/los dominio(s) que matchean (8 skills: `investigation`, `security_audit`,
  `pentesting`, `malware_protection`, `desktop_control`, `web_forms`,
  `phone_control`, `code_delegation`). Si nada matchea, cae al prompt+tools
  completos (fail-safe hacia "todo", nunca hacia "de menos"). `core` está siempre
  presente. Esto ya es una forma de orquestación consciente barata: **acotar el
  problema y las herramientas según la tarea**.
- **Perfiles** (`_system_prompt_for_profile`, `_tools_for_profile`): `default`
  (seguridad/código) vs `research` (investigación científica), cambiados con
  comando explícito (`/modo investigacion`). Mismo backend/modelo — es cambio de
  contexto, no una segunda instancia (12 GB de VRAM no da para dos modelos
  grandes).
- **Modos de operación** (`operation_mode.py`): SUPERVISADO (humano en vivo,
  sandbox FS amplio) vs AUTÓNOMO (desatendido, sandbox acotado). Fail-safe: el
  default del proceso es AUTÓNOMO; solo los entrypoints interactivos declaran
  SUPERVISADO por-invocación. **Guardrail anti-auto-escalada:** un turno del agente
  NUNCA puede subirse a SUPERVISADO desde adentro (no hay tool que cambie el modo).
- **Delegación a otros modelos, puntual y manual:** `cloud_expert_code/marketing`
  (Gemini Flash, borrador) y `opencode_run_task` (OpenCode → Ollama local). Son
  tools que el modelo decide llamar; **no** hay ruteo automático por complejidad.
- **Cola de misiones: DISEÑADA, no implementada** (`lab/ORQUESTACION-REMOTA-DESIGN.md`
  §7). Unidad de trabajo autónoma, estados (encolada → corriendo →
  necesita-confirmación → completada/fallida), worker en background, updates que
  sobreviven desconexión. Es el esqueleto de orquestación de tareas largas.
- **Composición de skills: base YA EXISTE, fábrica FALTA** (`HACIA-RAPHAEL.md §6`).
  El molde `Skill(name, trigger_keywords, prompt_fragment, tool_names)` soporta
  empaquetar un encadenamiento con nombre; falta el componente que detecte el
  patrón repetido y proponga la skill (con gate de aprobación de Damian).
- **El modelo, hoy:** `CLAUDE.md`/`CAPACIDADES` documentan `gpt-oss:120b-cloud`
  (Ollama cloud) o `jarvis-text-v2` (Qwen3-30B) local. **Transición en curso: a
  DeepSeek V4 por API por token** — lo que vuelve el ruteo de modelos (§4)
  **económicamente relevante**, no solo técnico: cada token ahora cuesta plata.

**Diagnóstico:** Jarvis no arranca de cero. Tiene la mitad de una orquestación
consciente (ruteo por skills + modos + cola diseñada). Lo que falta es **atar esas
piezas con un plano** y sumar dos cosas que las notas señalan: **router de modelos**
(Omniroute) y **scheduler/push** (n8n).

---

## 3. Patrón de orquestación recomendado: HÍBRIDO en tres capas

La pregunta del encargo —agente único vs. multi-agente vs. grafo tipo n8n vs.
híbrido— tiene una respuesta clara para el caso de Jarvis: **híbrido, con cada
patrón en la capa donde rinde y ninguno donde estorba.** No es indecisión: es que
los tres resuelven problemas distintos y Jarvis tiene los tres problemas.

```
   ┌──────────────────────────────────────────────────────────────┐
   │  CAPA A — GRAFO DETERMINÍSTICO (estilo n8n)                    │
   │  Disparadores (cron/evento) → pasos fijos → push a un canal    │
   │  Ej: brief matutino, escaneo diario, "misión encolada"         │
   │  NO decide un LLM el flujo; el flujo está escrito.             │
   └───────────────┬──────────────────────────────────────────────┘
                   │ invoca, cuando un paso necesita criterio:
                   ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  CAPA B — ORQUESTADOR-AGENTE (loop actual, agent.py)          │
   │  Un agente que planifica/ejecuta con tool-calling.            │
   │  Ruteo por skills (skills.py) = ya elige el "sub-dominio".    │
   │  Delega sub-tareas acotadas a ejecutores (Capa C).            │
   └───────────────┬──────────────────────────────────────────────┘
                   │ para una sub-tarea de dominio cerrado:
                   ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  CAPA C — EJECUTORES ESPECIALIZADOS (roles, §5)               │
   │  Contexto acotado + subconjunto de tools + prompt de dominio  │
   │  (seguridad, código, vault, lab/pentest, forense, control PC) │
   │  Hoy ya son "skills"; la evolución es darles vida como rol.   │
   └──────────────────────────────────────────────────────────────┘

   Transversal a las tres: ROUTER DE MODELOS (§4) — elige qué modelo
   atiende cada llamada según complejidad/costo, con fallback.
```

### 3.1 Por qué NO multi-agente "de verdad" (varios LLMs deliberando en paralelo)

Es la tentación de moda, y para Jarvis es **la peor opción hoy**, por tres razones
del propio repo:

1. **No hay hardware para dos modelos grandes a la vez** (`agent.py` lo dice
   explícito: *"12GB de VRAM no da para dos modelos grandes"*). Con DeepSeek V4 por
   token, "paralelo" ya no es un problema de VRAM sino de **costo multiplicado**:
   N agentes deliberando = N veces la factura de tokens.
2. **El techo del modelo** (`CAPACIDADES §6.1`): un modelo de esta clase *ejecuta
   flujos guiados, no delibera*. Multi-agente conversando entre sí **amplifica los
   modos de falla** que el código ya parchea (loops de reescritura, archivos
   abandonados). Más agentes ≠ más criterio; es más superficie para que el criterio
   que no hay se note.
3. **Complejidad de gates.** Cada gate (`authorized_targets.yaml`, `dry-run→confirm`,
   `preview_token`) hoy vive en un loop único y auditable. Repartirlo entre agentes
   autónomos multiplica los puntos donde un gate podría saltearse.

Lo que la gente llama "multi-agente" y **sí sirve** es más humilde: **un
orquestador que delega sub-tareas acotadas a ejecutores especializados, uno por
vez, con contexto reducido.** Eso es la Capa B→C, y es casi lo que `skills.py` ya
hace — solo que hoy el "ejecutor" es el mismo turno con menos tools, no una
sub-invocación con su propio presupuesto de contexto.

### 3.2 Por qué SÍ un grafo tipo n8n, pero solo en la Capa A

El loop del agente es malísimo para lo **repetitivo y programado**: pagar un LLM
para decidir "son las 8, hago el brief" es tirar tokens y meter no-determinismo
donde no se quiere ninguno. Ahí un **grafo declarativo** (cron → pasos fijos →
canal) es superior: barato, predecible, testeable. Es exactamente el modelo de la
nota de n8n, y cubre lo que `HACIA-RAPHAEL` Etapa 6 marca **FALTA** (scheduler
general + push). **Pero el LLM solo entra cuando un nodo lo necesita** ("resumí
estos hallazgos"), no para orquestar el flujo.

### 3.3 Por qué el orquestador-agente sigue en el centro (Capa B)

Para lo **abierto y ambiguo** ("auditá este repo y proponé fixes"), el loop de
tool-calling es lo correcto y ya está probado en el núcleo de auditoría/forense
(`CAPACIDADES §7`: *"en este perímetro, 'Jarvis hace y yo corrijo' ya es real"*).
No se reemplaza; se le agrega arriba la Capa A (para lo programado) y abajo la
Capa C (para acotar sub-tareas).

---

## 4. Ruteo de modelos (la idea de Omniroute) — el cambio más rentable ahora

Con la transición a **DeepSeek V4 por API por token**, cada llamada cuesta dinero
real y el ruteo de modelos pasa de "optimización" a **palanca de costo directa**.
La propuesta es un **router de modelos** que se inserta donde hoy está el punto
único de acceso: `app/llm_client.py` ya habla con un endpoint OpenAI-compatible, así
que el router va **detrás de esa misma interfaz** (igual que Omniroute se pone
detrás de Claude Code sin que el cliente cambie).

### 4.1 Ruteo por complejidad, decidido determinísticamente (no por un LLM)

Regla de oro heredada de `skills.py`: **la decisión de ruteo NO la toma un modelo**
(eso pagaría el costo que se intenta evitar). Se decide en el backend, por señales
baratas ya disponibles:

- **La clasificación de `skills.py` ya es una señal de complejidad.** Tareas de
  dominio cerrado y guiado (ingestar CSV, aplicar un fix propuesto, correr un
  escaneo) → **modelo barato**. Tareas abiertas/ambiguas o de planificación
  (auditar y proponer, deliberar un diseño) → **modelo potente**.
- **Señales adicionales sin costo:** longitud/nº de pasos estimados, si el turno es
  de código (ya sube el tope a 50 iteraciones), si es un turno de misión autónoma,
  si viene de un trigger programado (Capa A) vs. chat interactivo.

| Tipo de tarea | Modelo sugerido | Por qué |
|---|---|---|
| Flujo guiado, dominio cerrado (escanear, aplicar fix, ingestar) | Barato / local (`jarvis-text-v2`) | El andamiaje de skills ya compensa al modelo; no hace falta frontera |
| Abierta/ambigua, multi-paso, planificación | Potente (DeepSeek V4 por token) | Es donde el criterio importa y el barato falla (`CAPACIDADES §6.1`) |
| Resumen/redacción de un nodo de un grafo (Capa A) | Barato | Tarea acotada y verificable |
| Embeddings del vault | El de siempre (LM Studio local :1234) | Ya está aparte por diseño, no se toca |

### 4.2 Fallback automático — cerrar el agujero de `§6.2`

`CAPACIDADES §6.2`: *"el loop no reintenta"* y el cloud *"depende de estar logueado
y de la red"*. El router resuelve esto con lo que Omniroute vende como su feature
estrella: **cadena de fallback**. Si DeepSeek V4 (por token) falla, timeout o
rate-limit → cae a un secundario (otro proveedor por token, o el local
`jarvis-text-v2` como red de contención offline). Distinguiendo, eso sí, **error
transitorio de red** (reintentar/rotar, como ya hace `_is_transient_llm_error` en
`agent.py`) de **error de lógica del modelo** (no reintentar el mismo prompt a
ciegas).

### 4.3 Construirlo dentro vs. usar Omniroute/LiteLLM

- **Omniroute tal cual: NO** para producción de Jarvis. La nota misma advierte que
  los proveedores gratis **entrenan con tus datos** — inaceptable con datos de
  pentesting/forense. Sirve como **referencia de diseño** y, si acaso, para
  experimentar en local con tareas sin datos sensibles.
- **LiteLLM (u otro router OpenAI-compatible open-source, self-hosted): opción
  válida** si se quiere no reinventar. Se pone en `127.0.0.1`, habla el mismo
  protocolo que `llm_client.py`, y da fallback/routing/costos hechos.
- **Construirlo dentro: recomendado para la v1**, porque el router que Jarvis
  necesita es **chico** (2-3 modelos, no 290) y la lógica de "qué modelo según
  skill/complejidad" **ya tiene su insumo en `skills.py`**. Una capa fina de
  selección + fallback en `llm_client.py`, con `MODEL_CONTEXT_TOKENS` sincronizado
  por modelo (hoy es una sola variable — habría que volverla por-modelo, ver la
  advertencia de `CLAUDE.md` sobre `num_ctx`). Empezar propio y migrar a LiteLLM
  si crece.

---

## 5. Roles / ejecutores que tiene sentido definir

No son "agentes autónomos" con vida propia: son **ejecutores acotados** que el
orquestador (Capa B) invoca para una sub-tarea de dominio cerrado, con contexto y
tools reducidos. **La buena noticia: ya existen como skills.** El paso es darles
identidad de rol (un prompt de ejecutor + su set de tools + su modelo por defecto
vía el router), no crearlos de cero.

| Rol (ejecutor) | Skill(s) que ya lo respaldan | Tools núcleo | Modelo por defecto |
|---|---|---|---|
| **Orquestador / planificador** | el loop `agent.py` + `core` | `jarvis_reflect`, `obsidian_*`, `research_topic` | Potente (planifica) |
| **Auditor de código/seguridad** | `security_audit` | `security_scan_project`, `code_apply_fix`, `code_run_tests`, `audit_generate_report` | Barato (flujo guiado) |
| **Pentester del lab** | `pentesting` + (futuro) `vm_control`/`ssh_guest` | `nmap`/`sqlmap`/`zap` (gated), control de VMs | Barato/medio |
| **Defensor / antimalware** | `malware_protection` | `yara`, `clamav`, cuarentena (dry-run→confirm) | Barato |
| **Bibliotecario del vault** | `core` (obsidian) | `obsidian_search/save/list`, `research_topic` | Barato |
| **Forense** | `investigation` | pipeline de entidades/grafo (todo pendiente-de-confirmación) | Medio |
| **Manos sobre PC/celular** | `desktop_control`, `phone_control`, `web_forms` | desktop/browser/phone/forms | Barato |

**Principio (de `HACIA-RAPHAEL §6.5`):** esto es **recombinación, no alquimia**.
No emerge un poder nuevo; se le pone nombre y presupuesto a un encadenamiento que
Jarvis ya sabía hacer, para no redescubrirlo cada vez. El orquestador delega **de a
uno**, verifica el resultado, y sigue — no lanza seis ejecutores a deliberar.

---

## 6. Cómo se conecta con lo que ya existe

- **Con `skills.py`:** el ruteo por skills **es** la capa de selección de ejecutor
  y también la señal de ruteo de modelo (§4.1). No se tira; se le agrega (a) invocar
  el ejecutor como sub-tarea con contexto propio y (b) alimentar al router de
  modelos. La **composición de skills** de `HACIA-RAPHAEL §6` es el mecanismo por el
  cual nacen ejecutores nuevos: Jarvis propone, Damian aprueba con `proposal_id`.
- **Con `operation_mode.py`:** la orquestación respeta los dos modos tal cual. Los
  flujos de la Capa A (cron/misiones) corren **AUTÓNOMOS** por default (sandbox
  acotado) — es justo el caso de uso para el que se diseñó el fail-safe. El chat
  interactivo sigue SUPERVISADO. El guardrail anti-auto-escalada se mantiene: ni el
  orquestador ni un ejecutor pueden subir el modo desde adentro de un turno.
- **Con la cola de misiones (`ORQUESTACION-REMOTA-DESIGN.md §7`):** es la **Capa A
  para tareas largas**. Una misión es un flujo con estados; el paso
  `necesita-confirmación` es el gate remoto atado a cada acción (estilo
  `preview_token`/`proposal_id`). La orquestación propuesta no la reemplaza: la
  **generaliza** — la cola pasa a ser un caso del scheduler/grafo general.
- **Con los gates:** ninguno se toca ni se debilita. El router de modelos y el grafo
  de flujos son **infraestructura de ejecución**; los gates de scope
  (`authorized_targets.yaml`), irreversibilidad (`dry-run→confirm`) y aprobación
  (`proposal_id`) siguen exactamente donde están. Un flujo de la Capa A que llegue a
  algo gated **se detiene y pide OK**, igual que una misión.
- **Con `jarvis_reflect` + el bucle nocturno:** son la memoria de procedimiento. El
  bucle de `DETECCION-ESTRES-NOCTURNO` ya es la forma temprana de "aprender una
  rutina desde lo observado" (destila reglas YARA). La orquestación consciente
  extiende ese patrón a flujos completos, siempre con Damian firmando.

---

## 7. Herramientas externas vs. construir dentro

| Pieza | Recomendación | Por qué |
|---|---|---|
| **Router de modelos** | **Dentro** para v1 (capa fina en `llm_client.py`); LiteLLM self-hosted si crece | Necesita 2-3 modelos, no 290; el insumo de decisión ya está en `skills.py`. Omniroute-gratis: NO por privacidad de datos |
| **Grafo de flujos / scheduler** | **Empezar dentro** (scheduler simple + la cola de misiones ya diseñada); evaluar **n8n self-hosted** solo si los flujos crecen mucho | n8n mete un runtime aparte (Node), un segundo lugar donde viven secretos, y otro sistema que auditar. Para 3-4 flujos, un scheduler propio integrado con los gates y el audit log firmado es más simple y seguro. n8n vale si Damian quiere muchas integraciones no-código |
| **Agent Reach** | **Dentro, como tool puntual** detrás del credential store DPAPI | Es un sensor, no orquestación; reusar cookies de sesión es sensible y ya hay patrón cifrado (`forms/`) |
| **Push proactivo (canal saliente)** | **Dentro**, reusando el WebSocket al celular (`phone_link.py`) que ya empuja updates de misión | El canal ya existe para misiones; generalizarlo a brief/alerta es incremental (Etapa 6 de HACIA-RAPHAEL) |

**Criterio general (de la nota One-Person AI Business):** cada integración externa
suma superficie de ataque, un lugar más donde viven secretos, y algo más que
mantener. En un proyecto cuyo diseño entero gira alrededor de gates y auditoría
firmada, **construir dentro gana por defecto**; una herramienta externa se justifica
solo cuando el trabajo que elimina es grande y no hay forma barata de replicarlo.

---

## 8. Plan por fases (sin romper lo que anda)

De menor a mayor riesgo. Cada fase es útil sola y no depende de la siguiente.
Criterio de "listo" heredado del repo: **tests en verde (`cd backend && pytest`),
auditoría registrando, ningún gate debilitado.**

### Fase 0 — Router de modelos con fallback (el más rentable ya)

Capa fina de selección de modelo en `app/llm_client.py`: elige modelo por la señal
de `skills.py` + complejidad (§4.1), con cadena de fallback (§4.2) reusando
`_is_transient_llm_error`. `MODEL_CONTEXT_TOKENS` pasa a ser por-modelo.

*Listo cuando:* una tarea guiada usa el barato y una abierta usa el potente,
verificable en logs; si el primario falla/timeout, cae al secundario sin cortar el
turno; el costo por token baja de forma medible; tests del router en verde.

### Fase 1 — Ejecutores con identidad de rol (formalizar lo que ya hay)

Convertir las skills en ejecutores invocables como sub-tarea con contexto acotado
(§5), cada uno con su modelo por defecto vía el router. No inventa dominios: usa los
8 que ya existen.

*Listo cuando:* el orquestador delega una sub-tarea de dominio cerrado a un ejecutor
con tools/prompt reducidos y verifica el resultado antes de seguir; el
comportamiento de chat de siempre no cambia cuando no hay delegación.

### Fase 2 — Scheduler general + un flujo de la Capa A

Scheduler de tareas del agente (lo que `HACIA-RAPHAEL` Etapa 6 marca FALTA) y **un**
flujo determinístico de estreno: el **brief matutino** del escaneo diario que ya
corre, empujado al celular por el canal de `phone_link.py`.

*Listo cuando:* a una hora fija, sin intervención, Jarvis arma el brief y lo empuja;
el flujo es determinístico (el LLM solo redacta el resumen); corre AUTÓNOMO con
sandbox acotado; si toca algo gated, se detiene.

### Fase 3 — Generalizar la cola de misiones como grafo

Unificar la cola de misiones (`ORQUESTACION-REMOTA-DESIGN.md §7`) con el scheduler:
las misiones pasan a ser un tipo de flujo, con sus estados y el gate
`necesita-confirmación` intacto. (Depende de las Fases 2-4 de la orquestación
remota — Tailscale, SSH — para el camino remoto; en local se puede antes.)

*Listo cuando:* una misión se modela como flujo del scheduler, se detiene en cada
paso gated y espera OK de un solo uso, y deja nota en el vault; ningún gate remoto
amplía `authorized_targets.yaml`.

### Fase 4 — Fábrica de composición de skills (con gate)

El componente que detecta patrones de tools repetidos y **propone** una skill/rol
nuevo (`HACIA-RAPHAEL §6.3`), que Damian aprueba con `proposal_id`. Es la última por
ser la de mayor radio: una skill auto-creada que luego se ejecuta sola es "un arma
cargada" (§6.4 de HACIA-RAPHAEL) — **solo propone, nunca activa sin firma**.

*Listo cuando:* Jarvis detecta una cadena recurrente, redacta la propuesta de skill
(nombre, tools, keywords, prompt), y **no** la incorpora sin aprobación explícita de
un solo uso; una propuesta rechazada no deja rastro ejecutable.

---

## 9. Encuadre honesto: qué gana de verdad y qué NO

**Lo más importante, dicho sin maquillar:** la orquestación consciente **no
convierte a un modelo mediano en uno de frontera.** El techo de `CAPACIDADES §6.1`
sigue en pie — *"un 30B/120B ejecuta, no delibera"*, y DeepSeek V4 por token sube el
piso pero no cambia la naturaleza del problema: sobre tareas abiertas, ambiguas, de
muchos pasos con criterio encadenado, el modelo va a fallar de las mismas formas que
el código ya parchea (loops, archivos abandonados, soluciones inventadas). Ninguna
arquitectura de orquestación arregla eso; en el peor caso, un multi-agente mal hecho
lo **amplifica**.

**Lo que la orquestación consciente SÍ gana, y es real:**

- **Costo.** El router de modelos (Fase 0) es plata directa ahorrada: barato para lo
  guiado, caro solo donde importa. Con facturación por token, esto se paga solo.
- **Robustez.** El fallback cierra el agujero de "el cloud se cayó / rate-limit" que
  hoy corta el turno. Menos flujos rotos a la mitad.
- **Eficiencia y consistencia.** Acotar contexto+tools por ejecutor (lo que skills
  ya empieza) hace cada llamada más barata y más certera — el modelo mediano rinde
  **mejor** con el problema recortado, que es justo para lo que el andamiaje existe.
- **Alcance sin criterio nuevo.** El scheduler + push (Fases 2-3) le da a Jarvis
  trabajo desatendido y proactividad **en flujos determinísticos** — donde no hace
  falta criterio, solo constancia. Ahí un modelo mediano es perfectamente capaz,
  porque el flujo lo pone el diseño, no el modelo.
- **Memoria de procedimiento.** La fábrica de skills (Fase 4) evita redescubrir la
  misma rutina — recombinación con nombre, no inteligencia emergente.

**La regla que no cambia:** delegá tareas **acotadas y verificables**, no objetivos
abiertos. La orquestación mueve la frontera de "qué es acotado" (más flujos entran),
baja el costo y sube la robustez — pero **no delega criterio que el modelo no tiene.**
Eso, y no un grafo elegante, es lo que hace que "Jarvis hace y yo corrijo" siga
siendo verdad a mayor escala.

---

## Referencias

### Notas del vault (playlist "Info para Jarvis")

- `backend/obsidian_vault/jarvis/integracion-automatica-de-modelos-de-ia-gratuitos-con-omniroute-para-flujos-de-trabajo-eficientes.md` — OmniRoute (`o7hPSFNVBjo`)
- `backend/obsidian_vault/jarvis/solucion-para-evitar-limites-de-tokens-en-ia-omnirroot-con-gestion-automatica-de-proveedores.md` — Omnirroot (`p31sfv8CI5A`)
- `backend/obsidian_vault/jarvis/automatizacion-de-alertas-diarias-sobre-carreras-de-running-con-n8n.md` — n8n (`yP0PM-fpnXo`)
- `backend/obsidian_vault/jarvis/agent-reach-acceso-libre-a-sitios-con-login-para-agentes-de-ia-sin-codigo.md` — Agent Reach (`ImLUT5S_l9Q`)
- `backend/obsidian_vault/jarvis/como-construir-un-negocio-de-ia-con-un-solo-persona-usando-claude-code.md` — One-Person AI Business (`LVAHYV4Xrto`)

### Código y diseños del repo

- `backend/app/agent.py` — loop LLM→tool→LLM, perfiles, `_is_transient_llm_error`, topes de iteración.
- `backend/app/skills.py` — `Skill`, `SKILLS`, `classify` determinístico, `CORE_*`.
- `backend/app/operation_mode.py` — SUPERVISADO/AUTÓNOMO, fail-safe, anti-auto-escalada.
- `backend/app/llm_client.py` — endpoint OpenAI-compatible único (donde iría el router).
- `lab/ORQUESTACION-REMOTA-DESIGN.md` — cola de misiones (§7), gates remotos.
- `vision/CAPACIDADES-REALES-DE-JARVIS.md` — techo del modelo (§6.1), falta de reintentos (§6.2), ruteo por skills.
- `vision/HACIA-RAPHAEL.md` — Etapa 5 (orquestación remota), Etapa 6 (push proactivo, FALTA), §6 (composición de skills).
- `CLAUDE.md` — modelos en uso, `LMSTUDIO_MODEL`, `MODEL_CONTEXT_TOKENS`, gates.
