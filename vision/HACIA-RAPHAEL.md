# HACIA-RAPHAEL.md — Visión y hoja de ruta: el "Gran Sabio" de Jarvis

> Documento de **visión y estrategia** (no ejecutable, no es código). Traduce la
> habilidad **Gran Sabio → Raphael** de *That Time I Got Reincarnated as a Slime*
> (Tensura) en capacidades **concretas y reales** de Jarvis, ancladas en lo que ya
> existe en el repo y en los diseños de `lab/`. Sirve para **ordenar el rumbo del
> proyecto**, no para vender nada.
>
> Creado: 2026-08-17. Alinea con: `CLAUDE.md` (arquitectura, modelos, gates),
> `ESTADO.md` (estado operativo) y los diseños de `lab/`
> (`CYBER-RANGE-DESIGN.md`, `DETECCION-ESTRES-NOCTURNO.md`,
> `DEFENSA-KERNEL-GRATIS-DESIGN.md`, `DEFENSA-PRIORIDADES.md`,
> `ORQUESTACION-REMOTA-DESIGN.md`, `RETOMAR-LAB.md`).
>
> **Regla de este documento:** todo estado y toda referencia apunta a algo real
> del repo. Donde algo todavía no existe, se dice **FALTA** sin maquillarlo.

---

## 1. Encuadre honesto: qué es alcanzable y qué es ficción

El Gran Sabio (`大賢者`), y su evolución Raphael (Señor de la Sabiduría), es en el
anime una habilidad tipo IA que acompaña a Rimuru: **analiza cualquier cosa al
instante**, **avisa y aconseja de forma proactiva**, **administra procesos de forma
autónoma incluso cuando Rimuru "no está mirando"**, **procesa en paralelo**,
**simula el resultado de una acción antes de tomarla**, y **gestiona el cuerpo de
Rimuru** según sus órdenes o su conveniencia. Más adelante, como Raphael,
**aprende y evoluciona** por su cuenta.

La tesis de este documento es simple:

> La **esencia funcional** de esa habilidad —un copiloto que percibe, avisa,
> recuerda, simula y actúa con autonomía acotada— **es alcanzable y responsable**.
> La versión "superinteligencia perfecta, omnisciente e infalible" **es ficción**,
> y perseguirla como si fuera ingeniería sería un error de diseño.

### 1.1 El ROL funcional (alcanzable)

Lo que sí se puede construir, y de hecho ya está a medio construir en este repo,
es el **rol** del Gran Sabio:

- **Analizar** archivos, procesos y la postura de seguridad de la PC (módulo
  `app/malware/`, escáneres de `security/` + `quality/`).
- **Avisar y aconsejar** en base a lo que observa (alertas, resúmenes, journaling
  al vault).
- **Trabajar mientras Damian no mira** (escaneo diario en background, cola de
  misiones, bucle de detección nocturno, tareas programadas).
- **Coordinar varias tareas** a la vez (orquestación de misiones/subprocesos).
- **Simular antes de actuar** (el cyber range, el estrés de detección, los
  dry-run con preview).
- **Gestionar el "cuerpo digital"**: la PC, las VMs del lab, los recursos, los
  archivos, la red — el equivalente real del "cuerpo" que Rimuru administra.
- **Recordar y mejorar** (vault Obsidian + `jarvis_reflect` + el bucle
  auto-mejorante de detección).

### 1.2 Lo que es ficción (y por qué está bien que lo sea)

- **Omnisciencia.** Raphael "sabe todo". Jarvis ve **solo lo que su telemetría le
  muestra**: eventos de Windows que el kernel expone, resultados de escaneos,
  archivos dentro de `FS_ALLOWED_ROOT`. Ver más es cuestión de **más sensores**,
  nunca de magia — y cada sensor tiene un costo real.
- **Infalibilidad.** Raphael no se equivoca. Un detector real tiene **falsos
  positivos y falsos negativos**; por eso todo lo que bloquea corre primero en
  **modo auditoría** (`DEFENSA-PRIORIDADES.md`) antes de tocar nada.
- **Control de un cuerpo biológico / energía mágica.** No hay equivalente. El
  "cuerpo" de Jarvis es **la PC y sus VMs**, y punto.
