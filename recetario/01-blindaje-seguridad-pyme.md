# 01 — Blindaje de seguridad de una PyME ⭐

> **LA receta que monetiza.** Es el servicio que se vende: dejar una PC/red de
> PyME endurecida a nivel "kernel-grade" **usando solo herramientas gratis que ya
> trae Windows**, sin comprar un EDR comercial ni escribir un driver. La más
> importante del recetario.
>
> Basada en [`../lab/DEFENSA-PRIORIDADES.md`](../lab/DEFENSA-PRIORIDADES.md) (el
> orden por cuánto protege cada capa) y
> [`../lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`](../lab/DEFENSA-KERNEL-GRATIS-DESIGN.md)
> (el diseño técnico, GUIDs, mecanismos y límites honestos). Si algo acá parece
> contradecir el diseño, **gana el diseño**.

## Qué produce

Una máquina Windows con defensa de nivel empresarial construida en capas: el
antivirus a full y blindado, whitelisting de aplicaciones, reglas que cortan
cadenas de ataque comunes, cobertura de fileless, y telemetría de kernel para
detectar y responder — todo gratis. El entregable al cliente es la **PC endurecida
+ un reporte** de qué capas quedaron activas, qué está en auditoría y qué límites
honestos tiene frente a un EDR pago.

## Estación / especialista

Seguridad / **Garde-manger** (el defensor, el puesto del frío que cuida que nada
entre podrido). **Requiere PC con admin** en la máquina del cliente. Varios pasos
son irreversibles-si-mal-hechos → se cocina con cuidado y siempre en auditoría
primero.

## Ingredientes (requisitos previos)

- Windows 10/11 con permisos de **administrador**.
- PowerShell con consola elevada.
- Un período de **auditoría** disponible (días, no minutos): esta receta no se
  sirve en una sola sesión. Se activa en modo audit, se observa, y recién después
  se pasa a bloqueo.
- Inventario del **software legítimo** del cliente (qué apps usa de verdad), para
  no romperlo con el whitelisting.
- Sysmon (driver ya firmado por Microsoft/Sysinternals) si se va a sumar la capa
  sensorial.

## Pasos

**Regla transversal, sobre todo lo demás:** todo lo que bloquea (ASR, AppLocker,
WDAC) va **primero en modo AUDITORÍA**. Se corre en audit el tiempo suficiente, se
revisa qué *habría* bloqueado, y **recién cuando se confirma que no rompe software
legítimo** se pasa a bloqueo. **Nunca enforce directo.**

El orden de abajo es por **cuánto protege** (mayor → menor). El orden de *ejecución*
por esfuerzo es distinto (Sysmon primero, whitelisting al final) — ver §"Notas".

1. **Paso cero — Defender a full + Tamper Protection.** Protección altísima,
   esfuerzo casi nulo, y es prerrequisito de los pasos 3 y 4. Activar todo:
   Real-Time Protection, Behavior Monitoring, Cloud Protection, script scanning, y
   **Tamper Protection** (impide que malware o un atacante desactive las defensas).
   Sin esto, todo lo demás se puede desmantelar.

2. **AppLocker → luego WDAC (whitelisting de aplicaciones).** La capa que **más
   protege** y la de **mayor esfuerzo**: impide ejecutar binarios/scripts/drivers
   fuera de la allowlist. Empezar **siempre por AppLocker** (más simple y
   reversible), en **modo auditoría largo**, tunear qué es "normal" en esa PC, y
   recién después pasar a bloqueo y evolucionar a **WDAC** (que actúa a nivel Code
   Integrity, en kernel). Una policy incompleta rompe software legítimo → audit con
   cero falsos positivos antes de enforce.

3. **Reglas ASR de Defender (audit → block).** Muy alta protección, esfuerzo bajo:
   la mejor relación protección/esfuerzo. Frenan cadenas comunes (Office lanzando
   hijos, robo de credenciales de **LSASS** — GUID `9E6C4E1F-…-A39EF669E4B0`,
   ejecutables de email/USB, WMI/PSExec lateral). Activar **regla por regla, no
   todas de golpe**, con `Set-MpPreference`/`Add-MpPreference`: `Actions=2` (audit)
   o `6` (warn) primero, `Actions=1` (block) después. Empezar pasando a block la de
   **LSASS** y **Office→hijos**.

