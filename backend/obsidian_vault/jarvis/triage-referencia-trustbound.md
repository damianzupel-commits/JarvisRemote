---
author: jarvis
category: seguridad-triage
created: '2026-08-11T19:13:31.412329+00:00'
tags:
- triage-referencia
- trustbound
title: 'Trust Boundary Violation (CWE-501): qué mitigación es válida y cuál no'
updated: '2026-08-11T19:13:31.412329+00:00'
---

## Qué es el problema real
Trust Boundary Violation (CWE-501) NO es "el dato se muestra mal" ni "el dato rompe una consulta" -- es que un dato que viene de una fuente NO CONFIABLE (un parámetro HTTP, un header, un input de usuario) se guarda en una estructura que el resto del sistema trata como CONFIABLE (típicamente la sesión HTTP, `HttpSession.setAttribute`/`putValue`) sin validarlo antes de cruzar esa frontera. El problema es el CRUCE en sí, no lo que pase con el dato después en otro punto del flujo.

## Mitigaciones que SÍ cuentan para esta categoría
- Validar el valor contra una lista blanca / formato esperado ANTES de guardarlo en la sesión.
- No guardar el dato tal cual en la sesión -- guardar solo un identificador/referencia ya validado, y resolver el valor real desde una fuente confiable.
- Re-validar el valor en cada punto donde se LEE de la sesión, tratándolo como si siguiera siendo no confiable.

## Mitigaciones que NO cuentan para esta categoría (aunque estén presentes en el código)
- **HTML-escaping** (`StringEscapeUtils.escapeHtml`, `encodeForHTML`, etc.) -- mitiga XSS (que el dato se renderice como código en el navegador), NO mitiga que el dato haya cruzado la frontera de confianza sin validar. Son problemas distintos sobre el mismo dato.
- Parametrización SQL / `PreparedStatement` -- mitiga SQL injection, no trust boundary.
- Logging o auditoría del valor -- no es una mitigación, es solo registro.
- Cualquier sanitización pensada para OTRO sink (HTML, SQL, shell) que no sea específicamente "esto ya fue validado antes de guardarse en la sesión".

## Regla práctica
Si ves `session.setAttribute(...)`/`session.putValue(...)` con un valor que viene directo de un parámetro HTTP, y la única "protección" visible es escapado para HTML o similar -- ES una vulnerabilidad real de esta categoría. El escapado para otro sink no absuelve el cruce de frontera sin validar.