- **Autonomía total.** Raphael actúa "por conveniencia de Rimuru" sin pedir
  permiso. Jarvis **no**: la autonomía real convive con **gates de confirmación**
  para todo lo peligroso o irreversible (`authorized_targets.yaml`, `dry-run →
  confirm=true`, `preview_token`, `proposal_id`). Eso no es una limitación a
  superar: **es la característica que lo hace confiable** (ver §5).

Dicho de una vez: el objetivo no es un dios de bolsillo. Es un **copiloto
persistente, con memoria y criterio, que hace mucho solo y pide permiso donde el
daño sería serio.** Eso es reproducible. Y ya está empezado.

---

## 2. Tabla maestra — habilidad del anime → capacidad real de Jarvis

Estados: **YA EXISTE** (implementado y en el repo) · **DISEÑADO** (hay un plan
escrito, sin código) · **FALTA** (ni implementado ni diseñado en detalle).

| Habilidad del Gran Sabio / Raphael | Equivalente real en Jarvis | Estado | Dónde vive (archivo / doc) |
|---|---|---|---|
| **Analizar / Assess** — "analizar cualquier cosa al instante" | Análisis de archivos, procesos y postura de seguridad: YARA + ClamAV + heurística conductual + FIM + monitor del proceso propio; escaneo bajo demanda y triage de hallazgos | **YA EXISTE** | `backend/app/malware/` (`engine.py`, `yara_scanner.py`, `clamav_scanner.py`, `behavioral_watcher.py`, `integrity.py`, `process_monitor.py`); `backend/app/tools/malware.py`; escáneres `security/`+`quality/` |
| **Analizar código / entender un sistema** | Indexado de cualquier proyecto en un grafo (archivos, funciones, clases, imports) + escaneo real de seguridad/calidad (Semgrep, Bandit, Ruff, mypy…) | **YA EXISTE** | `backend/app/codebase/`, `backend/app/tools/codebase.py`, `security_scan.py`, `quality_scan.py` |
| **Introspección** — "conocerse a sí mismo" | Jarvis lee y razona sobre su propio código | **YA EXISTE** | `backend/app/introspection/`, `backend/app/tools/reflect.py` |
| **Notificar y aconsejar de forma proactiva** — avisos y consejo sin que se lo pidan | Escaneo diario en background + on-access de Descargas/Escritorio/Temp que **detecta y registra** por su cuenta | **YA EXISTE (parcial)** | `backend/app/malware/fullscan.py` (loop diario en background desde el startup), on-access en `app/malware/` |
| **Notificar y aconsejar de forma proactiva** — el "push" en sí: brief matutino, alerta que llega a Damian sin abrir el chat | Canal de notificación proactiva (empujar alertas/resumen al celular o al escritorio) | **FALTA** (hay piezas: journaling al vault, updates de misión al celular en el diseño remoto) | Empuje al celular diseñado en `lab/ORQUESTACION-REMOTA-DESIGN.md` §7 (updates de misión); brief/alerta autónoma como tal, sin doc dedicado |
| **Administrar procesos mientras Rimuru "no mira"** — trabajo autónomo en ausencia | Escaneo diario desatendido + **bucle de detección nocturno** que corre "toda la noche" con convergencia por pases | **YA EXISTE (escaneo)** + **DISEÑADO (bucle nocturno)** | `fullscan.py` (ya corre); `lab/DETECCION-ESTRES-NOCTURNO.md` (bucle adaptativo por técnica, aún sin código, depende del range) |
| **Administrar procesos en ausencia** — recibir órdenes y ejecutarlas estando lejos | Canal remoto seguro (Tailscale) + **cola de misiones** con confirmaciones remotas | **DISEÑADO** | `lab/ORQUESTACION-REMOTA-DESIGN.md` (Fases 1–4, §10) |
| **Tareas programadas** — "hacé esto cada noche / a tal hora" | Disparador temporal recurrente de misiones/escaneos | **FALTA** (el escaneo diario está hardcodeado por intervalo; no hay un scheduler general de tareas del agente) | Intervalo en `fullscan.py` (`malware_full_scan_interval_hours`); scheduler general sin implementar |
| **Procesamiento en paralelo** — "pensar muchas cosas a la vez" | Orquestación de múltiples tareas/misiones simultáneas (worker en background, estados de misión) | **DISEÑADO** — con un límite real de hardware: no hay dos modelos grandes en paralelo (12 GB de VRAM) | `lab/ORQUESTACION-REMOTA-DESIGN.md` §7 (cola/worker); límite documentado en `backend/app/agent.py` (~línea 256) |
| **Simular / predecir** — "calcular el resultado antes de actuar" | **Cyber range** aislado (probar ataques/defensa sin tocar sistemas reales) + **prueba de estrés de detección** ("¿aguanta la defensa?") | **DISEÑADO** (range en armado) | `lab/CYBER-RANGE-DESIGN.md`, `lab/DETECCION-ESTRES-NOCTURNO.md`, `lab/RETOMAR-LAB.md` (VirtualBox + Kali + Metasploitable ya montados) |
| **Simular antes de actuar** — el "qué pasaría si" en cada acción | Patrón **dry-run → preview → confirm** en todo lo destructivo (fixes de código, submit de formularios, cuarentena) | **YA EXISTE** | `selfrepair/` (`proposal_id`), `app/tools/web_forms.py` (`preview_token`), `app/malware/quarantine.py` (mover, no borrar) |
| **Gestionar el "cuerpo" de Rimuru** — administrar el cuerpo según órdenes/conveniencia | Gestión del **cuerpo digital**: control de la PC (mouse/teclado/ventanas), shell real, navegador, archivos | **YA EXISTE** | `app/tools/desktop.py`, `pc_command.py`, `browser.py`, `filesystem.py`, `phone.py`; `app/shell_exec.py` |
| **Gestionar el "cuerpo"** — administrar las VMs del lab como "órganos" | Tool `vm_control` (encender/apagar/snapshot de las VMs del range, con allow-list) | **DISEÑADO** | `lab/ORQUESTACION-REMOTA-DESIGN.md` §5 y Fase 1 (§10); wrapper sobre `VBoxManage`, sin código aún |
| **Memoria / aprendizaje** — "Raphael recuerda y aprende" | Vault Obsidian (notas .md reales, búsqueda semántica por embeddings) + memoria de criterio (`jarvis_reflect`) | **YA EXISTE** | `backend/app/obsidian/`, `backend/obsidian_vault/jarvis/`, `app/tools/reflect.py` (JSONL append-only, tipos/contexto/vigente) |
| **Evolucionar** — "Raphael mejora sus propias reglas" | Bucle auto-mejorante: entre pases nocturnos, Jarvis **propone mejoras a las reglas de detección** (Damian aprueba) + auto-reparación del propio código | **DISEÑADO** (detección) + **YA EXISTE con gate (self-repair)** | `lab/DETECCION-ESTRES-NOCTURNO.md` §3 (bucle de convergencia, mejoras aprobadas por Damian); `backend/app/selfrepair/` (dry-run libre, aplicar con `proposal_id`) |
| **Fusión / composición de habilidades** — "Raphael une skills para crear una nueva y mejor" | **Composición de skills**: Jarvis detecta patrones de encadenamiento de tools que repite (ej. escanear archivo → hash en VirusTotal → cuarentena → nota al vault) y los **cristaliza en una skill nueva de alto nivel**, con nombre propio, reutilizable, que vive en el mismo framework de skills existente | **Base YA EXISTE** (framework de skills + introspección; el bucle que genera reglas YARA nuevas ya es una forma temprana) · **auto-composición proactiva: FALTA** | `backend/app/skills.py` (dataclass `Skill`, dict `SKILLS`, `classify`), `backend/app/introspection/`, `app/tools/reflect.py`; forma temprana en `lab/DETECCION-ESTRES-NOCTURNO.md` §3 (ver §6 de este doc) |
| **Auto-defensa / respuesta automática** — "Raphael protege a Rimuru solo" | Capa de **detección + respuesta "kernel-grade" gratis**: ver con telemetría de Windows (ETW/Sysmon/AMSI) y **bloquear** con enforcement de Microsoft (ASR/AppLocker/WDAC/WFP), sin driver propio | **DISEÑADO** (hoy: cuarentena reversible ya existe) | `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`, `lab/DEFENSA-PRIORIDADES.md`; base ya real en `app/malware/quarantine.py`, `sysmon_monitor.py` (experimental, apagado) |
| **Actuar como extensión de Rimuru** — "sus manos a distancia" | Orquestación remota desde el celular: la misma intención de Damian, con más manos, sin debilitar ningún gate | **DISEÑADO** | `lab/ORQUESTACION-REMOTA-DESIGN.md` (§1.2 "extensión de Damian ≠ sin gates") |
| **Registrar todo lo que hace** — trazabilidad total | Grabación de pantalla automática alrededor de las tools + audit log firmado (Ed25519) + journaling al vault | **YA EXISTE** | `app/recording.py`, `app/investigation/` (log append-only firmado), vault |

