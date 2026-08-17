---
author: jarvis
category: seguridad-triage
created: '2026-08-11T19:13:39.465575+00:00'
tags:
- triage-referencia
- ldapi
title: 'LDAP Injection (CWE-90): qué mitigación es válida y cuál no'
updated: '2026-08-11T19:13:39.465575+00:00'
---

## Qué es el problema real
LDAP Injection (CWE-90) pasa cuando un dato no confiable se concatena directo en un filtro de búsqueda LDAP (ej. `"(uid=" + userInput + ")"`), permitiendo que caracteres especiales de LDAP (`* ( ) \` y NUL) alteren la lógica del filtro.

## Mitigaciones que SÍ cuentan para esta categoría
- Escapar específicamente los caracteres especiales de LDAP con una función dedicada a esto (un encode real para LDAP, no una función genérica).
- Construir el filtro con una API programática que arme la consulta sin concatenar strings (evita el problema de raíz).

## Mitigaciones que NO cuentan para esta categoría (aunque estén presentes en el código)
- HTML-escaping -- no toca los metacaracteres de LDAP, son alfabetos de escape completamente distintos.
- Escapado/parametrización SQL -- protege un motor de consultas distinto, no protege LDAP.
- Validación genérica de "es alfanumérico" SIN que se haya confirmado explícitamente que excluye los metacaracteres de LDAP.

## Regla práctica
Si el valor llega a un filtro LDAP armado con concatenación de strings y la única sanitización visible es para otro sink (HTML, SQL) o es una validación genérica sin mención explícita de los caracteres de LDAP -- ES una vulnerabilidad real de esta categoría.