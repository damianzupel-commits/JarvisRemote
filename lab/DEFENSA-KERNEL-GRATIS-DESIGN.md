# DEFENSA "KERNEL-GRADE" GRATIS — Documento de diseño

> **Estado:** SOLO DISEÑO. No hay código escrito ni nada instalado a partir de este
> documento. Ninguna decisión de acá modifica todavía `backend/app/malware/`.
> **Fecha:** 2026-08-17
> **Autor de la sesión:** diseño asistido por IA, alineado con el módulo real
> `backend/app/malware/` del repo.
> **Alcance:** capa de **detección + respuesta en tiempo (casi) real** para Jarvis
> en Windows, usando **solo herramientas gratis**, **sin escribir ni firmar un
> driver de kernel propio** (el certificado EV y el driver custom quedan
> descartados por ahora, decisión explícita de Damian).

---

## 1. Encuadre

### Objetivo

Acercar la protección de Jarvis a lo que hace un **EDR** (Endpoint Detection &
Response) comercial — visibilidad de kernel + capacidad de **bloquear**, no solo
mirar — pero con **presupuesto $0** y **riesgo de BSOD = 0**, porque no se
introduce ni una línea de código propio en el kernel.

Hoy el módulo `app/malware/` es sólido en su terreno pero tiene un techo conocido,
documentado en el propio código:

- `behavioral_watcher.py` detecta el **patrón** de ransomware (≥15 archivos en 15s
  con entropía media ≥7.5 bits/byte) pero **no puede identificar ni matar el
  proceso** que cifra — su propio docstring lo dice: "requiere correlación a nivel
  de kernel (qué proceso tiene el handle de escritura abierto)".
- `process_monitor.py` compara **nombres** de procesos hijos contra una allowlist
  y puertos de salida "raros" — filtro grueso, ciego a un `python.exe` no legítimo
  o a C2 sobre 443.
- `sysmon_monitor.py` (parte C, **experimental, `SYSMON_ENABLED=false` por
  default**) ya apunta en la dirección correcta: **leer eventos de kernel que
  Windows expone**, sin driver propio. Cubre hoy solo Event ID 8/10 filtrados al
  PID del backend.

La biblioteca de amenazas del vault (`obsidian_vault/jarvis/`) ya dejó el marco
conceptual: **firma detecta lo conocido, comportamiento detecta lo nuevo**
(`higiene-de-deteccion-firmas-vs-comportamiento.md`), el ~90% del malware 2026 es
polimórfico y el fileless es la mayoría de los incidentes serios
(`familias-de-malware-taxonomia-deteccion-y-defensa.md`). Esas dos clases son
justamente las que la firma estática (YARA/ClamAV, ya presentes) **no** cubre — y
las que esta capa apunta a cubrir con **telemetría y comportamiento**.

### Tesis

> **Orquestar el kernel de Windows en vez de meterse dentro de él.**

Windows ya trae, **firmados por Microsoft y gratis**, todos los componentes de
kernel que hacen falta para (a) **ver** lo que pasa a nivel de proceso, imagen,
archivo, registro y red, y (b) **bloquear** comportamientos y ejecuciones enteras.
El trabajo de Jarvis no es escribir esos componentes — es **configurarlos,
suscribirse a su telemetría desde espacio de usuario (Python), correlacionar, y
disparar sus mecanismos de bloqueo**. Se consigue visibilidad y enforcement de
nivel kernel **sin asumir el riesgo de código propio en el kernel** (un driver mal
escrito = BSOD, y firmarlo cuesta un certificado EV + proceso de attestation de
Microsoft, ambos descartados).

Concretamente, dos familias de piezas:

- **Detección (consumir telemetría):** ETW, Sysmon, AMSI, auditoría de Windows.
  Jarvis **lee**; el kernel de Microsoft **genera** los eventos.
- **Bloqueo (configurar/disparar enforcement de Microsoft):** Defender ASR, WDAC /
  AppLocker, WFP. Jarvis **configura la regla**; el motor de Microsoft (en muchos
  casos dentro del kernel) **la aplica**.

---

## 2. Tabla de componentes

