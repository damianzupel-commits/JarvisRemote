# DETECCION-ESTRES-NOCTURNO.md — Prueba defensiva de estrés de detección de Jarvis

> **Documento de diseño (no ejecutable).** Plan listo para correr, **no** una
> corrida en vivo. Describe cómo poner a prueba —de forma 100% defensiva y
> contenida— el módulo de detección de Jarvis (`backend/app/malware/`) mediante
> **emulación de adversarios** (Atomic Red Team + MITRE Caldera), EICAR y reglas
> YARA propias, corriendo desatendido "toda la noche" con un bucle adaptativo por
> técnica y un bucle externo de convergencia por pases.
>
> Creado: 2026-08-17. Complementa a `lab/CYBER-RANGE-DESIGN.md` (la topología del
> range, los blancos y la convención de snapshots): este documento **reusa** esa
> red aislada y esos snapshots, no los redefine.

---

## ⚠️ Nota de prerrequisitos — LEER PRIMERO

**Esto todavía NO se puede ejecutar.** Requiere que estén instaladas y armadas
primero varias piezas que **hoy no existen** en la máquina:

1. **El cyber range de `lab/CYBER-RANGE-DESIGN.md`** montado: red aislada
   `10.13.37.0/24`, VMware Workstation sobre WHP, VM Kali y al menos un blanco
   Windows con snapshots BASE. Sin el range no hay dónde detonar las técnicas de
   forma contenida.
2. **Atomic Red Team** (`redcanaryco/atomic-red-team` + el módulo PowerShell
   `Invoke-AtomicRedTeam`) instalado **dentro de la VM blanco**, no en el host.
3. **MITRE Caldera v5** (servidor + agente Sandcat) instalado, para las
   operaciones multi-paso que Atomic no cubre bien (C2, movimiento lateral
   encadenado).
4. **El módulo de detección de Jarvis operativo** con al menos ClamAV (clamd)
   corriendo y, opcionalmente, Sysmon instalado (`SYSMON_ENABLED=true`) para la
   capa experimental de auto-protección.

Mientras esas piezas no estén, este documento es **el plano de la corrida**, no
la corrida. La sección §9 (checklist) es la lista de puesta en marcha.

**Nada de esto genera ni despliega malware real.** La emulación de adversarios
reproduce *técnicas* (comandos, patrones, artefactos) de forma segura y con
rutina de limpieza; EICAR es el archivo de prueba estándar de la industria
antivirus (inofensivo); las reglas YARA son firmas propias. El objetivo es
**medir si la detección de Jarvis aguanta**, no atacar a nadie.

---

## 1. Alcance y encuadre defensivo + reglas de aislamiento

### 1.1 Qué es y qué no es

- **Es** una prueba de estrés **defensiva**: se emulan técnicas ofensivas *contra
  un blanco de laboratorio* para observar si el centinela de malware de Jarvis
  (YARA + ClamAV + heurística conductual + FIM + monitor de proceso + Sysmon
  experimental) las **detecta**, con qué señal, en cuánto tiempo, y qué se le
  escapa.
- **No es** una campaña ofensiva ni pentesting contra terceros. No hay blancos
  externos, no hay malware real, no hay exfiltración de datos reales.

### 1.2 Reglas de aislamiento (breves, no negociables)

Heredadas de `CYBER-RANGE-DESIGN.md`, aplican igual acá:

1. **Todo ocurre dentro del range `10.13.37.0/24`**, red host-only / LAN segment
   **sin salida a internet ni ruta a la LAN doméstica ni a la subred de WSL2**.
   La "exfiltración" y el "C2" de las técnicas apuntan a IPs del propio range
   (un colector Caldera en `10.13.37.10`), nunca afuera.
2. **Snapshot BASE antes de cada round y reset después** (§8). Todo blanco vuelve
   a `-BASE-limpio` al terminar; los artefactos de emulación se limpian con la
   rutina de cleanup de Atomic + el revert de snapshot.
3. **Sin malware real.** Solo emulación de adversarios (Atomic/Caldera), EICAR y
   YARA. Ningún binario malicioso vivo se descarga ni se ejecuta.
4. **El gate de scope de Jarvis sigue activo.** Cualquier tool de red de Jarvis
   valida el target contra `backend/authorized_targets.yaml`; el range ya está
   ahí (`10.13.37.0/24`, alta 2026-08-17). Esta prueba es de **detección**, no de
   ataque, así que las tools ofensivas de Jarvis casi no se usan —el que "ataca"
   es el agente de emulación dentro del blanco.

### 1.3 Rol de cada actor

| Actor | Rol en esta prueba |
|-------|--------------------|
| **Agente de emulación** (Invoke-AtomicRedTeam / Sandcat de Caldera) | Ejecuta la técnica ATT&CK **dentro del blanco**. Es "el adversario". |
| **Jarvis** (backend en WSL2) | **El defensor.** Observa el blanco con su módulo de detección, puntúa, journaliza a Obsidian y decide repetir/avanzar/converger. |
| **Orquestador nocturno** (script/loop, §3) | Corre desatendido: dispara técnica por técnica, coordina detección, aplica los topes de tiempo, snapshots y el bucle de convergencia. |
| **Damian** | Aprueba (o no) las mejoras de reglas propuestas entre pases; edita a mano lo que Jarvis no puede tocar por diseño. |

---

## 2. Arquitectura

### 2.1 Quién ejecuta la emulación

- **Atomic Red Team** provee **>1700 "atómicas"**: tests chicos, portables y
  reproducibles, cada uno mapeado a una técnica MITRE ATT&CK, organizados en
  carpetas por técnica (`atomics/T1055/` = Process Injection, etc.). Cada test
  corre en ≤5 minutos y trae comandos de setup y **cleanup**. Se ejecutan con el
  módulo PowerShell **`Invoke-AtomicRedTeam`** (`Invoke-AtomicTest T1059.001`).
  Multiplataforma con PowerShell Core; acá corren **dentro de la VM blanco**.
