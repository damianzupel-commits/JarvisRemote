---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- indice
title: OWASP Top 10 - Resumen
updated: '2026-07-28T00:00:00.000000+00:00'
---

El OWASP Top 10 (edición 2021, la vigente) es la lista de referencia de las categorías de riesgo más críticas en aplicaciones web. No es una lista de vulnerabilidades puntuales sino de *categorías* — cada una agrupa varios CWE (Common Weakness Enumeration) relacionados. Es el marco de clasificación que [[Cómo Jarvis Audita Seguridad de Código]] usa para etiquetar findings.

| # | Categoría | Nota detallada |
|---|---|---|
| A01 | Broken Access Control (la más prevalente en 2021) | [[OWASP A01 - Control de Acceso Roto]] |
| A02 | Cryptographic Failures | [[OWASP A02 - Fallas Criptográficas]] |
| A03 | Injection (incluye XSS desde 2021) | [[OWASP A03 - Injection]] |
| A04 | Insecure Design | [[OWASP A04 - Diseño Inseguro]] |
| A05 | Security Misconfiguration | [[OWASP A05 - Configuración de Seguridad Incorrecta]] |
| A06 | Vulnerable and Outdated Components | [[OWASP A06 - Componentes Vulnerables y Desactualizados]] |
| A07 | Identification and Authentication Failures | [[OWASP A07 - Fallas de Identificación y Autenticación]] |
| A08 | Software and Data Integrity Failures | [[OWASP A08 - Fallas de Integridad de Software y Datos]] |
| A09 | Security Logging and Monitoring Failures | [[OWASP A09 - Fallas de Registro y Monitoreo de Seguridad]] |
| A10 | Server-Side Request Forgery (SSRF) | [[OWASP A10 - Server-Side Request Forgery (SSRF)]] |

## Por qué importa para auditoría de código (vs. pentesting de app corriendo)
El Top 10 nació pensado en aplicaciones desplegadas, pero la mayoría de las categorías son detectables *estáticamente*, leyendo código fuente, que es el trabajo real de [[Herramientas SAST y SCA - Resumen]]:
- A01, A03, A07, A10 → altamente detectables con SAST (patrones de código: falta de chequeo de ownership, concatenación de queries, comparación de passwords, requests con URL controlada por el usuario).
- A02, A08 → mixto: algo es estático (algoritmos débiles hardcodeados, falta de verificación de firmas) y algo requiere config/infra.
- A06 → es directamente el dominio de SCA (Software Composition Analysis: [[Trivy en la Práctica]], [[Snyk en la Práctica]]), no SAST.
- A04, A05, A09 → mayormente arquitectura/config, más difícil de capturar con reglas de patrón, pero algunas heurísticas sirven (ej. debug=True hardcodeado es A05).

## Relación con vulnerabilidades específicas
Las categorías del Top 10 son paraguas. El detalle concreto — el código vulnerable línea por línea — vive en las notas de [[SQL Injection]], [[Cross-Site Scripting (XSS)]], [[Command Injection]], [[Path Traversal]], [[Insecure Deserialization]], [[XXE - XML External Entity]], [[SSTI - Server-Side Template Injection]] y [[Secretos Hardcodeados en Código]].