Leyenda: **Det** = detección · **Blo** = bloqueo/prevención · **K** = enforcement
en kernel · **U** = corre/decide en user-mode. Latencia = orden de magnitud
realista de "evento ocurre → Jarvis puede reaccionar" (detección) o "regla activa →
efecto" (bloqueo).

| # | Componente (gratis) | ¿Det / Blo? | ¿Kernel / User? | Latencia aprox. | Qué clase de ataque cubre (familias/tácticas del vault) |
|---|---|---|---|---|---|
| 1 | **ETW** — providers de kernel (`Microsoft-Windows-Kernel-Process`, `-Kernel-File`, `-Kernel-Network`, `-Kernel-Registry`), consumido desde Python (`pywintrace` / `PythonForWindows`) | **Det** | Genera en **K**, consume en **U** | ~ms–cientos de ms (tiempo real, callback por evento) | Ejecución (T1059), inyección (T1055), persistencia (T1547/Run key), descubrimiento; da el **PID+imagen** que hoy le falta al `behavioral_watcher` |
| 2 | **Sysmon** (driver YA firmado por Microsoft/Sysinternals) + config tipo SwiftOnSecurity/Olaf Hartong, eventos al Event Log `Microsoft-Windows-Sysmon/Operational` | **Det** | Captura en **K**, Jarvis lee en **U** (`win32evtlog.EvtQuery`) | ~cientos de ms a seg (vía Event Log) | Fileless (8/10 memoria, 1 cmdline), stealer/LSASS (10 ProcessAccess → T1003.001), RAT/C2 (3 net, 22 DNS), dropper (1+11), masquerading |
| 3 | **AMSI** (Antimalware Scan Interface) | **Det** (con Defender detrás, también **Blo** del script) | Interfaz en **U**, motor AV puede estar en **K** | Tiempo real, **antes de ejecutar** el script | Fileless / polimórfico en memoria: PowerShell ofuscado, macros de Office, JS/VBScript, .NET — el terreno donde la firma de archivo NO aplica |
| 4 | **Auditoría avanzada de Windows** — Event 4688 con **línea de comandos** (+ Script Block Logging 4104) | **Det** | Genera en **K**, Jarvis lee en **U** (Event Log) | ~seg (Event Log) | Ejecución/LOLBins, dropper/loader (PowerShell ofuscado), living-off-the-land — redundancia barata frente a Sysmon 1 |
| 5 | **Microsoft Defender ASR** (Attack Surface Reduction rules), activadas por `Set-MpPreference`/`Add-MpPreference` o GPO | **Blo** (y Det en modo audit) | **K** (motor Defender) | Preventivo, **en el acto** (bloquea la acción) | Office lanzando hijos, robo de credenciales de **LSASS** (GUID `9E6C4E1F-…-A39EF669E4B0`), ejecución de contenido ofuscado, USB, WMI/PSExec lateral |
| 6 | **WDAC** (Windows Defender Application Control) | **Blo** | **K** (integrado al módulo Code Integrity; enforcement **antes de cargar en memoria**) | Preventivo, en el acto | Ejecución de binarios/drivers/scripts **no autorizados** (troyano, dropper, BYOVD); lo más fuerte contra "ejecutar lo que no está en la allowlist" |
| 7 | **AppLocker** | **Blo** | **U** (a nivel de proceso; más fácil de evadir que WDAC) | Preventivo, en el acto | Igual que WDAC pero más simple de operar y más evadible — buen escalón intermedio |
| 8 | **WFP** (Windows Filtering Platform), filtros añadidos desde user-mode con `fwpuclnt` en capas ALE (`FWPM_LAYER_ALE_AUTH_CONNECT_V4`) | **Blo** (de red) | Filtro se evalúa en **K**, se **define** desde **U** sin driver | Preventivo/en el acto sobre cada conexión | C2/beaconing (RAT, botnet), exfiltración — **cortar la red de un proceso** sin driver propio (contención) |
| 9 | **MpCmdRun.exe** (CLI de Defender) + **Defender/AMSI** para escaneo bajo demanda | **Det** (+ Blo por cuarentena de Defender) | Motor en **K/U** | Segundos–minutos (on-demand) | Confirmación de archivo concreto con el motor de Microsoft, complementa YARA/ClamAV/VirusTotal ya presentes |

