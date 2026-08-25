# DEFENSA "KERNEL-GRADE" GRATIS — Checklist de prioridades

> **Estado:** SOLO DOCUMENTACIÓN. No hay código escrito ni nada instalado a partir
> de este documento. Ninguna decisión de acá modifica todavía `backend/app/malware/`.
> **Fecha:** 2026-08-17
> **Complementa** — no reemplaza — a `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md` (el
> diseño). Usa los mismos nombres de componente, GUIDs, flags y convenciones que
> ese doc; si algo parece contradecirlo, gana el diseño.

---

## Cómo leer este doc

El **plan por fases** del diseño (§6) ordena el trabajo **por esfuerzo** (menor →
mayor): primero Sysmon, después ETW, AMSI y recién al final el enforcement. Útil
para *ejecutar*.

Este checklist ordena las mismas piezas **por cuánto protegen** (mayor protección
→ menor), con una nota de esfuerzo en cada una. Útil para *priorizar qué mueve más
la aguja de seguridad por unidad de trabajo*. Los dos órdenes conviven: uno dice
"qué es más fácil de arrancar", el otro "qué te protege más".

**Regla transversal, sobre todo lo demás:** **todo lo que bloquea (ASR, AppLocker,
WDAC) va primero en modo AUDITORÍA.** Se corre en audit el tiempo suficiente, se
revisa qué *habría* marcado/bloqueado, y **recién cuando se confirma que no rompe
software legítimo** (incluido el propio Jarvis: Semgrep, Bandit, nmap, ffmpeg,
cmd.exe, python.exe — ver allowlist real de `process_monitor.py`) se pasa a
bloqueo. Nunca enforce directo.

**Convención de campos por ítem:**
- **Qué protege** — clase de ataque/táctica (referida a la taxonomía del vault).
- **Esfuerzo** — bajo / medio / alto.
- **Tipo** — detección o bloqueo (o híbrido).
- **¿Protege solo?** — si aporta protección por sí mismo, o si necesita que Jarvis
  esté cableado (correlación + respuesta) para que sirva.

---

## Orden priorizado (por cuánto protege)

### [ ] 0. Defender a full + Tamper Protection — *PASO CERO*
- **Protección:** altísima. **Esfuerzo:** casi nulo.
- **Qué protege:** es la base sobre la que se apoya todo lo demás. Antivirus de
  Microsoft **activado del todo** (Real-Time Protection, Behavior Monitoring, Cloud
  Protection, script scanning) + **Tamper Protection**, el blindaje que impide que
  malware —o un atacante con privilegios— **desactive las defensas** (apagar el AV,
  bajar ASR, cegar AMSI). Sin esto, todo lo de abajo se puede desmantelar.
- **Tipo:** bloqueo (AV) + protección de la configuración (Tamper).
- **¿Protege solo?** **Sí, protege solo** y además es **prerequisito** de los ítems
  3 (AMSI necesita Defender con RTP/Behavior/script scanning) y 2 (ASR es el motor
  de Defender). Es literalmente el paso cero: si Defender no está a full, ni AMSI ni
  ASR existen.

### [ ] 1. AppLocker → luego WDAC (whitelisting de aplicaciones)
- **Protección:** la más grande del set. **Esfuerzo:** el más alto.
- **Qué protege:** impide **ejecutar binarios/scripts/drivers no autorizados** —
  troyano, dropper, loader, BYOVD, cualquier cosa fuera de la allowlist. Es la
  defensa más fuerte contra "correr lo que no debería correr". WDAC actúa a nivel
  **Code Integrity (kernel)**, antes de cargar en memoria; AppLocker actúa a nivel
  proceso (user-mode), más simple de operar y más evadible.
- **Esfuerzo alto porque:** es lo más peligroso de mal-configurar. Una policy
  incompleta **rompe software legítimo, incluido el propio backend de Jarvis**.
- **Tipo:** bloqueo.
- **¿Protege solo?** **Sí, protege solo** una vez en enforce (no necesita a Jarvis
  para bloquear). En audit, además, es una **fuente de detección** valiosa.