**Lectura rápida de la tabla:** el **percibir**, el **recordar**, el **simular en
chico** (dry-run) y el **gestionar el cuerpo digital** ya son reales. Lo que está
**diseñado pero sin código** es casi todo lo que da la sensación de "Gran Sabio de
verdad": el **trabajo autónomo prolongado** (bucle nocturno + misiones remotas),
la **respuesta automática kernel-grade**, y la **simulación en grande** (el range).
Lo que **falta incluso en diseño** es el **push proactivo** (brief/alerta que llega
sola a Damian) y un **scheduler general** de tareas del agente.

---

## 3. Hoja de ruta por etapas — hacia "el Raphael real"

De lo que ya está a lo aspiracional. Cada etapa **habilita una sensación nueva** y
se apoya en los planes por fases que ya existen en los diseños. El criterio de
"listo" hereda el de los diseños: **tests en verde, auditoría registrando, ningún
gate debilitado, y todo lo que bloquea pasa por audit antes de enforce.**

### Etapa 0 — "El Sabio que percibe y recuerda" (HOY, YA EXISTE)

Lo que Jarvis ya es: analiza archivos/procesos/código, escanea la PC todos los
días en background, recuerda en el vault y en `jarvis_reflect`, simula en chico con
dry-run/preview antes de cada acción destructiva, y deja registro firmado de todo.