**Lectura clave de la tabla — qué previene de verdad vs. qué solo mira:**

- **Bloqueo real sin driver propio, confirmado:** ASR (5), WDAC (6), AppLocker (7)
  y WFP (8). Los cuatro **previenen** — el enforcement lo hace un componente de
  Microsoft, en varios casos dentro del kernel (ASR, WDAC, el filtro WFP), y Jarvis
  solo aporta la **política/regla**.
- **Solo detección:** ETW (1), Sysmon (2), auditoría 4688/4104 (4). Ven, no frenan.
  Jarvis convierte esa detección en respuesta **matando el proceso o cortándole la
  red** — pero eso es **contención posterior**, no prevención (ver §5).
- **AMSI (3)** es el híbrido interesante: como interfaz es user-mode, pero con
  Defender detrás **puede bloquear** el script malicioso **antes** de que se
  ejecute — es lo más cerca de "prevención" que se consigue contra fileless gratis.

---

## 3. Arquitectura

### Idea de una línea

> Jarsis (Python, user-space) **consume** ETW + Sysmon + AMSI + auditoría de
> Windows para **detectar**, correlaciona esos eventos con el `behavioral_watcher`
> / `integrity` (FIM) / `process_monitor` que ya existen, y **configura y dispara**
> Defender ASR + WDAC/AppLocker + WFP para **bloquear**, registrando todo en el
> `store` firmado (Ed25519) y en el vault de Obsidian.

### Diagrama en texto

```
                          KERNEL DE WINDOWS (firmado por Microsoft, gratis)
  ┌───────────────────────────────────────────────────────────────────────────┐
  │  ETW providers        Sysmon drv       AMSI→Defender      Code Integrity    │
  │  (Kernel-Process/      (Event ID        (script scan       (WDAC) · Defender │
  │   File/Network/Reg)     1,3,7,8,10,      en memoria)         ASR engine       │
  │                          11,22)                                              │
  └───┬─────────────┬───────────┬───────────────┬──────────────────┬────────────┘
      │ telemetría  │ Event Log │ verdict       │ ENFORCEMENT       │ ENFORCEMENT
      │ (callback)  │(EvtQuery) │ (scan)        │ (bloquea acción)  │ (bloquea exec)
      ▼             ▼           ▼               ▲                   ▲
 ╔═══════════════════════════════════════════════════════════════════════════╗
 ║  JARVIS · backend FastAPI · user-space (Python)                            ║
 ║                                                                            ║
 ║  ── CONSUMO / DETECCIÓN ────────────────────────────────────────────────  ║
 ║   etw_consumer      (NUEVO)  ── suscripción ETW en tiempo real            ║
 ║   sysmon_monitor.py (EXISTE, ampliar de 8/10 a 1/3/7/11/22)               ║
 ║   amsi_watch        (NUEVO)  ── lee detecciones AMSI/Defender             ║
 ║   audit_4688        (NUEVO)  ── lee 4688(cmdline)/4104 del Security log    ║
 ║                                                                            ║
 ║  ── CORRELACIÓN (lo que ya existe, ahora con PID+imagen reales) ─────────  ║
 ║   behavioral_watcher.py   entropía/ransomware  →  ahora + PID del ETW     ║
 ║   integrity.py (FIM)      baseline SHA-256 de archivos críticos           ║
 ║   process_monitor.py      hijos/conexiones inesperadas                    ║
 ║                                                                            ║
 ║            ▼  evento correlacionado supera umbral                          ║
 ║  ── RESPUESTA / ENFORCEMENT ────────────────────────────────────────────  ║
 ║   response_engine (NUEVO)  decide y despacha:                             ║
 ║     · matar proceso (ya hay taskkill/psutil en el proyecto)              ║
 ║     · WFP: añadir filtro de bloqueo de red (fwpuclnt)                    ║
 ║     · quarantine.py (EXISTE): mover archivo, reversible                  ║
 ║     · Defender ASR / WDAC / AppLocker: activar/endurecer política        ║
 ║                                                                            ║
 ║  ── EVIDENCIA (lo que ya existe) ───────────────────────────────────────  ║
 ║   store.py → log firmado Ed25519 (append-only, encadenado por hash)       ║
 ║   nota a obsidian_vault (autoría jarvis)                                   ║
 ╚═══════════════════════════════════════════════════════════════════════════╝
```

