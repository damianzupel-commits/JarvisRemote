---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A04 - Diseño Inseguro
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría nueva en el [[OWASP Top 10 - Resumen]] 2021. Distinta de las demás: no es "código con bug", es "el sistema hace exactamente lo que se diseñó que hiciera, y el diseño mismo es la falla". Ningún linter arregla esto — es un problema de threat modeling, no de sintaxis.

## Ejemplos concretos
- Flujo de recuperación de contraseña que permite intentos ilimitados de una pregunta de seguridad de baja entropía ("¿nombre de tu mascota?") sin rate limiting.
- Lógica de negocio que confía en que el cliente no va a mandar un precio negativo o una cantidad negativa en un carrito de compras (falta de validación de invariantes de negocio, no solo de tipo de dato).
- Arquitectura multi-tenant donde el aislamiento entre tenants depende de que el desarrollador se acuerde de filtrar por `tenant_id` en cada query, en vez de que el modelo de datos lo haga estructuralmente imposible de olvidar (ej. row-level security a nivel DB, o un scoping automático en el ORM).
- Feature de "recuperar cuenta por email" que no considera qué pasa si el atacante controla ese email temporalmente (won't-fix por diseño, ataque real contra varios servicios en el pasado).

## Qué puede hacer un auditor de código estático acá
Poco, en el sentido estricto de SAST. Pero sí es detectable con heurísticas y con revisión guiada:
- Buscar validaciones de invariantes de negocio ausentes cerca de operaciones monetarias/de cantidad (grep por `price`, `amount`, `quantity` sin chequeo de signo/rango cerca).
- Buscar límites de intentos (rate limiting) ausentes en endpoints de auth/recuperación — correlacionar con [[OWASP A07 - Fallas de Identificación y Autenticación]].
- Buscar filtros de tenant/owner faltantes de forma sistemática (no solo un endpoint) — señal de que el aislamiento no está garantizado por diseño, tema compartido con [[OWASP A01 - Control de Acceso Roto]].

## Mitigación
Threat modeling temprano (STRIDE es el framework más común), "secure design patterns" documentados y reusados en vez de reinventados por feature, y invariantes de negocio verificados en el borde del sistema (server-side), nunca solo confiando en el cliente. Ver también [[Defensa en Profundidad]].
