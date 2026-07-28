---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- playbook
title: Cómo Jarvis Audita Seguridad de Código
updated: '2026-07-28T00:00:00.000000+00:00'
---

Nota operativa. Define el rol de "Fase 1" del roadmap: Jarvis como centinela de seguridad de código 24/7, en la línea de Semgrep/Bandit/Trivy/Snyk/CodeQL. **Alcance explícito, para no confundir la identidad de producto**: esto es auditoría de **seguridad de código fuente / DevSecOps** — código propio y dependencias, antes o durante el desarrollo. **No** es detección de malware ni antivirus (análisis de binarios/comportamiento en runtime buscando payloads maliciosos) — esa es una categoría de producto completamente distinta y no la que se persigue acá.

## Flujo de trabajo al auditar un repo o un cambio de código
1. **Identificar lenguajes presentes** (lo que ya hace el indexador de Codebase: Python, Kotlin, JS/TS, PowerShell, Shell) → ir directo a la nota de lenguaje correspondiente para la lista de antipatrones específicos: [[Seguridad en Python]], [[Seguridad en JavaScript y TypeScript]], [[Seguridad en Kotlin y Android]], [[Seguridad en PowerShell]], [[Seguridad en Shell y Bash]].
2. **Elegir herramienta(s) según lenguaje y tipo de check** — no correr todo siempre, elegir según lo que aplica (ver tabla abajo).
3. **Mapear cada finding a su categoría** — CWE/patrón → nota de [[OWASP Top 10 - Resumen]] o de vulnerabilidad específica ([[SQL Injection]], [[Command Injection]], etc.) para dar contexto y mitigación concreta en la respuesta, no solo el nombre de la regla que disparó.
4. **Priorizar antes de reportar** (ver sección de priorización abajo) — no volcar los findings crudos, filtrar ruido conocido primero.
5. **Reportar con severidad + ubicación + mitigación concreta**, no solo "se encontró un problema" — cada nota de vulnerabilidad de esta base tiene el ejemplo vulnerable → seguro listo para reusar en la respuesta.

## Qué herramienta correr según lenguaje (tabla de decisión rápida)
| Lenguaje | SAST primario | SAST secundario / dataflow | SCA |
|---|---|---|---|
| Python | [[Bandit en la Práctica]] | [[Semgrep en la Práctica]] → [[CodeQL en la Práctica]] si hace falta seguir flujo entre funciones | [[Trivy en la Práctica]] / [[Snyk en la Práctica]] sobre `requirements.txt`/`pyproject.toml` |
| JS/TS | [[Semgrep en la Práctica]] (rulesets `p/react`, `p/node`) | [[CodeQL en la Práctica]] | [[Snyk en la Práctica]] (fuerte en npm) |
| Kotlin/Android | [[Semgrep en la Práctica]] (`p/kotlin`, `p/java`) | [[CodeQL en la Práctica]] | [[Trivy en la Práctica]] / [[Snyk en la Práctica]] sobre `build.gradle*` |
| PowerShell | PSScriptAnalyzer (ver [[Seguridad en PowerShell]]) | — | — |
| Shell/Bash | ShellCheck (ver [[Seguridad en Shell y Bash]]) | — | — |
| Contenedores/IaC | [[Trivy en la Práctica]] (`trivy config`) | — | [[Trivy en la Práctica]] (`trivy image`) |
| Secretos (cualquier lenguaje) | Gitleaks/TruffleHog, o reglas de secretos de [[Semgrep en la Práctica]]/[[Trivy en la Práctica]] | — | — |

## Cómo priorizar findings (para que la respuesta sea útil, no ruido)
Orden de triage, de mayor a menor prioridad real:
1. **Secreto hardcodeado real** ([[Secretos Hardcodeados en Código]]) — siempre máxima prioridad, impacto inmediato y de explotación trivial.
2. **Sink de inyección con fuente claramente no confiable y sin sanitización en el medio** (SQLi/command injection/SSTI con input de request directo al sink) — alta confianza, alto impacto.
3. **CVE de dependencia con severidad crítica/alta Y fix disponible** — bajo esfuerzo de arreglo, alto impacto si no se hace.
4. **Findings de baja confianza o alcanzabilidad dudosa** (ver secciones de falsos positivos de cada nota de herramienta: [[Bandit en la Práctica]], [[Semgrep en la Práctica]], [[Snyk en la Práctica]], [[Trivy en la Práctica]]) — mencionar pero no bloquear ni alarmar de más.
5. **Problemas de diseño/arquitectura** ([[OWASP A04 - Diseño Inseguro]], [[Autenticación y Autorización]] mal centralizada) — señalar como observación, no como "finding" puntual con línea exacta, porque requieren juicio humano de todas formas.

## Regla de comunicación
Nunca reportar un hallazgo de seguridad sin (a) explicar el escenario concreto de explotación en una frase, y (b) dar el fix concreto (código, no solo "sanitizar el input") — el objetivo es que la persona que lee el reporte pueda actuar en minutos, no que tenga que ir a investigar qué significa el finding. Ver [[Defensa en Profundidad]] para el framing correcto al proponer mitigaciones: nunca prometer que algo queda "impenetrable", sí explicar qué capas se están agregando y por qué.