### Cómo encastra con lo que ya existe

- **ETW le da a `behavioral_watcher.py` lo que hoy le falta.** Hoy detecta el
  patrón de cifrado pero no el proceso. Suscribiéndose a
  `Microsoft-Windows-Kernel-File` / `-Kernel-Process` por ETW, Jarvis obtiene el
  **PID + imagen** que está tocando esos archivos → la alerta pasa de "algo está
  cifrando" a "**este** PID está cifrando, matalo".
- **`sysmon_monitor.py` se amplía, no se reescribe.** Ya lee el canal
  `Microsoft-Windows-Sysmon/Operational` con `win32evtlog.EvtQuery` y parsea el XML
  de eventos. Hoy filtra Event ID 8/10 al PID del backend; la ampliación agrega
  1 (process create + cmdline), 3 (net), 11 (file create), 22 (DNS) y saca el
  filtro de "solo mi PID" para cubrir toda la PC.
- **`integrity.py` (FIM) gana un disparador en tiempo real.** Hoy compara contra
  el baseline SHA-256 cuando se lo llama; con ETW `Kernel-File`/`Kernel-Registry`
  puede **reaccionar al instante** a una modificación de `authorized_targets.yaml`,
  la clave Ed25519 o `app/`, en vez de esperar el próximo chequeo.
- **`quarantine.py` y el `store` firmado no cambian.** La cuarentena reversible
  (mover, no borrar; `confirm=true` para borrado definitivo) y el log Ed25519
  encadenado siguen siendo el punto de aterrizaje de toda respuesta — se reusan tal
  cual.

---

## 4. El circuito de respuesta en tiempo (casi) real

```
 evento de kernel (ETW / Sysmon / AMSI / 4688)
        │
        ▼
 Jarvis correlaciona  ──►  ¿supera umbral / IOA conocido?
 (response_engine)          (ej.: Office→PowerShell ofuscado que baja y ejecuta;
        │                    proceso cifrando en masa; handle a LSASS con
        │                    GrantedAccess de dump; conexión a IP/puerto de C2)
        │ sí
        ▼
 ACCIÓN DE CONTENCIÓN (una o varias, por severidad):
   1. matar el proceso responsable          (psutil/taskkill — ya en el proyecto)
   2. cortarle la red por WFP                (fwpuclnt: filtro ALE_AUTH_CONNECT)
   3. cuarentena del binario                 (quarantine.py, reversible)
   4. snapshot / preservación de evidencia   (artifact_store content-addressed)
        │
        ▼
 REGISTRO en audit_log firmado Ed25519       (store.log_event, encadenado por hash)
        │
        ▼
 NOTA a Obsidian (autoría jarvis)            (qué pasó, qué se contuvo, límites)
```

### Latencia realista y prevención vs. contención por vía

| Vía | ¿Qué logra? | Latencia realista | ¿Previene o contiene? |
|---|---|---|---|
| **AMSI + Defender** | Frena el script antes de ejecutar | Tiempo real, pre-ejecución | **PREVIENE** (el script no corre) |
| **ASR rule** activa | Frena el comportamiento (Office→hijo, dump LSASS) | En el acto | **PREVIENE** |
| **WDAC/AppLocker** | Frena el binario no autorizado antes de cargar | En el acto | **PREVIENE** |
| **WFP filtro pre-cargado** | Bloquea conexión saliente por regla ya puesta | En el acto | **PREVIENE** (esa conexión) |
| **ETW/Sysmon → matar proceso** | Detecta y **mata después** de que arrancó | ms a segundos | **CONTIENE** (ya ejecutó algo) |
| **ETW/Sysmon → WFP reactivo** | Detecta C2 y **corta la red después** | ms a segundos | **CONTIENE** |
| **behavioral_watcher → matar PID** | Corta el ransomware **tras** los primeros N archivos | segundos (necesita ≥15 eventos) | **CONTIENE** (algunos archivos ya cifrados) |
| **FIM + ETW** | Reacciona a modificación de archivo crítico | ms a segundos | **CONTIENE** (el cambio ya ocurrió; se revierte/alerta) |

