---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- deteccion
- defensa
- mitre-attack
- blue-team
- indice
- moc
title: 'Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Nota mapa de contenidos (MOC) de la **biblioteca de inteligencia de amenazas** de Jarvis, orientada a **detección y defensa (blue-team)**. Objetivo: tener contexto de adversario cargado **de antemano**, antes del estrés de detección nocturno (ver `lab/DETECCION-ESTRES-NOCTURNO.md` y `lab/CYBER-RANGE-DESIGN.md` en el repo), para que Jarvis no tenga que investigar desde cero en el momento.

## Encuadre y límite (leer antes de usar)

Esta biblioteca documenta cada técnica de adversario a nivel **inteligencia de amenazas / marco [[MITRE ATT&CK - Fundamentos del Marco]]**: qué hace, cómo la emplea *conceptualmente* el atacante, qué señales la delatan, cómo se **detecta**, cómo se **mitiga/endurece**, y qué **prueba atómica** ([[Probar la Detección de Forma Segura - EICAR Atomic Red Team Emulación]]) la ejercita.

**No** contiene: código de malware funcional, exploits armados, payloads listos para usar, ni pasos operativos para causar daño real. Es material **defensivo**. Donde una fuente trae PoC ofensivo, se resume el concepto y la detección — no se reproduce el arma. Este límite es deliberado (pedido de Damian) y no debe debilitarse.

## Cómo está organizada

Una nota por **táctica** de ATT&CK (el "por qué" del adversario), cada una con sus técnicas clave (el "cómo"). ATT&CK Enterprise tiene 14 tácticas; las dos pre-compromiso son Reconocimiento y **Resource Development** (preparación de infraestructura del atacante — dominios, cuentas, malware; se cubre brevemente dentro de [[ATT&CK Reconocimiento - Detección y Defensa]]). Las 13 tácticas del ciclo de intrusión:

### Pre-compromiso
- [[ATT&CK Reconocimiento - Detección y Defensa]] (TA0043) — recolección de información sobre el objetivo

### Acceso y ejecución
- [[ATT&CK Acceso Inicial - Detección y Defensa]] (TA0001) — cómo entra el adversario
- [[ATT&CK Ejecución - Detección y Defensa]] (TA0002) — cómo corre código en el host

### Consolidación
- [[ATT&CK Persistencia - Detección y Defensa]] (TA0003) — cómo se mantiene tras reinicios
- [[ATT&CK Escalación de Privilegios - Detección y Defensa]] (TA0004) — cómo gana permisos más altos
- [[ATT&CK Evasión de Defensas - Detección y Defensa]] (TA0005) — cómo evita ser detectado
- [[ATT&CK Acceso a Credenciales - Detección y Defensa]] (TA0006) — cómo roba usuarios/contraseñas

### Expansión
- [[ATT&CK Descubrimiento - Detección y Defensa]] (TA0007) — cómo mapea el entorno interno
- [[ATT&CK Movimiento Lateral - Detección y Defensa]] (TA0008) — cómo salta a otros hosts

### Objetivo
- [[ATT&CK Recolección - Detección y Defensa]] (TA0009) — cómo junta los datos de interés
- [[ATT&CK Comando y Control - Detección y Defensa]] (TA0011) — cómo se comunica con su infraestructura
- [[ATT&CK Exfiltración - Detección y Defensa]] (TA0010) — cómo saca los datos
- [[ATT&CK Impacto - Detección y Defensa]] (TA0040) — cómo destruye, cifra o interrumpe

## Notas transversales

- [[Familias de Malware - Taxonomía Detección y Defensa]] — virus, gusano, troyano, ransomware, spyware, rootkit, RAT, wiper, fileless, polimórfico: qué son, cómo se detectan, cómo defenderse.
- [[Hardening y Endurecimiento del Endpoint]] — reducción de superficie de ataque, buenas prácticas de configuración.
- [[Higiene de Detección - Firmas vs Comportamiento]] — cuándo sirve cada enfoque y por qué se combinan.
- [[Probar la Detección de Forma Segura - EICAR Atomic Red Team Emulación]] — cómo validar que la detección funciona sin ejecutar malware real.
- [[MITRE ATT&CK - Fundamentos del Marco]] — qué es ATT&CK, tácticas vs técnicas, cómo se lee una técnica.

## Conexión con las capacidades reales de Jarvis

El módulo `app/malware/` de Jarvis implementa varias de las detecciones que se describen acá: motor YARA (`yara_scanner.py` + reglas en `app/malware/rules/starter.yar`), ClamAV (`clamav_scanner.py`), heurística conductual de ransomware por entropía (`behavioral_watcher.py`), file integrity monitoring (`integrity.py`), monitor de procesos (`process_monitor.py`) y cuarentena reversible (`quarantine.py`). Cada nota de táctica enlaza a la capacidad concreta donde aplica. Ver también [[Cómo Jarvis Audita Seguridad de Código]] para el lado SAST/código.

## Fuentes de referencia (todas reconocidas)

- **MITRE ATT&CK** (attack.mitre.org) — tácticas, técnicas, detección y mitigación por técnica.
- **CISA / NSA / FBI** — guías conjuntas de detección (ej. "Identifying and Mitigating Living Off the Land Techniques").
- **Red Canary — Atomic Red Team** (atomicredteam.io) — pruebas atómicas mapeadas a ATT&CK.
- **CIS Benchmarks / NIST** — hardening y configuración segura.
