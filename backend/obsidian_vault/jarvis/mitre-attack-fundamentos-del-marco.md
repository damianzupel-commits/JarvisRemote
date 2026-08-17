---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- deteccion
- defensa
- fundamentos
title: 'MITRE ATT&CK - Fundamentos del Marco'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]].

**MITRE ATT&CK** (Adversarial Tactics, Techniques, and Common Knowledge) es una base de conocimiento pública de comportamiento de adversarios basada en observaciones del mundo real. No es una lista de vulnerabilidades (eso es CVE/CWE, ver [[CWE Top 25 Most Dangerous Software Weaknesses]]); es un catálogo de **lo que hacen los atacantes una vez que actúan**.

## Tácticas vs técnicas vs procedimientos

- **Táctica** = el *por qué*, el objetivo del adversario en una fase (ej. "Persistencia"). ATT&CK Enterprise tiene 14 tácticas.
- **Técnica** = el *cómo* general se logra ese objetivo (ej. T1547 "Boot or Logon Autostart Execution"). Hay ~200 técnicas y ~450 subtécnicas.
- **Subtécnica** = una variante más específica (ej. T1547.001 "Registry Run Keys / Startup Folder").
- **Procedimiento** = la implementación concreta que usa un grupo/malware puntual.

Cada técnica en attack.mitre.org trae: descripción, grupos/software que la usan, **Detection** (qué telemetría la delata) y **Mitigations** (cómo prevenirla). Esta biblioteca reusa ese esquema por técnica.

## Las tres matrices

**Enterprise** (Windows/Linux/macOS/Cloud/Contenedores — la que usa esta biblioteca), **Mobile** e **ICS** (sistemas de control industrial).

## Cómo se usa en el lado defensivo (blue-team)

1. **Mapeo de cobertura**: para cada técnica, ¿tengo telemetría y una regla que la detecte? Se pinta en un "ATT&CK Navigator" (verde = cubierto, rojo = ciego).
2. **Detection engineering**: escribir reglas de detección referenciando la técnica que cubren.
3. **Emulación de adversarios**: ejercitar técnicas de forma controlada (ver [[Probar la Detección de Forma Segura - EICAR Atomic Red Team Emulación]]) y verificar que la detección dispara.
4. **Priorización**: no todas las técnicas son igual de comunes; se priorizan las más observadas (ej. T1059 Command and Scripting Interpreter, T1055 Process Injection, T1003 OS Credential Dumping).

## Data sources: sin telemetría no hay detección

ATT&CK modela también las **fuentes de datos** que hacen visible cada técnica. Las más valiosas en un endpoint Windows: **creación de procesos con línea de comando** (Sysmon Event ID 1 / Windows 4688 con command line auditing), **carga de módulos/DLL** (Sysmon 7), **modificación de Registro** (Sysmon 12/13), **conexiones de red por proceso** (Sysmon 3), **creación de archivos** (Sysmon 11) y logs de **PowerShell Script Block Logging** (4104). Sin estas fuentes activadas, la mayoría de las detecciones de esta biblioteca son ciegas. Ver [[Hardening y Endurecimiento del Endpoint]].

## Referencias

- MITRE ATT&CK — https://attack.mitre.org (matrices, tácticas, técnicas).
- MITRE — "Getting Started with ATT&CK".