La lección operativa: **todo lo preventivo hay que dejarlo configurado de
antemano** (ASR/WDAC/AppLocker/WFP con reglas base). La vía "detectar → matar" es
inevitablemente **contención posterior**: siempre hay una ventana en la que el
proceso malicioso ya hizo *algo* antes de que Jarvis lo mate. Por eso las dos
capas se complementan y ninguna sola alcanza.

---

## 5. Honestidad sobre los límites

Qué **no** cubre esta vía gratis, frente a un EDR comercial con driver propio:

1. **Interceptar la creación de proceso ANTES vs. matar justo DESPUÉS.** Un EDR con
   minifilter/callbacks de kernel propios puede *vetar* un `CreateProcess` o una
   apertura de handle **antes** de que ocurra. Con esta vía, ETW/Sysmon **notifican
   después** de que el proceso ya arrancó — Jarvis reacciona en ms/segundos, pero
   el proceso ya existió y pudo ejecutar su primer stage. La única prevención real
   pre-hecho viene de las reglas declarativas (ASR/WDAC/AppLocker/WFP), que solo
   cubren los patrones que uno anticipó, no lo arbitrario.

2. **Latencia y pérdida del canal Event Log.** Sysmon y la auditoría 4688 llegan
   vía Event Log (segundos, no microsegundos) y un atacante con privilegios puede
   intentar **cegar el canal** (parar el servicio, limpiar el log, o técnicas tipo
   *WFP manipulation* para tapar telemetría de red). ETW en tiempo real es más
   rápido pero también manipulable desde admin. Un EDR serio protege su propio
   canal desde el kernel; acá el canal es el de Windows, compartido.

3. **Fileless / in-memory avanzado y evasión de AMSI.** AMSI cubre mucho fileless,
   pero **AMSI es evadible** (hay técnicas públicas de bypass de la DLL en el
   proceso). Inyección puramente en memoria sin tocar AMSI, o payloads que
   deshabilitan el logging, se escapan.

4. **Rootkits / bootkits / BYOVD.** La propia taxonomía del vault ya lo dice: la
   detección **desde el host comprometido no es confiable** para rootkits de kernel
   — subvierten al SO que provee la telemetría. Esto necesita Secure Boot, HVCI,
   arranque medido (TPM) — configurables, pero fuera de "orquestar telemetría".

5. **ProcessAccess (Sysmon 10) es ruidoso** — ya documentado en `sysmon_monitor.py`:
   antivirus, debuggers y el propio Task Manager abren handles todo el tiempo. Sin
   una config curada de exclusiones genera falsos positivos.

**En qué casos concretos recién ahí valdría un driver firmado propio:** (a) si se
necesita **vetar** creación de proceso/apertura de handle *antes* del hecho de
forma arbitraria (no solo por regla ASR/WDAC); (b) si se necesita telemetría de
kernel **a prueba de manipulación** desde el propio host; (c) si hace falta cubrir
inyección en memoria que evade AMSI y ETW. Fuera de esos tres, la vía gratis cubre
la enorme mayoría del espectro de amenazas de la taxonomía del vault.

---

## 6. Plan por fases (menor → mayor esfuerzo)

Cada fase entrega valor por sí sola y arranca en **modo detección/auditoría**
antes de cualquier bloqueo. Criterio general: **nada bloquea hasta haber corrido en
audit el tiempo suficiente para conocer los falsos positivos.**

### Fase 1 — Sysmon: instalar, configurar, consumir
- **Qué:** instalar Sysmon (driver ya firmado), aplicar una config base tipo
  **SwiftOnSecurity** (comentada, lista para producción) o **Olaf Hartong
  sysmon-modular** (mapeada a ATT&CK). Ampliar `sysmon_monitor.py` de Event ID 8/10
  a **1, 3, 7, 11, 22** y sacar el filtro "solo mi PID".
