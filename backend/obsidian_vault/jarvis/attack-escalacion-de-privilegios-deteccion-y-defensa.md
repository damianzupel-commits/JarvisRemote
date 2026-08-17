---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- escalacion-de-privilegios
- deteccion
- defensa
title: 'ATT&CK Escalación de Privilegios - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0004**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario pasa de **permisos limitados a permisos altos** (admin/SYSTEM/root). Muchas técnicas se solapan con [[ATT&CK Persistencia - Detección y Defensa]].

## T1548 — Abuse Elevation Control Mechanism (UAC bypass, sudo, setuid)
**Qué es.** Evadir los mecanismos que separan usuario normal de admin: bypass de UAC en Windows, abuso de `sudo`/setuid en Linux.
**Uso del adversario (conceptual).** Usa rutas legítimas mal configuradas o auto-elevación de binarios confiables para saltar el prompt de UAC, o explota reglas `sudo` laxas.
**Detección.** Procesos auto-elevados sin prompt; `fodhelper`/`eventvwr` con hijos anómalos (patrones de bypass UAC conocidos); ejecución de binarios setuid inusuales; edición de `/etc/sudoers`.
**Mitigación/endurecimiento.** UAC en el nivel más alto; quitar usuarios de admin local; `sudoers` mínimo y auditado; quitar bits setuid innecesarios.
**Prueba atómica.** Atomic Red Team T1548.002 ejercita técnicas de bypass de UAC conocidas en laboratorio para verificar detección.

## T1068 — Exploitation for Privilege Escalation
**Qué es.** Explotar una vulnerabilidad del kernel o de un driver/servicio privilegiado para ganar SYSTEM/root. *(No se documentan exploits.)*
**Detección.** Crashes de kernel anómalos; carga de drivers no firmados/vulnerables (BYOVD — "bring your own vulnerable driver", Sysmon 6); un proceso de bajo privilegio que de repente corre como SYSTEM.
**Mitigación.** Parcheo del SO y drivers; listas de bloqueo de drivers vulnerables (Microsoft Vulnerable Driver Blocklist / HVCI); mínimo privilegio.

## T1055 — Process Injection
**Qué es.** Inyectar código en un proceso legítimo (más privilegiado o más confiable) para heredar su contexto y esconderse. Cubre también evasión (ver [[ATT&CK Evasión de Defensas - Detección y Defensa]]).
**Uso del adversario (conceptual).** Escribe en la memoria de otro proceso y desvía su ejecución, para correr bajo un proceso de confianza sin tocar disco.
**Detección.** APIs de manipulación de memoria remota (CreateRemoteThread, WriteProcessMemory — Sysmon 8/10); regiones de memoria RWX en procesos que no deberían; hollowing (imagen en disco ≠ imagen en memoria). EDR con telemetría de memoria es clave.
**Mitigación.** EDR con protección de memoria; Attack Surface Reduction rules; Credential Guard/PPL para procesos sensibles.
**Prueba atómica.** Atomic Red Team T1055 incluye pruebas de inyección benignas (inyectan un payload inocuo, ej. abrir una calculadora) para verificar que tu EDR alerta la manipulación de memoria.

## T1134 — Access Token Manipulation
**Qué es.** Robar/duplicar/impersonar tokens de acceso para actuar como otro usuario más privilegiado.
**Detección.** Uso de APIs de tokens (DuplicateToken, ImpersonateLoggedOnUser); procesos con token de un usuario distinto al de la sesión; SeDebugPrivilege inusual.
**Mitigación.** Mínimo privilegio; separar cuentas admin; monitorear uso de privilegios sensibles.

## T1078 — Valid Accounts (privilegiadas)
**Qué es.** Usar credenciales de una cuenta que ya es privilegiada (robadas o default).
**Detección.** Uso de cuentas admin fuera de horario/host habitual; cuentas de servicio con logon interactivo.
**Mitigación.** PAM (privileged access management), tiering de cuentas admin, MFA, jump hosts.

## Referencias
- MITRE ATT&CK TA0004 (Privilege Escalation).
- Microsoft — Vulnerable Driver Blocklist / HVCI; recomendaciones UAC.
- Atomic Red Team — atomics T1548.*, T1055, T1134.
