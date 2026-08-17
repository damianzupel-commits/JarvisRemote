---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- deteccion
- pruebas
- atomic-red-team
- eicar
- emulacion
- defensa
title: 'Probar la Detección de Forma Segura - EICAR Atomic Red Team Emulación'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Nota transversal de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. **Un control que no se prueba se asume roto.** Acá: cómo validar que la detección funciona **sin ejecutar malware real ni causar daño**. Esto es lo que alimenta el estrés de detección nocturno del lab (ver `lab/DETECCION-ESTRES-NOCTURNO.md` y `lab/CYBER-RANGE-DESIGN.md` en el repo).

## EICAR — el "hola mundo" del antivirus
**Qué es.** Un archivo de texto estándar de la industria (EICAR Anti-Malware Test File), **inofensivo por diseño**, que todo AV reconoce como si fuera malware. Sirve para confirmar de punta a punta que el motor de firma está vivo y actúa (detecta → alerta → pone en cuarentena).
**Uso seguro.** No es malware: no hace nada. Solo dispara la firma. Es la primera prueba de humo de cualquier despliegue de AV.
**En Jarvis.** La regla `EICAR_Test_File` de `starter.yar` (severity `info`) está exactamente para esto: verificar que `yara_scanner.py` → `engine.scan_and_handle` → cuarentena funciona sin arriesgar nada. Es el smoke test del centinela.

## Atomic Red Team — pruebas atómicas mapeadas a ATT&CK
**Qué es.** Biblioteca open-source (Red Canary) de >1000 "pruebas atómicas": tests chicos, portables y reproducibles, cada uno mapeado a una técnica ATT&CK, que ejercitan **una** técnica en <5 minutos.
**Cómo funciona (conceptual).** Cada atómico trae un YAML/Markdown con prerequisitos, comando de setup y variantes. Se ejecuta la técnica de forma **controlada y benigna** (ej. crear una clave Run que apunta a un valor inocuo, volcar LSASS con una herramienta legítima sobre un sistema de laboratorio, generar tráfico HTTP a un endpoint de prueba) y se verifica si tu detección **dispara**. `Invoke-Atomic` orquesta la ejecución y la limpieza.
**Uso responsable (importante).**
- Correr **solo en laboratorio aislado** / cyber-range, nunca en producción sin autorización explícita.
- Muchos atómicos son intrusivos aunque benignos: **revertir** (cleanup) siempre; snapshot de VM antes.
- El objetivo es **medir detección**, no atacar: se mira si el SIEM/EDR alertó, no se busca impacto.
- Encaja con el guardrail de Jarvis: el scope de pentesting activo se valida contra `authorized_targets.yaml` (solo rangos privados/loopback por default). El cyber-range debe estar dentro de ese scope autorizado.

Cada nota de táctica de esta biblioteca cita el/los atómicos que ejercitan sus técnicas clave (ej. T1059.001 para PowerShell, T1003.001 para LSASS, T1486 para ransomware).

## Emulación de adversarios (nivel campaña)
**Qué es.** Encadenar técnicas para reproducir el comportamiento de un actor real de punta a punta (no una técnica suelta). Frameworks: MITRE Caldera (automatizado), planes de emulación de MITRE Engenuity, Atomic Red Team encadenado.
**Purple teaming.** Red (emula) y Blue (detecta) trabajan juntos: se ejecuta la técnica, se verifica si disparó la alerta, y si no, se escribe/afila la detección en el momento. Ciclo corto de mejora de cobertura.

## Otros recursos benignos de prueba
- **Cadenas de test estándar** anti-malware (equivalentes a EICAR para otros motores, ej. GTUBE para anti-spam).
- **Detonación en sandbox** de muestras reales **solo** en entorno aislado sin salida a producción (para análisis, no para "probar en vivo").

## Flujo recomendado para el estrés nocturno
1. Smoke test con EICAR → confirma que el motor de firma actúa (detecta + cuarentena).
2. Batería de atómicos por táctica en el cyber-range → mide qué técnicas se detectan y cuáles no (cobertura ATT&CK).
3. Registrar huecos (técnicas sin detección) como findings; afinar reglas.
4. Verificar la heurística conductual con un cifrador benigno de laboratorio (patrón de T1486) → confirma que `behavioral_watcher.py` dispara.
5. Snapshot/rollback del range entre corridas.

## Advertencia de seguridad
Estas pruebas son seguras **solo** en un entorno aislado y autorizado. Ejecutar atómicos intrusivos en producción, o descargar/detonar malware real fuera de un sandbox controlado, puede causar daño real y no está permitido. Ante la duda, EICAR y los atómicos con cleanup verificado son el piso seguro.

## Referencias
- EICAR — Anti-Malware Test File (estándar de la industria).
- Red Canary — Atomic Red Team (atomicredteam.io; github.com/redcanaryco/atomic-red-team) e Invoke-Atomic.
- MITRE — Caldera y planes de emulación de adversarios (Engenuity).
