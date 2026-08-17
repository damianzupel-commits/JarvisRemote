---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- descubrimiento
- deteccion
- defensa
title: 'ATT&CK Descubrimiento - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0007**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario, **ya dentro**, mapea el entorno: qué host es, qué hay en la red, quién es quién. Casi todo se hace con utilidades nativas (LOTL), así que la clave defensiva es la **anomalía de contexto**, no la firma.

## T1087 — Account Discovery / T1069 — Permission Groups Discovery
**Qué es.** Enumerar usuarios, grupos y admins del dominio (`net user`, `net group`, `whoami /groups`, consultas LDAP/AD).
**Uso del adversario (conceptual).** Identifica cuentas privilegiadas objetivo para el próximo salto.
**Detección.** `net.exe`/`net1.exe`, `whoami`, `dsquery` desde hosts/usuarios que normalmente no los corren; consultas LDAP masivas (herramientas tipo BloodHound generan patrones reconocibles).
**Mitigación.** Reducir enumeración anónima de AD; monitorear reconnaissance LDAP; process ancestry.

## T1082 — System Information Discovery / T1016 — System Network Configuration
**Qué es.** Recolectar info del host y su red (`systeminfo`, `ipconfig`, `hostname`, `uname -a`, `ifconfig`).
**Detección.** Ráfaga de comandos de descubrimiento en corto tiempo desde un mismo proceso padre (patrón muy típico post-explotación).
**Mitigación.** Baseline de qué host corre estos comandos normalmente; alertar sobre ráfagas.
**Prueba atómica.** Atomic Red Team T1082/T1016 ejecutan estos comandos benignos en secuencia para validar que tu correlación de "ráfaga de discovery" dispara.

## T1046 — Network Service Discovery / T1018 — Remote System Discovery
**Qué es.** Escanear la red interna en busca de hosts y servicios (barridos, `nmap` interno, ARP scan).
**Detección.** Un host interno conectando a muchos otros hosts/puertos en poco tiempo (escaneo lateral); tráfico SMB/RPC de mapeo. Se ve en flujos de red (NetFlow/Zeek).
**Mitigación.** Microsegmentación; deception (honeypots que alertan al primer toque); IDS interno. Ver [[Fundamentos de Nmap y Tipos de Escaneo]] para entender el lado del escaneo.

## T1057 — Process Discovery / T1518 — Software Discovery (incl. security software)
**Qué es.** Listar procesos y software instalado, en especial **buscar el AV/EDR** para decidir cómo evadirlo.
**Detección.** `tasklist`/`ps` seguido de consultas por nombres de productos de seguridad; enumeración de servicios de seguridad. Enlaza con [[ATT&CK Evasión de Defensas - Detección y Defensa]].
**Mitigación.** Tamper protection; ocultar/renombrar no ayuda mucho — mejor detectar el intento de enumeración.

## T1083 — File and Directory Discovery / T1135 — Network Share Discovery
**Qué es.** Recorrer el sistema de archivos y descubrir shares de red buscando datos de valor.
**Detección.** Enumeración recursiva masiva de directorios; `net view`/`net share`; acceso a muchos shares en poco tiempo.
**Mitigación.** Mínimo privilegio sobre shares; auditar acceso a shares sensibles; canary files.

## Referencias
- MITRE ATT&CK TA0007 (Discovery).
- CISA/NSA/FBI — LOTL (baselines y process ancestry para distinguir discovery malicioso de administración legítima).
- Atomic Red Team — atomics T1087, T1082, T1046, T1057, T1518, T1083.