- **Esfuerzo:** bajo (el consumo ya está escrito; es config + ampliar el parser).
- **"Listo" cuando:** los eventos ricos de Sysmon llegan al `store` firmado y
  `SYSMON_ENABLED=true` deja de ser experimental porque hay config que filtra el
  ruido conocido (sobre todo Event 10).

### Fase 2 — ETW en tiempo real
- **Qué:** un `etw_consumer` nuevo en Python (`pywintrace` o `PythonForWindows`)
  suscrito a `Microsoft-Windows-Kernel-Process` / `-Kernel-File` / `-Kernel-Network`.
  Objetivo #1: darle al `behavioral_watcher` el **PID+imagen** que hoy le falta.
- **Esfuerzo:** medio (callback en tiempo real, cuidar rendimiento del volumen de
  eventos de kernel).
- **"Listo" cuando:** una ráfaga de ransomware simulada (EICAR/Atomic Red Team, ya
  documentado en el vault) se correlaciona con el PID concreto que la causa.

### Fase 3 — AMSI para fileless
- **Qué:** `amsi_watch` que consume las detecciones AMSI/Defender de scripts
  (PowerShell/macros/JS). Requiere Defender con Real-Time Protection + Behavior
  Monitoring + script scanning activos.
- **Esfuerzo:** medio.
- **"Listo" cuando:** un PowerShell ofuscado de prueba dispara una alerta AMSI que
  Jarvis registra y correlaciona.

### Fase 4 — Enforcement (bloqueo), en orden de riesgo operativo creciente
Sub-orden pensado para minimizar el riesgo de romper software legítimo:

1. **ASR rules** — activar primero en **modo audit** (`Actions=2`), revisar qué se
   habría bloqueado, recién después pasar reglas concretas a **block** (`Actions=1`).
   Empezar por la de **LSASS** (GUID `9E6C4E1F-…-A39EF669E4B0`) y Office→hijos.
2. **AppLocker** — allowlisting a nivel proceso, en audit primero. Escalón más
   simple y reversible que WDAC.
3. **WDAC** — application control a nivel Code Integrity (kernel), lo más fuerte y
   lo más peligroso de mal-configurar. **Siempre** en audit largo antes de enforce.
4. **WFP para red** — filtros `fwpuclnt` en `FWPM_LAYER_ALE_AUTH_CONNECT_V4` para
   cortar C2/exfiltración; primero como acción **reactiva** puntual (bloquear la IP
   de un proceso ya detectado), luego reglas base. Ojo con el límite de **8192
   filtros** del sistema.
- **"Listo" (por sub-fase):** la protección está en block, midiendo cero falsos
  positivos sobre el software real que Damian usa, y toda activación/bloqueo queda
  en el `store` firmado.

---

## 7. Riesgos operativos y recomendaciones

- **WDAC/AppLocker mal configurado = bloquea software legítimo, incluido el propio
  Jarvis.** Jarvis lanza muchos binarios legítimos (Semgrep, Bandit, nmap, ffmpeg,
  cmd.exe, python.exe — ver la allowlist real de `process_monitor.py`). Una policy
  de application control tiene que **allow-listear explícitamente** todo eso o
  romperá el propio backend. **Recomendación: audit mode largo, análisis de lo que
  se habría bloqueado, y recién ahí enforce — nunca enforce directo.**
- **ASR puede dar falsos positivos.** Reglas como "Office no crea procesos hijos"
  chocan con automatizaciones legítimas. **Recomendación: `Actions=2` (audit) o
  `6` (warn) antes de `1` (block)**; activar regla por regla, no todas de golpe.
- **WFP: límite de 8192 filtros y riesgo de cortar tráfico legítimo.** Un filtro
  demasiado amplio puede dejar sin red a Jarvis (que necesita 443 para el LLM
  cloud, VirusTotal, búsquedas). **Recomendación: filtros específicos por proceso/IP,
  con TTL/limpieza, no reglas anchas permanentes.**