- **MITRE Caldera v5** (v5.3.0, abril 2025) aporta lo que Atomic no hace bien:
  **operaciones multi-paso encadenadas** (una "adversary" = secuencia de
  "abilities", cada ability = una técnica ATT&CK con su comando/executor). Trae el
  agente **Sandcat** (Go, C2 cross-platform), UI VueJS (Magma) y **REST API** para
  automatizar. Integra las ~1400 implementaciones de Atomic. Se usa para C2,
  movimiento lateral y cadenas realistas de varias técnicas seguidas.

**Regla de reparto:** técnica **aislada** → Atomic (una atómica). Técnica que solo
tiene sentido **en cadena** o necesita C2/persistencia real de laboratorio →
operación de Caldera.

### 2.2 Cómo observa/detecta Jarvis

Jarvis **no** instrumenta el ataque: lo **observa como defensor**, exactamente con
las capacidades que ya tiene en `backend/app/malware/`:

- **YARA** (`yara_scanner.py`): compila todos los `.yar`/`.yara` de
  `MALWARE_YARA_RULES_DIR` (default `app/malware/rules/`, hoy `starter.yar`) y
  matchea contra los artefactos que la técnica deja en disco.
- **ClamAV** (`clamav_scanner.py`, vía clamd): firmas conocidas; opcional (si no
  está, se reporta `clamav_available=false`, distinto de "limpio").
- **Heurística conductual + on-access** (`behavioral_watcher.py`): watchdog sobre
  Descargas/Escritorio/Temp; escaneo on-access de cada archivo nuevo/modificado +
  detector de patrón de ransomware (≥15 archivos en 15 s con entropía media ≥7.5
  bits/byte).
- **FIM** (`integrity.py`): baseline de archivos críticos; detecta modificado/
  borrado/nuevo. Ideal para técnicas de persistencia que tocan archivos vigilados.
- **Monitor de proceso** (`process_monitor.py`): hijos inesperados del backend,
  conexiones salientes raras.
- **Sysmon experimental** (`sysmon_monitor.py`): ProcessAccess/CreateRemoteThread
  contra el PID del backend. **Siempre** marcado experimental.
- **VirtualTotal** (`virustotal_client.py`): solo **posterior** a un hit local,
  nunca sobre archivos limpios.

Todo hallazgo real cae con rigor forense: SHA-256 content-addressed + log firmado
Ed25519 (`store.py`), y cuarentena reversible (mover, no borrar).

### 2.3 Cómo se conectan (diagrama)

```
        HOST Windows 11  ──►  WSL2  ──►  Jarvis backend (DEFENSOR)
        │                                  │  tools: malware_scan_path,
        │                                  │  malware_full_scan_run,
        │                                  │  malware_check_integrity,
        │                                  │  malware_check_process,
        │                                  │  malware_check_sysmon_experimental,
        │                                  │  malware_list_findings,
        │                                  │  obsidian_save_note / _search_notes
        │                                  ▼
        │            ORQUESTADOR NOCTURNO (loop desatendido, §3)
        │            dispara técnica → pide detección → journaliza → decide
        │                                  │
   ┌────┴──────────────────────────────────┼───────────────────────────┐
   │        RANGE AISLADO 10.13.37.0/24 (sin internet)                  │
   │                                        │                           │
   │   ┌──────────────────┐        detona   ▼                          │
   │   │ Colector Caldera │◄─ C2 ─┐   ┌──────────────────────────────┐  │
   │   │  10.13.37.10     │       └───│  VM BLANCO  10.13.37.40       │  │
   │   │  (dentro del range)│         │  - Invoke-AtomicRedTeam       │  │
   │   └──────────────────┘          │  - agente Sandcat (Caldera)   │  │
   │                                 │  - Jarvis observa este disco  │  │
   │                                 │    (share/mount de solo lectura│  │
   │                                 │     + carpetas vigiladas)      │  │
   │                                 │  snapshots BASE/PRE/POST       │  │
   │                                 └──────────────────────────────┘  │
   └────────────────────────────────────────────────────────────────────┘
```

**Cómo Jarvis "ve" el disco del blanco:** dos variantes, análogas a §6.1 del
range design:

1. **Recomendada — Jarvis orquesta un agente detector en el blanco:** el módulo de
   malware de Jarvis corre (o se le apunta) sobre las carpetas del blanco vía un
   share de solo lectura o un `malware_scan_path` remoto ejecutado por un pequeño
   colector en el blanco que devuelve los artefactos a escanear. Mantiene al
   defensor observando *desde afuera* del ataque.
2. **Alternativa — instancia de Jarvis dentro del blanco:** una copia del backend
   corre en la VM blanco con las carpetas de riesgo apuntando a donde Atomic deja
   sus artefactos. Más simple de cablear, menos "realista" (el defensor comparte
   host con el atacante). Aceptable en laboratorio.

En ambas, **el análisis de comportamiento de proceso/Sysmon** solo es fiel si
Jarvis corre *en* el blanco (variante 2) o si se le exportan los eventos; la
detección **por artefacto en disco** (YARA/ClamAV/on-access/FIM) funciona en las
dos.

---

## 3. El bucle adaptativo en detalle

Hay **dos bucles anidados**:

- **Bucle interno (por técnica):** detona UNA técnica, detecta, puntúa,
  journaliza, y decide **repetir la técnica** (variando parámetros) o **avanzar**
  a la siguiente. Criterio de "ya aprendí lo suficiente" bien definido (§3.2).
- **Bucle externo (de convergencia por pases):** un "pase" es recorrer **todo el
  arsenal** (todas las técnicas + EICAR/YARA). Al terminar un pase, si hubo
  **gaps de detección**, Jarvis los registra, **propone mejoras** y corre **otro
  pase completo**. Repite **hasta converger** (§3.4).

