---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A03 - Injection
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #3 del [[OWASP Top 10 - Resumen]]. Desde 2021 incluye a XSS (antes era su propia categoría A7 en 2017). Es la categoría con más CWEs mapeados (33) y la más "clásica" para SAST — patrón de dato no confiable llegando a un sink peligroso sin sanitizar.

## El patrón raíz: fuente → sink sin sanitización
Toda inyección es la misma forma: **datos controlados por el atacante (fuente) llegan a una función que interpreta ese dato como código/comando/query (sink), sin validación ni escape en el medio**. Esto es exactamente lo que rastrea el *taint analysis* de [[CodeQL en la Práctica]] y lo que aproximan con reglas sintácticas [[Semgrep en la Práctica]] y [[Bandit en la Práctica]].

## Subtipos con nota propia (con ejemplos de código)
- [[SQL Injection]] — el caso más común, sink = motor de base de datos
- [[Cross-Site Scripting (XSS)]] — sink = DOM/HTML del navegador
- [[Command Injection]] — sink = shell del sistema operativo
- [[XXE - XML External Entity]] — sink = parser XML
- [[SSTI - Server-Side Template Injection]] — sink = motor de templates
- Path Traversal es técnicamente una variante (sink = filesystem) — ver [[Path Traversal]]
- LDAP Injection, NoSQL Injection: mismo patrón que SQL Injection pero contra `ldap3`/consultas Mongo (`$where`, operadores con input directo del usuario) — no tienen nota propia, tratarlas como variante de [[SQL Injection]].

## Regla general de mitigación
Nunca construir el string interpretado por el sink con concatenación/interpolación de input del usuario. Preferir siempre APIs que separan código de datos: prepared statements (SQL), `subprocess` con lista de args y `shell=False` (comandos), auto-escaping del template engine activado (HTML), parsers XML con entidades externas deshabilitadas.

## Por qué es "fácil" para SAST y por qué igual hay falsos negativos
Es fácil detectar el *sink* peligroso (`cursor.execute(f"...")`, `os.system(...)`, `innerHTML = ...`). Es difícil saber con certeza si el dato que llega ahí es realmente controlable por un atacante — eso requiere seguir el flujo desde el input HTTP/CLI hasta el sink, que es justamente donde CodeQL (motor de flujo de datos real) le gana a Semgrep/Bandit (mayormente basados en patrones locales, aunda Semgrep sí soporta dataflow entre-procedural en su versión Pro).