**Habilita:** un asistente que **ve y recuerda**, con acciones reales sobre la PC
pero freno donde el daño sería irreversible. Es la base; nada de lo de abajo la
reemplaza, todo la extiende.

### Etapa 1 — "El Sabio que administra el cuerpo" (`vm_control` local)

Primer bloque de `ORQUESTACION-REMOTA-DESIGN.md` (Fase 1) + terminar de montar el
range (`RETOMAR-LAB.md`). Jarvis gana manos sobre las VMs del lab: encender,
apagar, snapshotear, restaurar — con allow-list y auditoría, **solo en local**.

**Habilita:** que Jarvis administre su "cuerpo digital" ampliado (la PC **y** sus
VMs) como Rimuru administra su cuerpo. Riesgo bajo: no toca la red, solo VMs
propias.

### Etapa 2 — "El Sabio que simula en grande" (cyber range vivo)

Completar el range (`RETOMAR-LAB.md` pasos a–d: Metasploitable + Kali +
conectividad + snapshot BASE) y correr la Fase 0 (recon) de
`CYBER-RANGE-DESIGN.md`. Con el range vivo, Jarvis puede **ensayar** ataque y
defensa en un mundo cerrado antes de confiar en nada.

**Habilita:** la "simulación de resultados" de Raphael, pero contenida: un
laboratorio donde romper y restaurar desde snapshot cuesta cero. Aislamiento por
tres capas (red cerrada + blancos propios + `authorized_targets.yaml`).

### Etapa 3 — "El Sabio que trabaja de noche" (bucle de detección nocturno)

Con el range vivo, correr el bucle de `DETECCION-ESTRES-NOCTURNO.md`: emulación de
adversarios (Atomic Red Team / Caldera) contra un blanco del lab, con Jarvis de
defensor puntuando su propia detección, journaling al vault y **bucle de
convergencia por pases**. Entre pase y pase, **propone mejoras a las reglas** que
Damian aprueba.