### 3.1 Diagrama de estados (bucle interno, por técnica)

```
        ┌─────────────────┐
        │  SNAPSHOT PRE    │  (revert a BASE + PRE-<tecnica>, §8)
        └────────┬─────────┘
                 ▼
        ┌─────────────────┐
        │ EJECUTAR TECNICA│  Invoke-AtomicTest Txxxx  /  op. Caldera
        │  (variante k)   │
        └────────┬─────────┘
                 ▼
        ┌─────────────────┐
        │    DETECTAR     │  Jarvis: malware_scan_path / full_scan /
        │  (ventana T_det)│  check_integrity / check_process / sysmon
        └────────┬─────────┘
                 ▼
        ┌─────────────────┐
        │    PUNTUAR      │  ¿detectó? señal, t_deteccion, FN, severidad
        └────────┬─────────┘
                 ▼
        ┌─────────────────┐
        │  JOURNAL Obsidian│ obsidian_save_note (nota por técnica, versión=pase)
        └────────┬─────────┘
                 ▼
        ┌─────────────────┐        SI ("puedo sacar más")
        │  ¿SUFICIENTE?   │───────────────────────────────┐
        └────────┬─────────┘                              │
                 │ NO (aprendí lo suficiente)             ▼
                 │                              ┌────────────────────┐
                 │                              │ SIGUIENTE VARIANTE │
                 │                              │ (params/ofusca/vec)│
                 │                              └─────────┬──────────┘
                 │                                        │ (revert PRE)
                 │                                        ▼
                 │                                 (vuelve a EJECUTAR)
                 ▼
        ┌─────────────────┐
        │ RESET al BASE + │
        │ SIGUIENTE TECNICA│
        └─────────────────┘
```

### 3.2 Criterio de "ya aprendí lo suficiente" (bucle interno)

Una técnica se da por **agotada** (se pasa a la siguiente) cuando se cumple
**cualquiera** de estas condiciones —el primero que se cumpla corta:

1. **Detección estable:** la técnica se detectó con la **misma señal** en
   `N_ESTABLE = 3` variantes/repeticiones **seguidas**. Ya sabemos que se detecta
   de forma robusta; insistir no aporta.
2. **Cobertura de variantes agotada:** se probaron **todas** las variantes
   planificadas para esa técnica (lista fija por técnica: p. ej. limpia,
   ofuscada, codificada base64, con `-WindowStyle Hidden`, vector alternativo) y
   no queda ninguna sin probar.
3. **Techo de intentos por técnica:** se alcanzó `MAX_INTENTOS_TECNICA = 6`
   detonaciones, se haya estabilizado o no. Evita ciclos infinitos sobre una
   técnica difícil.
4. **Techo de tiempo por técnica:** se superó `MAX_MIN_TECNICA = 20` minutos de
   reloj en esa técnica (suma de detonaciones + detección). Corta sí o sí.

La decisión de **repetir** (en vez de avanzar) requiere que **ninguna** de las 4
se cumpla **y** que Jarvis estime que hay más para aprender, operacionalizado como:

> **Repetir si**: (a) la última variante **no se detectó** (falso negativo →
> vale la pena probar si otra variante tampoco, o si la anterior sí), **o**
> (b) se detectó pero **quedan variantes sin probar** que ejercitan una señal
> **distinta** (p. ej. ya probé la firma YARA, falta ver si el detector de
> comportamiento la agarra), **o** (c) el tiempo de detección fue **anómalamente
> alto** y conviene confirmar si es estable.

Si nada de eso aplica → **avanzar**.

### 3.3 Pseudocódigo del bucle interno

```python
# --- Bucle interno: una técnica ---
def correr_tecnica(tecnica, pase_n, presupuesto_global):
    variantes = tecnica.variantes  # [limpia, ofuscada, b64, hidden, vector_alt, ...]
    detecciones_seguidas = 0
    ultima_senal = None
    intentos = 0
    t0 = ahora()
    resultados = []

    while True:
        # --- topes de corte (criterio de "suficiente", §3.2) ---
        if intentos >= MAX_INTENTOS_TECNICA:            razon = "techo_intentos"; break
        if minutos(ahora() - t0) >= MAX_MIN_TECNICA:    razon = "techo_tiempo";   break
        if not variantes:                                razon = "variantes_agotadas"; break
        if detecciones_seguidas >= N_ESTABLE:            razon = "deteccion_estable"; break
        if presupuesto_global.agotado():                 razon = "tope_global"; break

        variante = variantes.pop(0)

        snapshot_revert(tecnica.blanco, f"{tecnica.blanco}-PRE-{tecnica.id}")  # §8
        detonar(variante)                    # Invoke-AtomicTest / op. Caldera
        r = jarvis_detectar(tecnica, variante)   # §2.2 (ventana T_det con timeout)
        r.pase = pase_n
        resultados.append(r)
        intentos += 1

        # --- puntuar ---
        if r.detectado and r.senal == ultima_senal:
            detecciones_seguidas += 1
        elif r.detectado:
            detecciones_seguidas = 1; ultima_senal = r.senal
        else:
            detecciones_seguidas = 0     # falso negativo: reinicia la racha

        # --- decisión adaptativa: ¿repetir o avanzar? ---
        # (implícita: el while sigue si no se cumplió ningún corte y quedan variantes)

    # journaliza la nota por técnica de ESTE pase (§4), con todas las variantes
    journal_tecnica(tecnica, resultados, razon_corte=razon, pase_n=pase_n)
    cleanup_atomic(tecnica)               # rutina de limpieza de Atomic
    snapshot_revert(tecnica.blanco, f"{tecnica.blanco}-BASE-limpio")   # reset

    gap = evaluar_gap(resultados)         # ¿hubo FN / detección mala? -> gap
    return ResultadoTecnica(tecnica, resultados, razon, gap)
```

