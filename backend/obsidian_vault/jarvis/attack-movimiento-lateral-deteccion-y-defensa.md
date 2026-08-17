---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- movimiento-lateral
- deteccion
- defensa
title: 'ATT&CK Movimiento Lateral - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0008**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **salta de un host a otro** dentro de la red, casi siempre con credenciales válidas robadas (ver [[ATT&CK Acceso a Credenciales - Detección y Defensa]]).

## T1021 — Remote Services (RDP, SMB/Admin Shares, SSH, WinRM, DCOM)
**Qué es.** Usar protocolos de administración remota legítimos con credenciales robadas para acceder a otro host.
**Uso del adversario (conceptual).** Se autentica en el host destino como si fuera un admin: RDP interactivo, `PsExec` sobre SMB, WinRM, SSH.
**Detección.** Logins de red/tipo 3 y RDP/tipo 10 (Windows 4624) entre hosts que no suelen hablarse; uso de admin shares (`ADMIN$`, `C$`); creación de servicios remotos (patrón PsExec: servicio efímero + Windows 7045); WinRM (`wsmprovhost.exe`) inusual. Correlación de "cuenta que aparece en un host nuevo".
**Mitigación/endurecimiento.** Microsegmentación (host-to-host solo lo necesario); MFA en RDP; deshabilitar admin shares donde se pueda; LAPS (contraseña de admin local única por host, mata pass-the-hash lateral); tiering de cuentas admin; jump hosts.
**Prueba atómica.** Atomic Red Team T1021.001/T1021.002 ejecutan conexiones RDP/SMB controladas para validar la detección de movimiento entre hosts.

## T1550 — Use Alternate Authentication Material (Pass-the-Hash, Pass-the-Ticket)
**Qué es.** Autenticarse con el **hash** o el **ticket Kerberos** robado, sin conocer la contraseña en claro.
**Detección.** Logon NTLM con hash sin proceso de escritura de contraseña; tickets Kerberos reutilizados desde otro host; logon type 9 (NewCredentials) anómalo.
**Mitigación.** Credential Guard; LAPS; deshabilitar NTLM donde se pueda; cuentas admin sin logon interactivo en workstations.

## T1570 — Lateral Tool Transfer
**Qué es.** Copiar herramientas/implantes al host destino (vía SMB, admin shares, etc.).
**Detección.** Escritura de ejecutables en `ADMIN$`/`C$` de otro host; transferencia de binarios entre workstations. FIM + telemetría de red.
**Mitigación.** Bloquear escritura a admin shares; application control en destino; segmentación.

## T1563 — Remote Service Session Hijacking / T1072 — Software Deployment Tools
**Qué es.** Secuestrar sesiones RDP/SSH existentes, o abusar de herramientas de despliegue (SCCM, GPO, un RMM) para empujar código a muchos hosts a la vez.
**Detección.** Uso anómalo de la consola de despliegue; paquetes/GPO nuevos que ejecutan binarios raros; un RMM enviando comandos fuera de patrón.
**Mitigación.** MFA y mínimo privilegio en herramientas de despliegue (son objetivo de alto valor); auditar cambios de GPO/paquetes; segmentar el plano de administración.

## Referencias
- MITRE ATT&CK TA0008 (Lateral Movement).
- Microsoft — LAPS, Credential Guard, modelo de tiering administrativo.
- Atomic Red Team — atomics T1021.*, T1550.*, T1570.
