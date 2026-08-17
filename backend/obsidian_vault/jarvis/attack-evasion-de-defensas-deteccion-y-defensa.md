---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- evasion-de-defensas
- deteccion
- defensa
title: 'ATT&CK Evasión de Defensas - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0005**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **evita ser detectado**: apaga defensas, borra rastros, ofusca y se disfraza. Es la táctica más grande de ATT&CK.

## T1562 — Impair Defenses (apagar AV/EDR, borrar logs, firewall)
**Qué es.** Deshabilitar o cegar los controles de seguridad.
**Uso del adversario (conceptual).** Detiene servicios de AV/EDR, agrega exclusiones, apaga logging (`wevtutil cl`, `auditpol`), o baja el firewall.
**Detección.** Servicios de seguridad que se detienen (Windows 7036/7040); limpieza de logs (Windows 1102 = "audit log cleared" — señal fuerte); cambios en exclusiones de Defender; `auditpol /clear`. **Reenviar logs a un SIEM central** en tiempo real neutraliza el borrado local.
**Mitigación/endurecimiento.** Tamper protection del EDR; reenvío inmediato de logs a servidor central (WEF/syslog); alertar sobre parada de servicios de seguridad; mínimo privilegio.
**Prueba atómica.** Atomic Red Team T1562.001 intenta agregar exclusiones/detener Defender en laboratorio para verificar que tu monitoreo lo alerta.

## T1070 — Indicator Removal (borrar logs, timestomp, borrar archivos)
**Qué es.** Eliminar evidencia: limpiar event logs, `history`, alterar timestamps (timestomp), borrar los propios binarios.
**Detección.** Windows 1102 / Linux `auditd` gaps; archivos con `$STANDARD_INFORMATION` vs `$FILE_NAME` inconsistentes (timestomp); truncado de `.bash_history`.
**Mitigación.** Logs append-only y reenviados fuera del host; FIM. Jarvis aplica esta filosofía con su **log firmado Ed25519 append-only** en `investigation/` (reusado por `malware/`): un rastro que el atacante no puede reescribir localmente sin invalidar la firma.

## T1027 — Obfuscated/Encoded Files or Information
**Qué es.** Ofuscar payloads (base64, empaquetadores, cifrado) para evadir firmas. Enlaza con [[Familias de Malware - Taxonomía Detección y Defensa]] (polimórfico, packers).
**Detección.** Alta entropía en secciones de ejecutables (packer); PowerShell `-EncodedCommand`; strings ilegibles + APIs de descifrado. Detección **conductual** > firma acá.
**Mitigación.** AMSI (des-ofusca scripts en memoria antes de ejecutar); EDR conductual; application control.

## T1036 — Masquerading (nombres/rutas/firmas falsas)
**Qué es.** Hacer pasar el malware por algo legítimo: nombrarlo `svchost.exe`, ponerlo en `System32`, o firmar con un cert robado.
**Detección.** `svchost.exe` corriendo desde una ruta que no es `System32`; proceso legítimo con padre incorrecto (ej. `svchost` sin `services.exe` de padre); firma inválida/ausente en binarios "del sistema".
**Mitigación.** Application control por ruta+firma; baseline de árbol de procesos legítimo.

## T1218 — System Binary Proxy Execution (LOLBins: rundll32, regsvr32, mshta, msbuild)
**Qué es.** Usar binarios firmados de Microsoft para ejecutar código malicioso y evadir application control.
**Uso del adversario (conceptual).** `rundll32`/`regsvr32`/`mshta` ejecutan DLLs/scripts remotos; abusa de la confianza en binarios firmados (ver proyecto LOLBAS).
**Detección.** Estos binarios haciendo conexiones de red o con líneas de comando anómalas; `regsvr32` con URL; `mshta` ejecutando desde temp. Process ancestry (CISA/LOTL).
**Mitigación.** WDAC con reglas que cubran LOLBins; bloquear los innecesarios; logging de línea de comando.
**Prueba atómica.** Atomic Red Team T1218.* cubre `rundll32`/`regsvr32`/`mshta` con pruebas que ejecutan un payload benigno para validar detección.

## T1497 — Virtualization/Sandbox Evasion / T1140 — Deobfuscate/Decode
**Qué es.** Detectar si corre en sandbox/VM y no detonar; descifrar el payload en runtime.
**Detección.** Malware que "duerme" o chequea artefactos de VM; desempaquetado en memoria (EDR).
**Mitigación.** Sandboxing realista; detonación con EDR conductual; no depender solo de sandbox.

## Referencias
- MITRE ATT&CK TA0005 (Defense Evasion); proyecto LOLBAS (lolbas-project.github.io).
- CISA/NSA/FBI — LOTL (process ancestry para LOLBins).
- Atomic Red Team — atomics T1562.*, T1070.*, T1218.*, T1036.
