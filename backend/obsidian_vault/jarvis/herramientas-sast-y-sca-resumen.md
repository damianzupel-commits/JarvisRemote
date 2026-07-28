---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- herramienta
- sast
- sca
- indice
title: Herramientas SAST y SCA - Resumen
updated: '2026-07-28T00:00:00.000000+00:00'
---

Punto de entrada a las notas de herramientas. Distinción central que hay que tener clara — y que también aplica a la identidad de producto de [[Cómo Jarvis Audita Seguridad de Código]]: esto es tooling de **desarrollo/DevSecOps** (audita código fuente y dependencias antes/durante el desarrollo), **no** antivirus ni detección de malware (que analiza binarios ejecutables o comportamiento en runtime buscando payloads maliciosos conocidos).

## Las dos categorías
- **SAST (Static Application Security Testing)**: analiza el código fuente propio del proyecto sin ejecutarlo, buscando patrones de código vulnerable (los que están documentados en [[SQL Injection]], [[Cross-Site Scripting (XSS)]], etc.). Herramientas: [[Semgrep en la Práctica]], [[Bandit en la Práctica]], [[CodeQL en la Práctica]].
- **SCA (Software Composition Analysis)**: analiza las *dependencias de terceros* del proyecto (no el código propio) buscando CVEs conocidas en las versiones usadas — es el dominio de [[OWASP A06 - Componentes Vulnerables y Desactualizados]]. Herramientas: [[Trivy en la Práctica]], [[Snyk en la Práctica]] (Snyk hace ambas cosas, SAST y SCA).

## Tabla comparativa rápida
| Herramienta | Tipo | Fuerte en | Setup |
|---|---|---|---|
| [[Semgrep en la Práctica]] | SAST | Multi-lenguaje, reglas custom rápidas de escribir | Muy bajo, sin compilar el proyecto |
| [[Bandit en la Práctica]] | SAST | Python específicamente | Muy bajo |
| [[CodeQL en la Práctica]] | SAST | Flujo de datos real (taint tracking), menos falsos positivos en casos complejos | Alto, necesita compilar/indexar el proyecto |
| [[Trivy en la Práctica]] | SCA + misconfig | Dependencias + imágenes de contenedor + IaC, todo en una herramienta | Bajo |
| [[Snyk en la Práctica]] | SCA (+ SAST) | Ecosistema npm/JS, base de datos de vulns curada, reachability analysis | Bajo (requiere cuenta/token para features completas) |

## Cómo se complementan (no son sustitutas entre sí)
Un pipeline de seguridad de código completo típicamente corre **varias** de estas juntas, no una sola:
1. SAST rápido en cada commit/PR (Semgrep + linter específico de lenguaje: Bandit para Python, ShellCheck para shell, PSScriptAnalyzer para PowerShell — ver [[Seguridad en Python]], [[Seguridad en Shell y Bash]], [[Seguridad en PowerShell]]).
2. SCA en cada build (Trivy/Snyk) para pescar CVEs nuevas en dependencias que ya estaban en el repo (una dependencia "limpia" ayer puede tener una CVE publicada hoy).
3. CodeQL (u otro motor de dataflow) en CI, más lento pero con mejor señal para bugs de lógica de flujo de datos que las reglas sintácticas se pierden.
4. Escaneo de secretos (Gitleaks/TruffleHog, o las reglas de secretos integradas en Semgrep) como pre-commit hook además de en CI — ver [[Secretos Hardcodeados en Código]].

## Priorización de findings (para no ahogar a nadie en ruido)
Ningún scanner tiene cero falsos positivos. Orden de triage recomendado: severidad (crítico/alto primero) → alcanzabilidad real (¿el código llega a ejecutar ese sink con input controlable, o es teórico?) → si es una dependencia, ¿hay fix disponible ya? Cada nota de herramienta tiene su propia sección de "falsos positivos comunes" para ese scanner específico.
