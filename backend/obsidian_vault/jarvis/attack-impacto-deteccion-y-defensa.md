---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- impacto
- ransomware
- deteccion
- defensa
title: 'ATT&CK Impacto - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0040**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **daña disponibilidad o integridad**: cifra, destruye, borra o interrumpe. Es el objetivo final de muchas campañas (ransomware, wipers). Ver [[Familias de Malware - Taxonomía Detección y Defensa]].

## T1486 — Data Encrypted for Impact (ransomware)
**Qué es.** Cifrar archivos/sistemas para pedir rescate.
**Uso del adversario (conceptual).** Recorre discos y shares cifrando archivos en masa, cambia extensiones, deja notas de rescate. Suele combinarse con exfiltración previa (doble extorsión, ver [[ATT&CK Exfiltración - Detección y Defensa]]).
**Detección.** **Patrón conductual**: muchos archivos modificados/renombrados en poco tiempo **con alta entropía** (contenido cifrado); aparición de notas de rescate; borrado de shadow copies (`vssadmin delete shadows` — señal muy fuerte y previa al cifrado). La firma sola llega tarde; el comportamiento es lo que detecta ransomware **nuevo**.
**Mitigación/endurecimiento.** Backups **offline/inmutables** probados (3-2-1); segmentación para limitar shares alcanzables; mínimo privilegio; EDR con rollback; controlled folder access; alertar sobre borrado de shadow copies.
**Prueba atómica.** Atomic Red Team T1486 usa un cifrador **benigno de laboratorio** sobre archivos de prueba (y T1490 para borrado de shadow copies) para validar que la detección conductual dispara — nunca ransomware real.
**Capacidad Jarvis.** Doble cobertura real: (1) la regla `Possible_Ransom_Note` de `starter.yar` matchea texto típico de nota de rescate (severity critical); (2) la **heurística conductual** de `app/malware/behavioral_watcher.py` dispara alerta cuando ve ≥15 eventos de archivo en una ventana de 15s con entropía media ≥7.5 bits/byte — exactamente el patrón de cifrado masivo, e independiente de firmas para cubrir ransomware sin firma conocida. Limitación honesta (documentada en el código): detecta el *patrón*, no mata el *proceso* responsable (eso requeriría correlación a nivel kernel).

## T1490 — Inhibit System Recovery
**Qué es.** Sabotear la recuperación antes de cifrar: borrar shadow copies, backups, deshabilitar recovery.
**Detección.** `vssadmin`/`wbadmin`/`bcdedit` borrando copias o deshabilitando recuperación; borrado de catálogos de backup. Preludio casi seguro de ransomware.
**Mitigación.** Backups offline/inmutables fuera del alcance del host; alertar/bloquear estos comandos; mínimo privilegio.

## T1485 — Data Destruction / T1561 — Disk Wipe (wipers)
**Qué es.** Destruir datos o inutilizar discos sin intención de rescate (wiper — objetivo es daño puro).
**Detección.** Sobrescritura masiva de archivos; escritura directa a `\\.\PhysicalDrive`; corrupción del MBR/boot record; borrado sin nota de rescate.
**Mitigación.** Backups inmutables; mínimo privilegio de acceso a disco raw; EDR; segmentación.

## T1489 — Service Stop / T1529 — System Shutdown/Reboot
**Qué es.** Detener servicios críticos (bases de datos, para poder cifrar sus archivos) o forzar reinicios.
**Detección.** Parada masiva de servicios de negocio antes del cifrado; `net stop`/`sc stop` en ráfaga; shutdown forzado.
**Mitigación.** Alertar sobre parada de servicios críticos; mínimo privilegio.

## T1498/T1499 — Network / Endpoint Denial of Service
**Qué es.** Saturar un servicio (DDoS) o agotar recursos de un endpoint para negar disponibilidad.
**Detección.** Picos de tráfico anómalos; agotamiento de conexiones/CPU; flujos desde muchas fuentes.
**Mitigación.** Anti-DDoS/CDN; rate-limiting; autoescalado; planes de respuesta.

## Referencias
- MITRE ATT&CK TA0040 (Impact).
- CISA — #StopRansomware (backups inmutables, segmentación, respuesta).
- Atomic Red Team — atomics T1486, T1490, T1485, T1489.