- **Sysmon Event 10 (ProcessAccess) ruidoso** — ya sabido en el repo. **Config con
  exclusiones curadas obligatoria** antes de tratar sus alertas como accionables.
- **La respuesta automática que mata procesos puede matar algo legítimo.**
  Mantener el mismo espíritu de gates del resto del proyecto: para acciones
  **irreversibles** (borrado, no la cuarentena que es reversible), patrón
  **dry-run → confirm**; para matar un proceso, umbral alto + registro, y
  posibilidad de operar en "solo alertar" mientras se afina.
- **No debilitar los gates existentes.** El enforcement nuevo se suma **detrás** de
  los gates ya decididos (`authorized_targets.yaml` para pentesting, `confirm=true`
  para lo destructivo, flags `*_ENABLED`). Cada capacidad nueva debería tener su
  propia flag (`ETW_ENABLED`, `AMSI_WATCH_ENABLED`, `ASR_ENFORCE`, `WDAC_ENFORCE`,
  `WFP_BLOCK_ENABLED`) siguiendo la convención del proyecto.

---

## Referencias

**Detección / telemetría**
- pywintrace (wrapper Python de ETW) — Mandiant/Google Cloud: https://cloud.google.com/blog/topics/threat-intelligence/introducing-pywintrace-python-wrapper-etw
- ETW primer — Nasreddine Bencherchali: https://nasbench.medium.com/a-primer-on-event-tracing-for-windows-etw-997725c082bf
- microsoft/krabsetw (wrapper C++/.NET, no Python): https://github.com/microsoft/krabsetw/blob/master/docs/EtwPrimer.md
- PythonForWindows — ETW: https://hakril.github.io/PythonForWindows/build/html/etw.html
- About Event Tracing — Microsoft Learn: https://learn.microsoft.com/en-us/windows/desktop/ETW/about-event-tracing
- Sysmon config SwiftOnSecurity: https://github.com/SwiftOnSecurity/sysmon-config
- Sysmon event IDs (qué colectar) — NXLog: https://nxlog.co/news-and-blog/posts/sysmon-event-ids
- AMSI + Microsoft Defender Antivirus — Microsoft Learn: https://learn.microsoft.com/en-us/defender-endpoint/amsi-on-mdav
- AMSI como fuente de datos — Red Canary: https://redcanary.com/blog/threat-detection/better-know-a-data-source/amsi/
- Command line process auditing (4688) — Microsoft Learn: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/component-updates/command-line-process-auditing

**Enforcement / bloqueo**
- Enable ASR rules — Microsoft Learn: https://learn.microsoft.com/lv-LV/defender-endpoint/enable-attack-surface-reduction
- Configurar ASR por PowerShell/GPO — 4sysops: https://4sysops.com/archives/configure-attack-surface-reduction-in-microsoft-defender-using-group-policy-or-powershell/
- WDAC vs AppLocker (enforcement kernel vs proceso): https://www.cyberask.co.uk/posts/implementing-applocker-and-wdac-for-application-whitelisting.html
- WDAC — Microsoft Learn: https://learn.microsoft.com/en-us/windows/iot/iot-enterprise/customize/application-control
- WFP basic operation / filtros user-mode — Microsoft Learn: https://learn.microsoft.com/en-us/windows/win32/fwp/basic-operation
- WFP ALE (FWPM_LAYER_ALE_AUTH_CONNECT) — Microsoft Learn: https://learn.microsoft.com/en-us/windows/win32/fwp/ale-flow-customization

**Contexto interno (repo/vault)**
- `backend/app/malware/` — módulo real (sysmon_monitor, behavioral_watcher, integrity, process_monitor, quarantine, engine, store)
- `obsidian_vault/jarvis/familias-de-malware-taxonomia-deteccion-y-defensa.md`
- `obsidian_vault/jarvis/higiene-de-deteccion-firmas-vs-comportamiento.md`
- `obsidian_vault/jarvis/attack-*-deteccion-y-defensa.md` (biblioteca ATT&CK por táctica)