### 3.4 Bucle externo de convergencia (por pases)

Un **pase** = recorrer todo el arsenal (§5) una vez, corriendo `correr_tecnica`
para cada técnica + el sub-test EICAR/YARA. Al final de cada pase Jarvis mira los
**gaps** (técnicas no detectadas o mal detectadas) y decide si converge o hace
otro pase.

**Convergencia:** el proceso converge cuando un pase entero arroja **CERO gaps
nuevos**, o cuando las mejoras aplicadas **dejan de reducir** el número de gaps
(*plateau*: dos pases seguidos con la misma cantidad de gaps abiertos).

**Clave anti-ciclo-inútil:** entre pase y pase **debe** aplicarse (o al menos
**proponerse para aprobación de Damian**) al menos **una mejora de detección**.
Correr el mismo pase sin cambiar nada encontraría siempre los mismos gaps. Si en
un pase no se generó ninguna mejora aplicable, el bucle externo **no repite**:
para y reporta (no tiene sentido otro pase idéntico).

**¿Auto-aplicar o gate de aprobación?** — decisión explícita, alineada con los
gates ya existentes del proyecto (`selfrepair/` Opción C, patrón dry-run→confirm):

- **Reglas YARA nuevas o modificadas** → **NO se auto-aplican al vuelo sin
  registro.** Jarvis las **genera y las deja como propuesta** (archivo
  `app/malware/rules/generadas/<pase>-<tecnica>.yar.propuesta` + entrada en la
  nota de Obsidian). Para el bucle nocturno hay **dos modos configurables**:
  - **Modo asistido (default, recomendado):** las reglas propuestas quedan
    **pendientes de aprobación de Damian**. El bucle externo puede seguir usando
    una **copia de trabajo** de las reglas dentro del range (aislado) para medir
    si la mejora cierra el gap, pero **no** toca el `MALWARE_YARA_RULES_DIR` de
    producción hasta que Damian confirma. Así corre toda la noche sin gate y por
    la mañana Damian revisa/aprueba lo que valió.
  - **Modo autónomo-en-range:** solo dentro del range aislado, el bucle **sí**
    recompila YARA con las reglas nuevas (`compile_rules(force=True)`) para poder
    medir la convergencia real pase a pase. Nunca escribe fuera del range.
- **Ajustes de umbral conductual** (p. ej. bajar `_RANSOMWARE_MIN_EVENTS`,
  `_RANSOMWARE_MIN_AVG_ENTROPY`) → **siempre propuesta**, nunca auto-aplicados a
  producción; requieren revisión de Damian porque afectan la tasa de falsos
  positivos en el uso real.
- **Regla de oro:** nada de lo que Jarvis auto-aplique sale del range. Lo que
  toca producción pasa por Damian. El log firmado (`store.py`) registra cada
  cambio de reglas propuesto/aplicado.

### 3.5 Pseudocódigo del bucle externo

```python
def noche_de_estres():
    presupuesto = PresupuestoGlobal(
        deadline = ahora() + MAX_HORAS_NOCHE,     # tope de tiempo global
        max_pases = MAX_PASES,                    # tope de pases completos
    )
    arsenal = cargar_arsenal()          # §5: técnicas ATT&CK + EICAR/YARA
    gaps_previos = None
    log_maestro = LogMaestro("session-<fecha>")

    for pase_n in range(1, presupuesto.max_pases + 1):
        if presupuesto.vencido(): break

        snapshot_pase(arsenal.blancos, f"PASE{pase_n}")   # §8, reset entre pases
        gaps_pase = []

        for tecnica in arsenal.tecnicas:                  # un pase = todo el arsenal
            if presupuesto.vencido(): break
            rt = correr_tecnica(tecnica, pase_n, presupuesto)   # §3.3
            log_maestro.registrar(rt)
            if rt.gap:
                gaps_pase.append(rt.gap)

        # --- sub-test antivirus EICAR + YARA propias (§5.5) ---
        gaps_pase += correr_subtest_av(pase_n, log_maestro)

        # --- ¿converge? ---
        if len(gaps_pase) == 0:
            log_maestro.convergio(pase_n, razon="cero_gaps")
            break
        if gaps_previos is not None and len(gaps_pase) >= len(gaps_previos):
            log_maestro.convergio(pase_n, razon="plateau")   # mejoras dejaron de reducir
            break

        # --- generar mejoras ANTES del próximo pase (anti-ciclo-inútil) ---
        mejoras = jarvis_proponer_mejoras(gaps_pase)   # nuevas YARA, umbrales, señales
        if not mejoras:
            log_maestro.parar(pase_n, razon="sin_mejoras_posibles")
            break
        aplicar_o_proponer(mejoras)     # §3.4: modo asistido vs autónomo-en-range
        journal_mejoras(mejoras, pase_n)
        gaps_previos = gaps_pase

    else:
        # se agotaron los pases sin converger
        log_maestro.parar(pase_n, razon="tope_pases_sin_converger")

    journal_convergencia(log_maestro)   # nota-resumen de convergencia (§4.3)
```

### 3.6 Corrida desatendida "toda la noche"

- **Topes de tiempo:** `MAX_HORAS_NOCHE` (global, p. ej. 8 h), `MAX_MIN_TECNICA`
  (20 min/técnica), y `MAX_PASES` (p. ej. 5 pases completos). El primero que se
  agote corta con gracia.
- **Log maestro de la sesión:** un JSONL append-only + una nota-índice de
  Obsidian, actualizado tras cada técnica y cada pase. Si el proceso muere, el log
  permite retomar/entender dónde quedó.
- **Sin intervención humana durante la noche:** las únicas decisiones que
  requieren a Damian (aprobar reglas para producción) quedan **encoladas como
  propuestas** para la mañana; el bucle no se bloquea esperándolas (modo asistido
  usa copia de trabajo en el range).

