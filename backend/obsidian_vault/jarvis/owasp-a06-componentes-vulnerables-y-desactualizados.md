---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
- sca
title: OWASP A06 - Componentes Vulnerables y Desactualizados
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #6 del [[OWASP Top 10 - Resumen]]. Es la categoría que corresponde por completo a **SCA (Software Composition Analysis)**, no a SAST — no es sobre el código que escribió el equipo, es sobre las dependencias de terceros que ese código importa (directas y transitivas).

## El problema
Un proyecto moderno tiene, típicamente, 10-100x más líneas de código en sus dependencias que en su propio código. Cada dependencia con una CVE conocida es una puerta de entrada, y la mayoría de los incidentes reales (Log4Shell, la brecha de Equifax vía Struts) fueron por una dependencia vulnerable **conocida** que no se actualizó a tiempo, no por un 0-day.

## Qué mirar en un repo
- Archivos de manifiesto de dependencias: `requirements.txt` / `pyproject.toml` / `Pipfile.lock` (Python), `package.json` / `package-lock.json` (JS/TS), `build.gradle` / `build.gradle.kts` (Kotlin/Android).
- Versiones fijadas a un release muy viejo (`django==1.11`, cualquier cosa end-of-life) o sin pin en absoluto (`requests` sin versión, arriesga traer una versión con CVE nueva en cada build).
- Lockfiles ausentes en el repo (sin `package-lock.json`/`poetry.lock` commiteado, cada build puede traer una versión distinta — no reproducible y no auditable).
- Dependencias transitivas: una directa "limpia" puede traer una transitiva vulnerable; herramientas de SCA resuelven el árbol completo, grep manual no alcanza.

## Herramientas
Esto es exactamente lo que hacen [[Trivy en la Práctica]] (escanea manifiestos y también imágenes de contenedor completas) y [[Snyk en la Práctica]] (fuerte en JS/npm y con la base de datos de vulns más curada del mercado). Semgrep en su tier gratuito no hace SCA real; Bandit tampoco — son SAST puro. CodeQL tampoco es SCA por diseño.

## Cómo priorizar findings de SCA (para no generar ruido)
No todas las CVEs de una dependencia importan igual:
1. ¿Es alcanzable? (¿el código del proyecto realmente llama a la función vulnerable, o es una función de la librería que nunca se usa?) — Trivy/Snyk con *reachability analysis* filtran esto.
2. Severidad (CVSS) + exploit disponible públicamente.
3. ¿Hay fix release disponible? Si no, mitigar con WAF/config en el ínterin.

## Mitigación
Actualizaciones automatizadas (Dependabot/Renovate), pin + lockfile siempre commiteado, y escaneo de SCA en CI, no solo local. Ver [[Herramientas SAST y SCA - Resumen]].
