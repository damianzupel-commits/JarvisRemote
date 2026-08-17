---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- ejecucion
- lolbins
- deteccion
- defensa
title: 'ATT&CK Ejecución - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0002**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **corre código controlado por él** en un sistema. Es la táctica más rica en telemetría: casi todo pasa por creación de procesos.

## T1059 — Command and Scripting Interpreter (PowerShell, cmd, bash, WScript, Python)
**Qué es.** Abuso de intérpretes ya presentes en el SO para ejecutar comandos y scripts.
**Uso del adversario (conceptual).** "Living off the land": usa binarios legítimos (PowerShell, `cmd`, `wscript`, `mshta`, `rundll32`) para no traer un ejecutable propio y mezclarse con actividad normal. Típicamente descarga y ejecuta la siguiente etapa en memoria (fileless — ver [[Familias de Malware - Taxonomía Detección y Defensa]]).
**Detección.** **Command-line logging** (Windows 4688 / Sysmon 1) y **PowerShell Script Block Logging (4104)** son la base. Señales: PowerShell con `-EncodedCommand`, `-ExecutionPolicy Bypass`, `-WindowStyle Hidden`, `DownloadString`/`IEX`; procesos de Office/`explorer` lanzando intérpretes; `wscript`/`mshta` ejecutando desde carpetas de usuario. Heurística de **process ancestry** (CISA/LOTL): ¿es normal que *este* padre lance *este* intérprete?
**Mitigación/endurecimiento.** PowerShell Constrained Language Mode; AMSI habilitado; application control (WDAC/AppLocker) para bloquear scripts no firmados; deshabilitar intérpretes innecesarios; logging verboso centralizado.
**Prueba atómica.** Atomic Red Team T1059.001 (PowerShell) incluye una prueba que ejecuta un one-liner **codificado en base64** para verificar si el EDR/Script Block Logging lo captura — sirve para validar detección, no para atacar.
**Capacidad Jarvis.** La regla `Suspicious_PowerShell_Obfuscation` de `starter.yar` requiere 3 de estos indicadores (`-enc`, `DownloadString`, `IEX(New-Object`, `-ExecutionPolicy Bypass`, `-WindowStyle Hidden`, `-NoProfile`) para reducir falsos positivos.

## T1204 — User Execution
**Qué es.** El adversario necesita que **el usuario haga clic/ejecute** el archivo malicioso (adjunto, LNK, instalador).
**Detección.** Ejecución desde carpetas de descargas/temp; archivos con Mark-of-the-Web ejecutados; doble extensión; LNK que lanza un intérprete.
**Mitigación.** Bloqueo de macros de Internet; filtrado de tipos peligrosos; concientización; application control. Enlaza con [[ATT&CK Acceso Inicial - Detección y Defensa]].

## T1047 — Windows Management Instrumentation (WMI)
**Qué es.** Uso de WMI para ejecutar comandos local o remotamente sin escribir a disco.
**Detección.** `wmic`/`WmiPrvSE.exe` lanzando procesos; consumidores de eventos WMI permanentes (también persistencia, T1546.003); Sysmon 19/20/21 (eventos WMI).
**Mitigación.** Restringir WMI remoto por firewall; application control; monitorear suscripciones WMI.

## T1053 — Scheduled Task/Job
**Qué es.** Crear tareas programadas/cron para ejecutar código (a menudo también persistencia — ver [[ATT&CK Persistencia - Detección y Defensa]]).
**Detección.** Creación de tareas (Windows 4698, `schtasks.exe`); tareas que apuntan a binarios en temp/appdata; cron jobs nuevos en `/etc/cron*`.
**Mitigación.** Restringir quién puede crear tareas; auditar tareas; baseline de tareas legítimas.

## T1569 — System Services / T1106 — Native API / T1129 — Shared Modules
**Qué es.** Ejecutar código creando servicios, llamando directo a la API del SO, o cargando DLLs.
**Detección.** Creación de servicios (Windows 7045); carga de DLL desde rutas inusuales (Sysmon 7); servicios que ejecutan desde temp.
**Mitigación.** Application control; mínimo privilegio; monitoreo de creación de servicios.

## T1204/T1059 en contenedores y nube
**Qué es.** Ejecución vía `kubectl exec`, contenedores maliciosos, o funciones serverless.
**Detección.** Auditoría de API de Kubernetes; imágenes no confiables; runtime security (Falco).
**Mitigación.** Admission controllers; imágenes firmadas; mínimo privilegio de pods.

## Referencias
- MITRE ATT&CK TA0002 (Execution).
- CISA/NSA/FBI — "Identifying and Mitigating Living Off the Land Techniques" (process ancestry, baselines, logging).
- Atomic Red Team — atomics T1059.*, T1047, T1053.