---

## 4. Formato de las notas de aprendizaje en Obsidian

Jarvis escribe con la tool **`obsidian_save_note`** (autor fijo `jarvis`, ver
`app/tools/obsidian.py`). Las notas son `.md` reales con frontmatter YAML en
`backend/obsidian_vault/jarvis/`. Se usan `tags`, `category` y `[[wikilinks]]`
(buscando antes con `obsidian_search_notes` para no aislar la nota).

### 4.1 Plantilla — nota por técnica (versionada por pase)

**Una nota por (técnica × pase).** El título incluye el pase para poder ver la
evolución: una técnica que falla en el pase 1 y se detecta en el pase 3 tras la
mejora queda como tres notas enlazadas entre sí.

Título sugerido: `Deteccion T1059.001 PowerShell — pase 1`

```markdown
---
title: "Deteccion T1059.001 PowerShell — pase 1"
author: jarvis
category: deteccion-estres
tags: [deteccion-estres, attack, T1059.001, ejecucion, pase-1]
created: 2026-08-17T02:14:05Z
updated: 2026-08-17T02:19:40Z
attack_tactic: "Execution (TA0002)"
attack_technique: "T1059.001 — Command and Scripting Interpreter: PowerShell"
emulador: "Atomic Red Team / Invoke-AtomicTest T1059.001"
pase: 1
resultado: parcial          # detectado | no-detectado | parcial
tiempo_deteccion_s: 8.4     # null si no-detectado
falsos_negativos: 1
severidad_maxima: high
snapshot_pre: "win7smb-PRE-T1059.001-20260817"
snapshot_post: "win7smb-POST-T1059.001-20260817"
---

## Qué se probó
Ejecución de PowerShell (T1059.001), 4 variantes: limpia, `-EncodedCommand`,
`IEX(New-Object Net.WebClient).DownloadString(...)` ofuscada, y `-WindowStyle
Hidden -NoProfile`. Blanco: win7smb (10.13.37.40). Emulador: Invoke-AtomicTest.

## Resultado por variante
| # | Variante | ¿Detectado? | Señal | t_det (s) |
|---|----------|-------------|-------|-----------|
| 1 | limpia | no | — | — |
| 2 | -EncodedCommand | sí | YARA `Suspicious_PowerShell_Obfuscation` | 8.4 |
| 3 | IEX DownloadString | sí | YARA `Suspicious_PowerShell_Obfuscation` (3+ strings) | 7.1 |
| 4 | -WindowStyle Hidden | sí | idem regla | 9.0 |

## Señal de detección
Regla YARA `Suspicious_PowerShell_Obfuscation` (`app/malware/rules/starter.yar`),
condición "3 of them" sobre `-EncodedCommand`/`DownloadString`/`IEX`/`-Hidden`.
Motor: `yara_scanner.py`. Finding registrado en el log firmado (`store.py`).

## Falso negativo / gap
La variante **limpia** (un `Get-Process` benigno con `-NoProfile`) no matcheó —
correcto que no sea "malware", pero un one-liner de descarga **sin** las 3 strings
mínimas se escaparía. **Gap:** la regla exige 3 strings; un dropper minimalista
(solo `IEX` + una URL) pasa por debajo del umbral.

## Mejora propuesta (para el próximo pase)
Nueva regla `PowerShell_Download_Cradle_Min`: matchear `IEX`/`Invoke-Expression`
+ patrón de URL (`http`/`https`) con condición "2 of them", severity high. Deja
como propuesta en `rules/generadas/pase2-T1059.001.yar.propuesta`.

## Enlaces
[[Deteccion T1059.001 PowerShell — pase 2]] · [[Indice sesion estres 2026-08-17]] ·
[[como-jarvis-audita-seguridad-de-codigo]]
```

### 4.2 Campos obligatorios del frontmatter

`attack_tactic`, `attack_technique`, `emulador`, `pase`, `resultado`,
`tiempo_deteccion_s`, `falsos_negativos`, `severidad_maxima`, `snapshot_pre/post`.
Esto permite consolidar métricas (§7) parseando el frontmatter de todas las notas
`tag: deteccion-estres`.

### 4.3 Plantilla — nota-índice / resumen de convergencia

Una sola nota por sesión, actualizada al final: `Indice sesion estres 2026-08-17`.

