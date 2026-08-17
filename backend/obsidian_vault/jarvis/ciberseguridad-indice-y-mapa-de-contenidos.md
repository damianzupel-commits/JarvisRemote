---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- indice
- moc
title: 'Ciberseguridad: Índice y Mapa de Contenidos'
updated: '2026-07-28T00:00:00.000000+00:00'
---

Nota mapa de contenidos (MOC) de toda la base de conocimiento de ciberseguridad. Objetivo: que Jarvis pueda navegar rápido desde acá a la nota específica que necesita, sin tener que releer todo. Alcance explícito: **seguridad de código fuente / DevSecOps (SAST, SCA, secure coding)**, en la línea de Semgrep, Bandit, Trivy, Snyk, CodeQL. **No** es sobre detección de malware ni antivirus — esa es una categoría de producto distinta y no la que persigue [[Cómo Jarvis Audita Seguridad de Código]].

## Fundamentos y conceptos transversales
- [[Defensa en Profundidad]] — principio general, reemplaza cualquier idea de sistema "impenetrable"
- [[Autenticación y Autorización]]
- [[Gestión de Secretos]]
- [[Criptografía Aplicada: Qué NO Hacer]]

## OWASP Top 10 (2021)
- [[OWASP Top 10 - Resumen]] — punto de entrada a las 10 categorías
  - [[OWASP A01 - Control de Acceso Roto]]
  - [[OWASP A02 - Fallas Criptográficas]]
  - [[OWASP A03 - Injection]]
  - [[OWASP A04 - Diseño Inseguro]]
  - [[OWASP A05 - Configuración de Seguridad Incorrecta]]
  - [[OWASP A06 - Componentes Vulnerables y Desactualizados]]
  - [[OWASP A07 - Fallas de Identificación y Autenticación]]
  - [[OWASP A08 - Fallas de Integridad de Software y Datos]]
  - [[OWASP A09 - Fallas de Registro y Monitoreo de Seguridad]]
  - [[OWASP A10 - Server-Side Request Forgery (SSRF)]]

## Tipos de vulnerabilidad (deep dives, con ejemplos de código)
- [[SQL Injection]]
- [[Cross-Site Scripting (XSS)]]
- [[Command Injection]]
- [[Path Traversal]]
- [[Insecure Deserialization]]
- [[XXE - XML External Entity]]
- [[SSTI - Server-Side Template Injection]]
- [[Secretos Hardcodeados en Código]]

## Seguridad por lenguaje (cruzado con lo que indexa Codebase)
- [[Seguridad en Python]]
- [[Seguridad en JavaScript y TypeScript]]
- [[Seguridad en Kotlin y Android]]
- [[Seguridad en PowerShell]]
- [[Seguridad en Shell y Bash]]

## Herramientas SAST / SCA
- [[Herramientas SAST y SCA - Resumen]] — cuándo usar cada una
  - [[Semgrep en la Práctica]]
  - [[Bandit en la Práctica]]
  - [[Trivy en la Práctica]]
  - [[Snyk en la Práctica]]
  - [[CodeQL en la Práctica]]

## Operativo
- [[Cómo Jarvis Audita Seguridad de Código]] — playbook: qué mirar primero, qué tool correr según lenguaje, cómo priorizar findings

## Áreas relacionadas (otros MOC)
- [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]] — el lado **detección/defensa (blue-team)** por táctica MITRE ATT&CK, familias de malware y hardening. Categoría distinta a esta (que es secure-code/SAST), pero complementaria.

## Convención de tags de esta base
`seguridad` (todas) · `owasp` · `vulnerabilidad` · `sast` / `sca` · `herramienta` · tag por lenguaje (`python`, `javascript`, `typescript`, `kotlin`, `android`, `powershell`, `shell`) · `concepto` · `playbook`
