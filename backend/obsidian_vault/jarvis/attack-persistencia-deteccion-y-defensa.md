---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- persistencia
- deteccion
- defensa
title: 'ATT&CK Persistencia - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0003**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **sobrevive a reinicios, cierres de sesión y cambios de credenciales** para mantener el acceso.

## T1547 — Boot or Logon Autostart Execution (Run keys, startup folder)
**Qué es.** Registrar código para que arranque solo al bootear o iniciar sesión.
**Uso del adversario (conceptual).** Añade una entrada a las claves `Run`/`RunOnce` del Registro o coloca un acceso directo en la carpeta Startup, apuntando a su binario.
**Detección.** Modificación de claves de autostart (Sysmon 12/13, Windows Registry auditing); binarios de autostart en rutas de usuario/temp; herramientas tipo Autoruns como baseline.
**Mitigación/endurecimiento.** Application control (WDAC/AppLocker); baseline de autostarts legítimos y alertar sobre cambios; mínimo privilegio (escribir estas claves de máquina requiere admin).
**Prueba atómica.** Atomic Red Team T1547.001 agrega una clave Run de prueba a un valor benigno para verificar que tu detección de modificación de Registro dispara (y la revierte).
**Capacidad Jarvis.** La regla `Suspicious_Persistence_Registry_Run_Key` de `starter.yar` matchea referencias a `...CurrentVersion\Run`/`RunOnce`; su meta advierte que sola no es concluyente (instaladores legítimos también las tocan) y debe combinarse con contexto — buen ejemplo de por qué firma sola no basta (ver [[Higiene de Detección - Firmas vs Comportamiento]]).

## T1053 — Scheduled Task/Job
**Qué es.** Tarea programada/cron que reejecuta el implante periódicamente o al arranque.
**Detección.** Windows 4698 (creación de tarea); `schtasks`/`at`; tareas apuntando a temp/appdata; cron nuevos.
**Mitigación.** Restringir creación de tareas; auditar y baseline.

## T1543 — Create or Modify System Process (servicios, daemons)
**Qué es.** Instalar un servicio de Windows o daemon systemd/launchd que arranque el implante como proceso del sistema.
**Detección.** Creación de servicios (Windows 7045); nuevos unit files en `/etc/systemd/system`; servicios que ejecutan desde rutas raras.
**Mitigación.** Application control; mínimo privilegio; monitorear creación/modificación de servicios.

## T1546 — Event Triggered Execution (WMI subs, image hijack, .bashrc)
**Qué es.** Enganchar la ejecución a un evento del sistema: suscripción WMI permanente, IFEO/Image File Execution Options, perfiles de shell (`.bashrc`, `.bash_profile`), COM hijacking.
**Detección.** Suscripciones WMI permanentes (Sysmon 19/20/21); cambios en IFEO; modificaciones de perfiles de shell; secuestro de CLSID COM.
**Mitigación.** Monitorear estos puntos específicos; application control; integridad de archivos de perfil.

## T1136 — Create Account / T1098 — Account Manipulation
**Qué es.** Crear cuentas nuevas o modificar existentes (agregar a grupos, sumar credenciales/keys) para tener otra puerta de entrada.
**Detección.** Creación de cuentas (Windows 4720); cambios de membresía de grupos privilegiados (4728/4732); nuevas SSH keys en `authorized_keys`; nuevas app passwords en la nube.
**Mitigación.** Alertar sobre altas de cuentas y cambios de grupos privilegiados; revisión periódica de cuentas; MFA.

## T1505.003 — Server Software Component: Web Shell
**Qué es.** Dejar un web shell en un servidor comprometido para reentrar vía HTTP.
**Detección.** Archivos web nuevos/modificados en el docroot; el proceso del servidor lanzando shells; patrones de webshell.
**Capacidad Jarvis.** La regla `Suspicious_PHP_Webshell` de `starter.yar` matchea patrones de webshell PHP (`eval(base64_decode(`, `system($_`, `$_POST['cmd']`, etc.). El file integrity monitoring (`integrity.py`) detecta el archivo nuevo en el docroot.
**Mitigación.** FIM sobre docroots; mínimo privilegio del servicio web; WAF.

## Referencias
- MITRE ATT&CK TA0003 (Persistence).
- Sysinternals Autoruns (baseline de puntos de autostart).
- Atomic Red Team — atomics T1547.*, T1053, T1543, T1546.*, T1136.