```markdown
---
title: "Indice sesion estres 2026-08-17"
author: jarvis
category: deteccion-estres
tags: [deteccion-estres, indice, convergencia]
created: 2026-08-17T01:55:00Z
updated: 2026-08-17T06:40:00Z
pases_totales: 3
convergio: true
razon_corte: cero_gaps        # cero_gaps | plateau | tope_pases | tope_tiempo | sin_mejoras
cobertura_attack_final: "9/9 tácticas · 24/27 técnicas detectadas"
reglas_yara_generadas: 4
gaps_abiertos_al_final: 1
---

## Resumen de la noche
Emulación defensiva desatendida, range 10.13.37.0/24, 8 h de tope. 3 pases
completos hasta converger (cero gaps nuevos en el pase 3).

## Gaps cerrados por pase
| Pase | Gaps al inicio | Mejoras aplicadas | Gaps al cierre |
|------|----------------|-------------------|----------------|
| 1 | 7 | 3 reglas YARA + 1 umbral | 7 → base |
| 2 | 4 | 1 regla YARA nueva | 4 |
| 3 | 1 | — (verificación) | 1 (aceptado) |

## Cobertura ATT&CK final
Execution ✅ · Persistence ✅ · Defense Evasion ⚠️ (1 gap) · Credential Access ✅ ·
Discovery ✅ · Lateral Movement ✅ · Exfiltration ✅ · C2 ✅ · Impact ✅.

## Reglas nuevas generadas (propuestas para Damian)
- `PowerShell_Download_Cradle_Min` (T1059.001) — pase 2.
- `Registry_Run_Persistence_Write` (T1547.001) — pase 2.
- `LSASS_Access_Heuristic` (T1003.001) — pase 2, **necesita Sysmon**.
- `Suspicious_Rundll32_Proxy` (T1218.011) — pase 3.
Ubicación: `app/malware/rules/generadas/*.propuesta`. **Pendientes de aprobación.**

## Qué quedó sin resolver
- **Defense Evasion T1055 (Process Injection):** detección solo por artefacto en
  disco; sin Sysmon+correlación de kernel no se ve la inyección en memoria.
  Registrado como límite conocido (coincide con el docstring de
  `behavioral_watcher.py`). Requiere decisión de Damian sobre Sysmon.

## Enlaces
[[Deteccion T1059.001 PowerShell — pase 1]] · [[Deteccion T1003.001 LSASS — pase 2]] · ...
```

---

## 5. Cobertura ATT&CK — de simple a complejo

Recorrido por las **9 tácticas** pedidas, de menos a más difícil de detectar.
Cada fila: qué técnica, con qué emulador, y **qué prueba de la detección de
Jarvis**. Se arranca por lo que la detección por artefacto en disco agarra bien
(EICAR, droppers con strings) y se escala hacia lo que exige comportamiento/kernel
(inyección, C2 sobre 443), que es donde se esperan los gaps honestos.

### 5.1 Ejecución (TA0002) y evasión inicial — las más fáciles de detectar

| Técnica | Emulador | Qué prueba de Jarvis |
|---------|----------|----------------------|
| **T1059.001** PowerShell | Atomic | Regla YARA `Suspicious_PowerShell_Obfuscation` (ya existe). Umbral "3 of them". |
| **T1059.003** cmd/bat | Atomic | Escaneo on-access de scripts nuevos en carpetas vigiladas. |
| **T1204** ejecución por usuario (archivo señuelo) | Atomic | on-access + YARA sobre el artefacto entregado. |

### 5.2 Persistencia (TA0003)

| Técnica | Emulador | Qué prueba |
|---------|----------|-----------|
| **T1547.001** Run/RunOnce del Registro | Atomic | YARA `Suspicious_Persistence_Registry_Run_Key` + **FIM** si toca un archivo vigilado. |
| **T1053.005** Scheduled Task | Atomic | Monitor de proceso (hijo/tarea inesperada) + artefacto en disco. |
| **T1543.003** servicio nuevo | Atomic | FIM/monitor de proceso; prueba si Jarvis nota el binario del servicio. |

### 5.3 Evasión de defensas (TA0005) y acceso a credenciales (TA0006) — más duras

| Técnica | Emulador | Qué prueba |
|---------|----------|-----------|
| **T1055** Process Injection | Atomic/Caldera | **Gap esperado:** sin Sysmon, solo se ve el artefacto en disco, no la inyección en memoria (ver límite de `behavioral_watcher.py`). Ejercita la capa Sysmon experimental. |
| **T1218.011** rundll32 proxy exec | Atomic | Monitor de proceso (hijo inusual) + YARA sobre payload. |
| **T1003.001** dump de LSASS | Atomic/Caldera | `malware_check_process` + Sysmon (ProcessAccess al LSASS). Prueba la correlación de acceso a memoria. |
| **T1552** credenciales en archivos / browser | Atomic | YARA `Browser_Credential_Store_Access` (ya existe, matchea rutas de Login Data). |

### 5.4 Descubrimiento, movimiento lateral, exfiltración, C2, impacto

| Táctica / Técnica | Emulador | Qué prueba |
|-------------------|----------|-----------|
| **Discovery** T1082/T1057/T1018 (sistema/proceso/red) | Atomic | Comportamiento de enumeración; prueba si el monitor nota barridos anómalos. Muchos son de bajo ruido → gap probable (esperado). |
| **Lateral Movement** T1021 (SMB/RDP/WinRM) | Caldera (op. encadenada) | Monitor de conexiones salientes/entrantes inusuales entre blancos del range. |
| **Exfiltration** T1041 (exfil sobre C2) / T1048 | Caldera → colector `10.13.37.10` | Monitor de proceso (conexión saliente rara). "Exfil" apunta **dentro del range**, nunca afuera. |
| **C2** T1071 (HTTP/HTTPS) / T1573 (canal cifrado) | Caldera Sandcat | **Gap esperado:** C2 sobre HTTPS 443 es difícil de distinguir de tráfico legítimo (límite documentado en `process_monitor.py`). Ejercita ese límite honestamente. |
| **Impact** T1486 (cifrado tipo ransomware) | **Emulación segura** (cifra archivos señuelo en carpeta vigilada, con cleanup) | **La estrella del test conductual:** dispara la heurística de ransomware de `behavioral_watcher.py` (≥15 archivos en 15 s, entropía ≥7.5). Mide t_detección del patrón. |

> **Nota de seguridad sobre T1486:** se usa una atómica que cifra **archivos
> señuelo** creados a propósito en una carpeta vigilada del blanco (con rutina de
> cleanup + revert de snapshot), **no** datos reales y **no** ransomware real. Es
> exactamente el caso de uso para el que se diseñó el detector de patrón.

### 5.5 Sub-test de antivirus — EICAR + firmas YARA propias

Prueba de sanidad de punta a punta del motor de detección, en cada pase:

1. **EICAR:** se deja caer el archivo de prueba estándar EICAR
   (`X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*`) en una
   carpeta vigilada. **Debe** matchear la regla `EICAR_Test_File` de
   `starter.yar` (severity info) vía on-access, y confirmar que el pipeline
   completo (scan → finding → log firmado → cuarentena reversible) funciona.
   Si **no** detecta EICAR, es un gap **crítico de infraestructura**, no de
   cobertura (algo del motor está roto).
2. **Firmas YARA propias:** se generan archivos de prueba que matcheen cada regla
   de `starter.yar` (`Possible_Ransom_Note`, `Suspicious_PHP_Webshell`,
   `Browser_Credential_Store_Access`, etc.) para confirmar que **cada regla
   dispara** y ninguna quedó rota tras un cambio. Es el "test unitario" de las
   reglas, corrido dentro del bucle.
3. **Reglas generadas en pases previos:** cada regla nueva que Jarvis propuso en
   un pase anterior se valida acá (¿matchea lo que debía sin romper las
   existentes?) antes de contarla como "gap cerrado".

---

## 6. Enganche con las tools y el vault reales de Jarvis

Nombres y rutas reales del repo (no inventar):

**Detección (defensor) — `app/tools/malware.py`:**

- `malware_scan_path(path, use_virustotal)` — escanea archivo/carpeta con YARA +
  ClamAV; cuarentena automática si hay hit. **Tool principal** de la ventana de
  detección tras cada técnica.
- `malware_full_scan_run()` / `malware_full_scan_status()` — escaneo completo de
  `FS_ALLOWED_ROOT` (en el range, apuntar a las carpetas del blanco).
- `malware_check_integrity()` — FIM, para técnicas de persistencia.
- `malware_check_process()` — hijos/conexiones inesperadas, para inyección/C2/LM.
- `malware_check_sysmon_experimental(lookback_minutes)` — ProcessAccess/
  CreateRemoteThread; **requiere Sysmon + `SYSMON_ENABLED=true`**. Presentar
  siempre como experimental.
- `malware_list_findings(status)` — consolidar hallazgos del pase.
- `malware_verify_log()` — confirmar que el log firmado no fue tocado.

**Motores subyacentes — `app/malware/`:** `engine.scan_and_handle` (pipeline
YARA+ClamAV+cuarentena), `yara_scanner.compile_rules(force=True)` (recompilar tras
agregar reglas), `behavioral_watcher` (on-access + patrón ransomware),
`store.py` (SHA-256 + log firmado Ed25519), `quarantine.py` (mover, no borrar).

**Reglas YARA:** viven en `MALWARE_YARA_RULES_DIR` (default
`backend/app/malware/rules/`, hoy `starter.yar`). Las reglas **generadas** por el
bucle se dejan en `backend/app/malware/rules/generadas/*.propuesta` (fuera del set
que compila producción hasta aprobación). En modo autónomo-en-range se copian a
una carpeta de trabajo del range y se hace `compile_rules(force=True)`.

**Journaling (vault) — `app/tools/obsidian.py`:**

- `obsidian_save_note(title, content, tags, category)` — **autor fijo `jarvis`**;
  cada nota por técnica/pase y la nota-índice se escriben con esta tool.
- `obsidian_search_notes(query, author, limit)` — buscar notas relacionadas antes
  de escribir para poner `[[wikilinks]]` correctos (evita notas aisladas).
- `obsidian_list_notes(author, tag)` — al final, listar todo `tag: deteccion-estres`
  para consolidar métricas.

**Vault real:** `backend/obsidian_vault/jarvis/` (archivos `.md` con frontmatter
YAML, búsqueda semántica por embeddings coseno con umbral 0.4, ver
`app/obsidian/vault.py` / `embeddings.py`). Categoría sugerida: `deteccion-estres`.
Existe además el **perfil de vault de investigación** (`app/obsidian/profile.py`)
si se quisiera aislar estas notas en el vault de investigación en vez del de
seguridad; por default van al vault de seguridad estándar.

**Scope de red:** `10.13.37.0/24` ya autorizado en `authorized_targets.yaml`
(§6.2 del range design). Esta prueba es de detección, así que apenas usa
`nmap_scan`; si lo usa (inventario del blanco), valida contra ese archivo.

---

## 7. Métricas

Se calculan parseando el frontmatter de todas las notas `tag: deteccion-estres`
(via `obsidian_list_notes`) + el log maestro JSONL.

### 7.1 Métricas por técnica y por táctica

- **Tasa de detección:** `# variantes detectadas / # variantes probadas`, por
  técnica y agregada por táctica.
- **Tiempo medio de detección (MTTD):** promedio de `tiempo_deteccion_s` sobre las
  variantes detectadas, por técnica y por táctica.
- **Falsos negativos por táctica:** suma de `falsos_negativos`, agrupada por las 9
  tácticas ATT&CK.
- **Cobertura ATT&CK:** `# técnicas con ≥1 detección / # técnicas probadas`, y
  `# tácticas con ≥1 técnica detectada / 9`.
- **Señal dominante:** qué motor detectó (YARA / ClamAV / conductual / FIM /
  proceso / Sysmon), para ver de qué depende la detección.

### 7.2 Métricas del bucle externo (convergencia)

- **Pases hasta converger** y **razón de corte** (cero_gaps / plateau /
  tope_pases / tope_tiempo / sin_mejoras).
- **Gaps cerrados por pase:** serie `gaps_al_inicio → gaps_al_cierre` por pase
  (la tabla de la nota-resumen §4.3). Muestra si las mejoras realmente reducen
  gaps o si hay plateau.
- **Reglas nuevas generadas** y **cuántas cerraron su gap** (validadas en §5.5).
- **Evolución por técnica:** comparación pase-a-pase de una misma técnica (posible
  porque las notas están versionadas por pase) — p. ej. "T1547.001: no-detectado
  en pase 1 → detectado en pase 2 tras `Registry_Run_Persistence_Write`".
- **Gaps abiertos al final:** los que ninguna mejora cerró (con su motivo, típico:
  requiere Sysmon/kernel).

### 7.3 Consolidación al final de la noche

Todo se vuelca en la **nota-resumen de convergencia** (§4.3) y en un CSV/JSON
derivado del log maestro. El log maestro append-only permite reconstruir la
sesión aunque el proceso se haya cortado por tope de tiempo.

---

## 8. Snapshots y reset entre técnicas / rounds / pases

Reusa la convención de `CYBER-RANGE-DESIGN.md` §7 (BASE sagrado, PRE/POST
desechables, "máx. 3" snapshots vivos por VM). Adaptada a esta prueba:

- **Antes de cada técnica:** revert a `<blanco>-BASE-limpio`, luego snapshot
  `<blanco>-PRE-<Txxxx>-<fecha>` (aísla el efecto de esa técnica).
- **Entre variantes de la misma técnica:** revert al PRE de esa técnica antes de
  cada nueva detonación (cada variante arranca de un estado idéntico → medición
  limpia).
- **Después de cada técnica:** opcional `<blanco>-POST-<Txxxx>` si se quiere
  análisis forense; luego **revert a BASE** + `cleanup_atomic` (rutina de limpieza
  de Atomic Red Team) para no arrastrar artefactos al siguiente test.
- **Entre pases completos:** snapshot de referencia `<blanco>-PASE<n>` al arrancar
  el pase, y **reset total a BASE** de todos los blancos al cerrarlo. Cada pase
  parte de un estado idéntico → la única variable entre pases son **las mejoras de
  detección**, que es exactamente lo que el bucle de convergencia quiere medir.
- **Higiene anti-llenado:** borrar PRE/POST de técnicas ya journalizadas dentro
  del pase; no acumular árboles largos (los blancos Windows inflan snapshots
  rápido, §4.5 del range design). El BASE nunca se toca.

---

## 9. Checklist de puesta en marcha y prerrequisitos

**A. Range (prerrequisito duro — ver `lab/CYBER-RANGE-DESIGN.md`)**
- [ ] Range `10.13.37.0/24` montado, aislado, sin internet.
- [ ] VM blanco (recom. Windows, p. ej. win7smb `.40`) con `-BASE-limpio`.
- [ ] Colector Caldera en `10.13.37.10` (dentro del range) para C2/exfil.
- [ ] `10.13.37.0/24` ya en `backend/authorized_targets.yaml` (a mano).

**B. Frameworks de emulación (hoy NO instalados)**
- [ ] **Atomic Red Team** (`redcanaryco/atomic-red-team`) + módulo PowerShell
      `Invoke-AtomicRedTeam` instalados **en la VM blanco**.
- [ ] **MITRE Caldera v5** (servidor + agente Sandcat) para operaciones
      encadenadas (C2, movimiento lateral).
- [ ] Verificar que las atómicas traen su rutina de **cleanup** y probar una
      inofensiva (T1059.001) con revert de snapshot.

**C. Detección de Jarvis operativa**
- [ ] Backend arriba con `app/malware/` activo; ClamAV (clamd) corriendo.
- [ ] `MALWARE_YARA_RULES_DIR` con `starter.yar`; confirmar EICAR detecta
      (sub-test §5.5) **antes** de arrancar la noche.
- [ ] (Opcional pero recomendado) **Sysmon** instalado + `SYSMON_ENABLED=true`
      para T1055/T1003 (si no, esos quedan como gap esperado, no como fallo).
- [ ] `MALWARE_WATCH_FOLDERS` apuntando a las carpetas del blanco donde Atomic
      deja artefactos (o instancia de Jarvis en el blanco, §2.3).
- [ ] Carpeta `app/malware/rules/generadas/` creada para las reglas propuestas.

**D. Orquestador nocturno**
- [ ] Parámetros de topes: `MAX_HORAS_NOCHE`, `MAX_PASES`, `MAX_MIN_TECNICA`,
      `MAX_INTENTOS_TECNICA`, `N_ESTABLE`, `T_det` (ventana de detección).
- [ ] Modo de reglas elegido: **asistido** (default, propuestas para Damian) o
      **autónomo-en-range** (recompila YARA solo dentro del range).
- [ ] Log maestro JSONL + nota-índice de Obsidian inicializados.
- [ ] Arsenal cargado (§5): lista de técnicas + variantes + sub-test EICAR/YARA.

**E. Verificación previa (dry-run corto, no toda la noche)**
- [ ] Correr **1 técnica fácil** (T1059.001) de punta a punta: detonar → detectar
      → journalizar → revert. Confirmar que la nota de Obsidian sale bien formada.
- [ ] Confirmar que una técnica **no** detectada genera un **gap** y una **mejora
      propuesta** correctamente (probar el camino del bucle externo con 1 pase).
- [ ] Confirmar reset limpio entre técnicas (snapshot revert + cleanup).

**F. Recién entonces: lanzar la corrida nocturna completa.**

---

## Fuentes (investigación 2026)

- [redcanaryco/atomic-red-team (GitHub, README)](https://github.com/redcanaryco/atomic-red-team/blob/master/README.md)
- [Atomic Red Team™ Documentation](https://www.atomicredteam.io/docs/atomic-red-team)
- [Test your defenses with Red Canary's Atomic Red Team](https://redcanary.com/atomic-red-team/)
- [MITRE Caldera Releases New User Interface for Adversarial Emulation](https://www.mitre.org/news-insights/news-release/mitre-caldera-releases-new-user-interface-adversarial-emulation)
- [Mastering Automated Adversary Emulation with MITRE Caldera](https://maxwellseefeld.org/caldera/)
- [Get Started — Adversary Emulation and Red Teaming (MITRE ATT&CK)](https://attack.mitre.org/resources/get-started/adversary-emulation-and-red-teaming/)
- [MITRE & CISA Release Caldera Extension for Operational Technology](https://www.mitre.org/news-insights/news-release/mitre-cisa-release-open-source-caldera-operational-technology)
- Interno: `lab/CYBER-RANGE-DESIGN.md`, `backend/app/malware/*`, `backend/app/obsidian/*`, `backend/app/tools/{malware,obsidian}.py`.