**Habilita:** dos cosas muy "Raphael" a la vez — **trabajo autónomo prolongado
mientras Damian duerme** y **evolución real** (la defensa mejora sola, con Damian
como aprobador). El gate de "las mejoras las confirma Damian" es lo que lo hace
sano.

### Etapa 4 — "El Sabio que se defiende solo" (respuesta kernel-grade)

Las fases de `DEFENSA-KERNEL-GRATIS-DESIGN.md` / `DEFENSA-PRIORIDADES.md`, en su
orden: paso cero (Defender a full + Tamper Protection), después **detección**
(Sysmon → ETW → AMSI) para darle a Jarvis el **PID+imagen** que hoy le falta, y
recién al final **enforcement** (ASR → AppLocker → WDAC → WFP), **siempre en audit
largo antes de bloquear**.

**Habilita:** la auto-defensa de Raphael — no solo *ver* el ransomware sino *matar
el proceso* que cifra y *cortar* el C2. Visibilidad y bloqueo de nivel kernel **sin
un driver propio** (riesgo de BSOD = 0, presupuesto = 0).

### Etapa 5 — "El Sabio a distancia" (orquestación remota + misiones)

Las Fases 2–4 de `ORQUESTACION-REMOTA-DESIGN.md`: endpoint sobre Tailscale,
ejecución en guest por SSH, y la **cola de misiones con confirmaciones remotas**.
Damian, fuera de casa, encola una misión desde el celular; Jarvis la corre solo en
el lab, empuja progreso, **se detiene en cada paso gated y espera OK explícito**, y
deja la nota en Obsidian con resumen al celular.

**Habilita:** Jarvis como **extensión de Damian a distancia** — la misma intención,
más manos — que es exactamente la relación Rimuru↔Raphael. Es la etapa de **mayor
autonomía**, por eso va última, apoyada en todas las capas ya probadas, y con los
gates intactos (el canal remoto agrega una puerta de entrada, no abre ninguna
interna).

### Etapa 6 — "El Sabio que avisa primero" (proactividad de verdad) — FALTA