4. **AMSI para fileless.** Protección alta, esfuerzo medio. Cubre ataques en
   memoria / fileless / polimórficos (PowerShell ofuscado, macros, JS/VBScript,
   .NET) — el terreno donde la firma de archivo no aplica. Con Defender detrás,
   bloquea el script antes de ejecutarlo. Depende del paso 0 (script scanning
   activo).

5. **Sysmon + ETW — capa sensorial.** No bloquean solos, pero **habilitan la
   respuesta**: dan el PID + imagen del proceso responsable. Con eso el defensor
   puede matar el proceso, ponerlo en cuarentena o cortarle la red. Cubren fileless,
   LSASS, RAT/C2, droppers. Config con exclusiones curadas obligatoria (Sysmon
   Event 10 es ruidoso).

6. **WFP — bloqueo de red.** Protección media-alta, esfuerzo avanzado. Corta
   C2/beaconing y exfiltración con filtros user-mode (`fwpuclnt`, capa ALE). Es
   contención: cerrarle la salida a un proceso ya detectado. **Ojo:** límite de
   8192 filtros; usar filtros específicos por proceso/IP con TTL, nunca reglas
   anchas permanentes (podés dejar sin red a la propia PC).

## Tiempo estimado

Días a semanas por cliente — **no** es una sesión. El grueso del tiempo es el
período de **auditoría** de cada capa que bloquea (pasos 2 y 3, sobre todo). La
activación técnica de cada capa es de minutos; la validación de que no rompe nada
es lo que lleva tiempo.

## Notas / errores comunes

- **Dos órdenes distintos.** Esta receta lista por *protección* (Defender →
  AppLocker → ASR → AMSI → Sysmon → WFP). El orden de *ejecución* por esfuerzo/
  riesgo del diseño §6 es al revés en la punta: arrancar por lo barato y sensorial
  (Sysmon → ETW → AMSI) y dejar el enforcement (ASR → AppLocker → WDAC → WFP) para
  cuando hay audit suficiente. En la práctica se combinan: Defender full desde el
  minuto cero, telemetría temprano, whitelisting al final.
- **El error clásico: enforce directo.** Activar AppLocker/WDAC/ASR en bloqueo sin
  audit previo rompe software legítimo del cliente (y del propio Raphael: Semgrep,
  Bandit, nmap, ffmpeg, cmd.exe, python.exe). Audit largo, análisis, y recién ahí
  block.
- **Honestidad con el cliente (parte del servicio).** Esto NO iguala a un EDR con
  driver propio: ETW/Sysmon notifican *después* de que el proceso arrancó (contienen,
  no previenen); AMSI es evadible; rootkits/bootkits/BYOVD no se detectan confiablemente
  desde el host. Decirlo es parte del valor — ver §5 del diseño.
- Cada capacidad nueva lleva su **flag** (`ETW_ENABLED`, `AMSI_WATCH_ENABLED`,
  `ASR_ENFORCE`, `WDAC_ENFORCE`, `WFP_BLOCK_ENABLED`) siguiendo la convención del
  proyecto; no debilitar los gates ya decididos.

## ¿Candidata a skill?

**⭐ SÍ — la candidata #1 del recetario.** Es el servicio que se vende: graduarla a
skill hace que cada cliente reciba el mismo endurecimiento, con el mismo rigor y el
mismo reporte, y escala el negocio de "a mano por cliente" a "Raphael ejecuta, yo
superviso". El paso que siempre queda humano: la **decisión de pasar de audit a
block** (mirar los falsos positivos del software real del cliente) y el acceso
admin a la máquina. La automatización cubriría la activación, la recolección de lo
que se habría bloqueado, y el reporte; el gate audit→block lo firma Damian.
