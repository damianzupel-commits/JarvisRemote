---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- concepto
title: Defensa en Profundidad
updated: '2026-07-28T00:00:00.000000+00:00'
---

Principio central de seguridad: **ningún sistema es "impenetrable"** — el objetivo no es una barrera perfecta (no existe), sino varias capas de control independientes, de forma que si una falla, las siguientes igual contienen el daño. Un sistema descrito como "impenetrable" es una señal de alarma, no de confianza: implica una sola capa de la que todo depende.

## Por qué "impenetrable" es el framing equivocado
Toda defensa individual tiene un modo de falla conocido o desconocido: una librería de validación tiene un bug, una regla de firewall se mal-configura, un secreto se filtra por accidente. Diseñar asumiendo que *una* capa nunca va a fallar es lo que convierte una falla puntual en una brecha total. Diseñar con defensa en profundidad asume que cada capa individual puede fallar, y pregunta "si esta falla, ¿qué me protege igual?".

## Ejemplo aplicado a un caso concreto: SSRF
Ver [[OWASP A10 - Server-Side Request Forgery (SSRF)]] para el detalle del bug. Las capas de defensa, ninguna suficiente por sí sola:
1. Allowlist de dominios permitidos en el código de la app (capa de aplicación).
2. Validación de que la IP resuelta no sea privada/interna, revalidada después de cada redirect (capa de aplicación, defensa contra bypass de la capa 1).
3. Egress firewall a nivel de red que bloquea que el proceso llegue a rangos de IP internos aunque el código de la app tenga un bug (capa de infraestructura, independiente del código).
4. Logging + alertas si el proceso intenta conectarse a un rango bloqueado (capa de detección — ver [[OWASP A09 - Fallas de Registro y Monitoreo de Seguridad]], permite notar el intento aunque las capas anteriores lo hayan contenido).

## Aplicado a auditoría de código (el rol de Jarvis)
Ninguna herramienta de [[Herramientas SAST y SCA - Resumen]] es completa por sí sola — Semgrep se pierde flujos interprocedurales que CodeQL sí sigue, Trivy/Snyk cubren dependencias pero no lógica propia, ningún SAST reemplaza a un humano revisando decisiones de diseño ([[OWASP A04 - Diseño Inseguro]]). Correr varias herramientas en capas (SAST rápido + SCA + dataflow profundo + revisión humana de hallazgos críticos) es aplicar el mismo principio al propio proceso de auditoría.

## Corolario práctico
Cuando se evalúa una mitigación propuesta para cualquier vulnerabilidad de esta base de conocimiento, la pregunta correcta no es "¿esto la arregla del todo?" sino "¿qué capas independientes tengo, y qué pasa si la más fuerte falla?". Esto aplica igual a [[Autenticación y Autorización]], [[Gestión de Secretos]] y [[Criptografía Aplicada: Qué NO Hacer]].