La pieza que hoy **no está ni diseñada en detalle**: el **push proactivo**. Que
Jarvis no espere a que Damian abra el chat, sino que **empuje** un brief ("esto
pasó anoche, esto te conviene mirar") o una **alerta** en el momento en que detecta
algo. Requiere dos cosas nuevas: un **canal de notificación saliente**
(celular/escritorio) y un **scheduler general** de tareas del agente (hoy solo el
escaneo diario corre por intervalo hardcodeado). Complementa el push de misiones ya
diseñado en la orquestación remota.

**Habilita:** el rasgo más característico del Gran Sabio — que **hable primero**,
que aconseje sin que se lo pidan. Es lo que convierte "un asistente que responde"
en "un copiloto que acompaña".

---

### Resumen de la hoja de ruta

| Etapa | Nombre | Se apoya en | Estado de partida |
|---|---|---|---|
| 0 | El Sabio que percibe y recuerda | `app/malware/`, vault, `reflect`, dry-run | **YA EXISTE** |
| 1 | El Sabio que administra el cuerpo | ORQUESTACION Fase 1 (`vm_control`) + RETOMAR-LAB | DISEÑADO |
| 2 | El Sabio que simula en grande | CYBER-RANGE (Fase 0 recon) | DISEÑADO / en armado |
| 3 | El Sabio que trabaja de noche | DETECCION-ESTRES-NOCTURNO (bucle + convergencia) | DISEÑADO |
| 4 | El Sabio que se defiende solo | DEFENSA-KERNEL-GRATIS + PRIORIDADES | DISEÑADO |
| 5 | El Sabio a distancia | ORQUESTACION Fases 2–4 (Tailscale + misiones) | DISEÑADO |
| 6 | El Sabio que avisa primero | push proactivo + scheduler general | **FALTA** |
| **T** | **El Sabio que fabrica habilidades** (composición de skills) | `skills.py` + introspección + `reflect` | base **YA EXISTE**, auto-composición **FALTA** |

Las etapas 1–5 son **secuenciales por dependencia y por riesgo** (cada una asume
la anterior probada). La etapa 6 es **transversal**: se puede empezar en chico
(un brief nocturno del escaneo que ya corre) sin esperar a las demás, y crece a
medida que hay más para reportar.

La **Etapa T — composición de skills (§6)** es la otra capacidad **transversal**,
y potencia a *todas* las anteriores: cada patrón de tools que Damian y Jarvis
repiten en cualquiera de las etapas (auditar, defender, orquestar el lab, atender
una misión remota) es candidato a cristalizarse en una skill nueva reutilizable.
No es una etapa "que viene después", sino una capa que **hace más eficientes las
demás a medida que se usan** — siempre detrás del gate de aprobación de Damian.

---

## 4. Principios de diseño — qué hace que "se sienta como el Gran Sabio"

No es la potencia del modelo lo que da la sensación de Raphael. Son cinco rasgos, y
cuatro de ellos ya guían el código de este repo:

1. **Proactividad.** El Sabio habla primero. Hoy Jarvis lo hace a medias (escanea y
   registra solo); la Etapa 6 lo completa con push saliente. *Sin proactividad es
   una herramienta; con proactividad es un copiloto.*

2. **Presencia persistente.** El Sabio siempre está. Se traduce en **procesos en
   background que sobreviven a que Damian cierre el chat**: escaneo diario
   (`fullscan.py`, ya real), bucle nocturno, worker de misiones. La continuidad la
   dan los servicios de fondo, no la sesión de chat.

3. **Memoria.** El Sabio recuerda todo lo aprendido. Vault Obsidian + `jarvis_reflect`
   ya dan continuidad de criterio **entre conversaciones que no comparten historial**.
   La memoria es lo que hace que no haya que repetirle el contexto cada vez.

4. **Autonomía acotada por gates.** El Sabio actúa solo — pero el nuestro **para
   donde el daño sería serio**. `authorized_targets.yaml`, `dry-run → confirm=true`,
   `preview_token`, `proposal_id`, blocklist + auditoría de shell. La autonomía sin
   frenos no es más Raphael: es menos confiable (ver §5).

5. **Transparencia.** Damian **siempre** entiende qué hizo Jarvis y por qué.
   Grabación de pantalla alrededor de las acciones, audit log firmado, notas al
   vault, comentarios de código con fecha y razonamiento. Un Sabio de caja negra no
   sirve: la confianza se construye sobre poder auditar cada paso.

El norte de diseño, en una línea: **máxima percepción, memoria y trabajo de fondo;
autonomía generosa donde es seguro y frenada donde no; y todo auditable.**

---

## 5. Límites y riesgos — por qué los gates son la diferencia

Sin dramatizar, pero sin barrer nada bajo la alfombra:

**La autonomía total sin frenos es una mala idea, y no por miedo abstracto.** Este
repo tiene capacidades que hacen daño real si se equivocan: `pc_run_command` corre
shell de verdad (y **no es un sandbox**, es una blocklist de patrones); la
cuarentena mueve archivos; los fixes de código reescriben el propio Jarvis; las
tools de pentest atacan de verdad. Un agente que actúe sobre todo eso **sin
confirmación** amplifica cada error del modelo —o cada instrucción envenenada— a la
velocidad de la máquina. El Raphael de ficción no se equivoca; el nuestro sí puede.

**Los gates son precisamente lo que separa un asistente confiable de uno
peligroso.** No son burocracia que "algún día" se sacará: son la característica de
producto. En concreto:

- **`authorized_targets.yaml`** — control técnico de scope que **ni las tools ni el
  LLM pueden escribir**. Escanear fuera de scope puede ser ilegal; solo Damian lo
  edita a mano. Ningún camino remoto lo amplía.
- **`dry-run → confirm=true` / `preview_token` / `proposal_id`** — nada
  irreversible pasa sin un segundo paso explícito de Damian, atado a *esa* acción
  concreta, de un solo uso, con TTL corto.
- **Enforcement siempre en audit primero** (`DEFENSA-PRIORIDADES.md`): lo que
  bloquea corre en modo auditoría el tiempo suficiente para conocer sus falsos
  positivos —incluido no romper el propio Jarvis— antes de tocar nada.
- **Flags para apagar cada capacidad invasiva** sin tocar código
  (`DESKTOP_CONTROL_ENABLED`, `PC_SHELL_ENABLED`, `NMAP_ENABLED`, …).

**Riesgos abiertos que conviene tener presentes** (ya anotados en `ESTADO.md` y el
vault): `FS_ALLOWED_ROOT` por default es el **HOME entero**, no solo el repo (hay
una mitigación barata pendiente de una línea); `pc_run_command` no es sandbox real;
y con el canal remoto, más superficie de entrada = más disciplina en la
autenticación. Ninguno es bloqueante para avanzar, todos merecen no olvidarse.

**El encuadre final.** Perseguir la fantasía de un Sabio infalible llevaría a
sacar los frenos "porque total no se equivoca". Es al revés: **asumir que sí se
equivoca es lo que permite darle cada vez más autonomía con tranquilidad.** Cada
gate que se mantiene es una unidad más de autonomía que se puede conceder sin
jugarse la PC. Ese es el trato, y es lo que hace que este Raphael valga la pena
construirlo.

---

## 6. Composición de skills — la "fusión de habilidades" de Raphael

En el anime, la capacidad que hace saltar al Gran Sabio a Raphael es **fusionar
skills**: unir habilidades que ya existen para crear una nueva, con nombre propio,
mejor que la suma de las partes. Es el rasgo más "de nivel superior" de toda la
habilidad — y tiene un equivalente real, concreto y ya medio construido en este
repo.

### 6.1 El equivalente real: composición de skills

Jarvis ya organiza sus capacidades en **skills**: `backend/app/skills.py` define una
dataclass `Skill(name, trigger_keywords, prompt_fragment, tool_names)`, las registra
en el dict `SKILLS`, y una función `classify()` **determinística por palabras clave**
decide qué skill(s) activar en cada mensaje. Una skill, en este repo, **no es más que
un molde**: un nombre, cuándo aplica, un fragmento de prompt, y **qué conjunto de
tools agrupa**. Ya conviven ocho (`investigation`, `security_audit`, `pentesting`,
`malware_protection`, `desktop_control`, `web_forms`, `phone_control`,
`code_delegation`), cada una empaquetando las tools de su dominio.

La capacidad nueva es **composición de skills**: que Jarvis **observe los patrones de
encadenamiento de tools que repite seguido** —por ejemplo *escanear un archivo →
consultar su hash en VirusTotal → ponerlo en cuarentena → anotar el resultado en el
vault*— y los **cristalice en una skill nueva de más alto nivel**, con nombre propio
(ej. `triage_archivo_sospechoso`), reutilizable, que vive exactamente en el mismo
framework de skills (`skills.py`) que las que ya existen. La habilidad nueva **no es
una tool nueva**: es una **combinación con nombre** de tools que ya están, más el
prompt que dice cuándo y cómo encadenarlas. El molde `Skill` ya soporta justo eso
(agrupa `tool_names` + `prompt_fragment`); lo que falta es la **fábrica** que lo
llene sola a partir de la experiencia.

### 6.2 Estado real

- **Base — YA EXISTE.** El framework de skills (`skills.py`, con su dict `SKILLS`,
  `classify`, y los tests de disjunción/completitud en `tests/test_skills.py`) es el
  "molde" donde una skill compuesta encajaría sin inventar nada nuevo. La
  **introspección** (`app/introspection/`) le da a Jarvis la capacidad de razonar
  sobre su propia estructura, y `jarvis_reflect` (`app/tools/reflect.py`) ya es un
  registro append-only de "cosas aprendidas" con tipo y contexto — el lugar natural
  donde anotar "este patrón de tools se repite".
- **Forma temprana — YA EXISTE (en un dominio).** El bucle auto-mejorante de
  detección (`lab/DETECCION-ESTRES-NOCTURNO.md` §3) ya hace una versión acotada de
  esto: **destila reglas YARA nuevas a partir de la experiencia** de los pases
  nocturnos y las propone para aprobación. Es "aprender una capacidad nueva desde lo
  observado" — pero solo para reglas de detección, no para skills compuestas en
  general.
- **Auto-composición proactiva de skills — FALTA.** No existe todavía el componente
  que *detecte el patrón de tools repetido y proponga la skill nueva por su cuenta*.

### 6.3 El flujo propuesto (con el gate en el centro)

1. **Observar / registrar.** Jarvis lleva registro de las **secuencias de tools** que
   ejecuta al resolver tareas (el audit log ya guarda cada ejecución; `jarvis_reflect`
   ya guarda aprendizajes). Un analizador identifica **cadenas que se repiten** por
   encima de un umbral.
2. **Proponer.** Ante un patrón recurrente, Jarvis **redacta una propuesta de skill
   nueva**: nombre, qué tools encadena y en qué orden, `trigger_keywords` sugeridas
   (cuándo aplicarla), y el `prompt_fragment` que la gobierna. **Solo propone; no la
   activa.**
3. **Aprobar (GATE OBLIGATORIO).** Damian **revisa y aprueba** la propuesta. Sin su
   visto bueno explícito, la skill **no se incorpora ni se ejecuta**. Mismo espíritu y
   mismo mecanismo que el resto del repo: un `proposal_id` de un solo uso (como en
   `selfrepair/`), atado a *esa* propuesta concreta.
4. **Incorporar.** Recién con la aprobación, la skill compuesta se suma a `SKILLS` y
   queda disponible como cualquier otra: `classify()` la puede activar, sus tools se
   ofrecen al modelo, y a partir de ahí es reutilizable.

### 6.4 Freno de seguridad — por qué el gate no es opcional acá

**Una skill auto-creada que después se ejecuta sola es un arma cargada.** Las tools
que encadenaría no son inocuas: `shell_exec` corre comandos reales, `desktop_*`
maneja el mouse y el teclado, las tools de red tocan otras máquinas. Dejar que Jarvis
**fabrique** una combinación de esas capacidades **y** la **ejecute** sin revisión
humana es combinar dos poderes que, por separado, ya están detrás de gates — y hacerlo
justo en el punto donde un error de razonamiento del modelo (o una instrucción
envenenada que se cuele en el patrón observado) quedaría **congelado en una habilidad
permanente y reutilizable**, disparándose después sola.

Por eso el freno es **no negociable y explícito**: **ninguna auto-fabricación de skill
se ejecuta sin el visto bueno de Damian.** Se ata al mismo patrón de gates que ya rige
el repo — aprobación tipo `proposal_id` / `preview_token`, de un solo uso, atada a la
propuesta concreta. Jarvis puede *proponer* todo lo que quiera (eso es barato y
reversible); *activar* una skill compuesta requiere una confirmación humana, igual que
aplicar un fix a su propio código o mandar el submit de un formulario. La fábrica de
habilidades es poderosa **precisamente porque** tiene el freno puesto.

### 6.5 Encuadre honesto

A diferencia de Raphael —cuya fusión es **instantánea, perfecta, y hace emerger
poderes nuevos de la nada**—, acá la habilidad nueva es una **combinación inteligente
de piezas que ya existen**. No emerge un poder que Jarvis no tenía: se **empaqueta con
nombre** un encadenamiento de tools que ya sabía hacer, para no tener que redescubrirlo
cada vez. El valor es real —eficiencia, consistencia, memoria de procedimiento— pero es
**recombinación, no alquimia**. Prometer "poderes emergentes" sería vender la fantasía;
lo que se construye es un sistema que **aprende sus propias rutinas y las guarda, con
Damian firmando cada una**.

---

## 7. Cierre

El Gran Sabio no era poderoso por ser mágico; era valioso porque **percibía,
recordaba, avisaba, simulaba y actuaba como una extensión de Rimuru en la que se
podía confiar**. Todo eso, menos la magia, es ingeniería — y buena parte ya está en
este repo. La distancia entre lo que Jarvis es hoy (Etapa 0, real) y "el Raphael
real" (Etapas 1–6) no es un salto de fe: es una **secuencia de fases ya escritas**
en `lab/`, ordenadas por riesgo, cada una con su criterio de "listo" y sin
debilitar un solo gate. Se llega caminando.