- **⚠️ OBLIGATORIO:** empezar por **AppLocker** (escalón más simple y reversible),
  en **modo auditoría** largo, tunear qué es "normal" en esta PC, y **recién
  después** pasar a bloqueo y evolucionar hacia **WDAC**. **Siempre** audit largo
  antes de enforce, con cero falsos positivos sobre el software real de Damian.

### [ ] 2. Reglas ASR de Microsoft Defender (audit → luego block)
- **Protección:** muy alta. **Esfuerzo:** bajo.
- **Qué protege:** frena **cadenas de ataque comunes** de una: Office lanzando
  procesos hijos, **robo de credenciales de LSASS** (GUID
  `9E6C4E1F-…-A39EF669E4B0`, T1003.001), ejecutables **venidos de email/USB**,
  ejecución de contenido ofuscado, abuso de WMI/PSExec para movimiento lateral.
- **Cómo se activa:** por PowerShell (`Set-MpPreference`/`Add-MpPreference`) o GPO.
  `Actions=2` (audit) o `6` (warn) primero; `Actions=1` (block) después.
- **Tipo:** bloqueo (y detección en modo audit).
- **¿Protege solo?** **Sí, protege solo** en block. Excelente relación
  protección/esfuerzo: casi tan protector como el whitelisting pero muchísimo más
  barato de activar.
- **⚠️ Orden:** activar **regla por regla, no todas de golpe**, en **audit**
  primero; revisar qué se habría bloqueado (automatizaciones de Office legítimas
  chocan con "Office no crea hijos"); empezar pasando a block la de **LSASS** y
  **Office→hijos**.

### [ ] 3. AMSI para fileless
- **Protección:** alta. **Esfuerzo:** medio.
- **Qué protege:** ataques **en memoria / fileless / polimórficos** — PowerShell
  ofuscado, macros de Office, JS/VBScript, .NET — el terreno donde la firma de
  archivo (YARA/ClamAV, ya presentes) **no** aplica. Con Defender detrás, puede
  **bloquear el script antes de que se ejecute** (lo más cerca de "prevención" que
  se consigue contra fileless gratis).
- **Tipo:** híbrido — detección del script + bloqueo (vía Defender).
- **¿Protege solo?** **Parcialmente solo:** Defender+AMSI bloquean el script por su
  cuenta, pero para que Jarvis **correlacione y responda** (registrar, encadenar con
  otras señales) necesita el `amsi_watch` cableado. **Depende del ítem 0** (Defender
  a full con script scanning).

### [ ] 4. Sysmon + ETW — capa sensorial de Jarvis
- **Protección:** no bloquean por sí solos, pero **habilitan la respuesta**.
  **Esfuerzo:** bajo (Sysmon: el consumo ya está escrito) a medio (ETW tiempo real).
- **Qué protege:** dan a Jarvis el **PID + imagen** del proceso responsable —lo que
  hoy le falta al `behavioral_watcher`, que detecta el *patrón* de ransomware pero
  no puede identificar ni matar al proceso que cifra. Con eso Jarvis puede
  **reaccionar**: matar el proceso, cuarentena, cortarle la red. Cubren fileless
  (Sysmon 8/10 memoria, 1 cmdline), stealer/LSASS (10 ProcessAccess), RAT/C2 (3
  net, 22 DNS), droppers (1+11), ejecución/LOLBins (ETW Kernel-Process + 4688).
  Además **alimentan el bucle auto-mejorante** de Jarvis.
- **Tipo:** detección (pura). Ven, no frenan.
- **¿Protege solo?** **No — necesita que Jarvis esté cableado.** Sin el
  `response_engine` que correlaciona y despacha una acción, Sysmon/ETW solo llenan
  un log. Enganchan con lo que ya existe: `behavioral_watcher` (entropía/ransomware,
  ahora + PID del ETW), `integrity`/FIM (disparador en tiempo real sobre archivos
  críticos) y `process_monitor`. Ampliar `sysmon_monitor.py` de Event ID 8/10 a
  **1/3/7/11/22** y sacar el filtro "solo mi PID".
- **Nota:** es **contención posterior**, no prevención: siempre hay una ventana en
  la que el proceso ya hizo *algo* antes de que Jarvis lo mate. Por eso va después
  del enforcement preventivo en este orden por-protección. Sysmon Event 10 es
  ruidoso — config con exclusiones curadas obligatoria antes de accionar sus alertas.

