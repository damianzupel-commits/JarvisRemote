---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- concepto
title: Autenticación y Autorización
updated: '2026-07-28T00:00:00.000000+00:00'
---

Dos conceptos que se confunden seguido pero son preguntas distintas, y confundirlas en el diseño de un sistema es en sí misma una fuente de bugs de seguridad.

## La distinción
- **Autenticación (AuthN)**: ¿quién sos? Verificar identidad — password, token, certificado, biometría, MFA.
- **Autorización (AuthZ)**: ¿qué podés hacer, siendo quien decís ser? Verificar permisos sobre una acción/recurso específico.

Un sistema puede tener autenticación perfecta y autorización rota (usuario correctamente identificado, pero puede leer datos de otro usuario — ver [[OWASP A01 - Control de Acceso Roto]]), o al revés (autorización bien diseñada pero la autenticación es fácil de falsear — ver [[OWASP A07 - Fallas de Identificación y Autenticación]]). Son fallas independientes con causas y fixes distintos.

## Modelos de autorización comunes
- **RBAC (Role-Based Access Control)**: permisos atados a roles (`admin`, `editor`, `viewer`), el usuario tiene uno o más roles. Simple de razonar, se vuelve rígido cuando los permisos necesitan granularidad por recurso individual.
- **ABAC (Attribute-Based Access Control)**: la decisión de permiso evalúa atributos del usuario, del recurso y del contexto (ej. "puede editar si es el owner del documento Y el documento no está archivado Y es horario laboral"). Más flexible, más complejo de auditar porque la lógica de la regla no está centralizada en una tabla simple.
- **ReBAC (Relationship-Based)**: el permiso depende de una relación entre entidades (ej. "puede ver el documento si está en la misma organización que el owner") — el modelo detrás de sistemas de permisos tipo Google Docs.

## Fallas de diseño comunes (más allá del bug puntual de código)
- **Autorización verificada en el cliente, no en el servidor**: el botón "borrar" solo se oculta en el frontend para usuarios sin permiso, pero el endpoint sigue aceptando la request igual si se llama directo. La UI nunca es una capa de seguridad, solo de UX — ver [[Defensa en Profundidad]].
- **Autorización *después* de traer el recurso**, en vez de *durante* la query (traer el objeto y recién ahí chequear ownership, en vez de filtrar por ownership en la query misma) — funcionalmente correcto pero más fácil de olvidar en un endpoint nuevo si no es el patrón consistente en todo el codebase.
- **Falta de deny-by-default**: un sistema donde agregar un endpoint nuevo es automáticamente accesible salvo que alguien agregue el chequeo de permiso a mano, en vez de ser inaccesible salvo que alguien lo habilite explícitamente. El primer diseño garantiza que tarde o temprano alguien se olvida.

## JWT: dónde suele fallar la autenticación basada en tokens
Ver ejemplo de código en [[OWASP A07 - Fallas de Identificación y Autenticación]]. Puntos de falla específicos de JWT: aceptar `alg: none`, no fijar explícitamente qué algoritmos son válidos al verificar (permite confusion attacks entre HS256/RS256), secret de firma débil o hardcodeado (ver [[Gestión de Secretos]]), y no verificar expiración (`exp`) o revocación (los JWT son difíciles de revocar por diseño — stateless — así que sesiones de larga duración necesitan una estrategia explícita de revocación, como una blocklist server-side).

## Principio general
Autorización centralizada y consistente (middleware/decorador reusado, no reimplementado a mano en cada endpoint), deny-by-default, y validación server-side siempre — sin excepciones "porque el cliente ya valida esto".