### [ ] 5. WFP — bloqueo de red (`fwpuclnt`)
- **Protección:** media-alta. **Esfuerzo:** avanzado.
- **Qué protege:** corta **C2/beaconing y exfiltración** — añade filtros de bloqueo
  de red desde user-mode (`fwpuclnt`, capa ALE `FWPM_LAYER_ALE_AUTH_CONNECT_V4`),
  sin driver propio. Es **contención de red**: cerrarle la salida a un proceso ya
  detectado. Va al final porque es el escalón más avanzado y llega después de que el
  ataque ya está en curso.
- **Tipo:** bloqueo (de red).
- **¿Protege solo?** **Parcialmente:** un filtro base pre-cargado (bloquear una IP
  de C2 conocida) previene esa conexión por sí solo, pero el uso principal —cortar
  la red del PID que Jarvis acaba de detectar— **necesita a Jarvis cableado**
  (detección → `response_engine` → filtro WFP reactivo).
- **⚠️ Cuidado:** límite de **8192 filtros** del sistema; un filtro demasiado ancho
  puede dejar sin red al propio Jarvis (necesita 443 para el LLM cloud, VirusTotal,
  búsquedas). Filtros **específicos por proceso/IP, con TTL/limpieza**, no reglas
  anchas permanentes.

---

## Resumen en una tabla

| Prioridad | Componente | Protección | Esfuerzo | Det/Blo | ¿Protege solo? |
|---|---|---|---|---|---|
| 0 | Defender full + Tamper Protection | altísima | casi nulo | bloqueo | **sí** (y prerequisito de 2 y 3) |
| 1 | AppLocker → WDAC | la más grande | el más alto | bloqueo | **sí** (en enforce) |
| 2 | ASR rules | muy alta | bajo | bloqueo | **sí** (en block) |
| 3 | AMSI | alta | medio | híbrido | parcial (Defender sí; correlación necesita Jarvis) |
| 4 | Sysmon + ETW | habilita respuesta | bajo–medio | detección | **no** (necesita Jarvis cableado) |
| 5 | WFP (red) | media-alta | avanzado | bloqueo | parcial |

**Nota sobre los dos órdenes:** este ranking por-protección **no** es el orden de
implementación. El orden de *ejecución* (por esfuerzo/riesgo) es el del diseño §6:
Sysmon → ETW → AMSI → enforcement (ASR → AppLocker → WDAC → WFP). En la práctica se
arranca por lo barato y sensorial (Sysmon/ETW) aunque en protección pura estén más
abajo, y el whitelisting —lo que más protege— se deja para cuando hay audit
suficiente para no romper nada.

---

## Cómo se relaciona con el diseño

Este checklist es la **vista por prioridad de protección** del plan que ya está en
`lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`. Correspondencias:

- Los **componentes, GUIDs y mecanismos** (ETW providers, Sysmon Event IDs, GUID de
  LSASS, `Set-MpPreference`, `fwpuclnt`/capa ALE, límite de 8192 filtros) salen de
  la **§2 (tabla de componentes)** y **§4** del diseño.
- La **regla "audit antes de block"** y el sub-orden ASR → AppLocker → WDAC → WFP
  vienen de la **§6 (plan por fases)** y **§7 (riesgos)** del diseño.
- El "**protege solo vs. necesita Jarvis cableado**" refleja la distinción
  **prevención (ASR/WDAC/AppLocker/WFP pre-cargados) vs. contención posterior
  (detectar→matar)** de la **§4** y la lectura de la tabla en **§2**.
- Los **límites honestos** (canal Event Log manipulable, AMSI evadible, no veta
  creación de proceso *antes* del hecho de forma arbitraria, rootkits no
  detectables desde el host) están en la **§5** del diseño y aplican igual acá.
- Cada capacidad nueva debería llevar su propia flag siguiendo la convención del
  proyecto (`ETW_ENABLED`, `AMSI_WATCH_ENABLED`, `ASR_ENFORCE`, `WDAC_ENFORCE`,
  `WFP_BLOCK_ENABLED`), sin debilitar los gates ya decididos (**§7** del diseño).

Para el **detalle técnico, arquitectura, diagrama, circuito de respuesta y
referencias**, ver el diseño completo. Este doc es solo el **orden de prioridad**.
