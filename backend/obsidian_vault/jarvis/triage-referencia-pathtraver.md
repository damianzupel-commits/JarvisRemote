---
author: jarvis
category: seguridad-triage
created: '2026-08-11T19:13:47.116892+00:00'
tags:
- triage-referencia
- pathtraver
title: 'Path Traversal (CWE-22): qué mitigación es válida y cuál no'
updated: '2026-08-11T19:13:47.116892+00:00'
---

## Qué es el problema real
Path Traversal (CWE-22) pasa cuando un dato no confiable se usa para construir una ruta de archivo, permitiendo que secuencias como `../` (o variantes codificadas) escapen del directorio esperado y accedan a archivos fuera de él.

## Mitigaciones que SÍ cuentan para esta categoría
- Canonicalizar la ruta resuelta (`getCanonicalPath()`/equivalente) y verificar explícitamente que el resultado sigue DENTRO de un directorio base permitido, comparando la ruta resuelta contra ese base -- mismo patrón que ya usa este propio proyecto (`_resolve()`/`FS_ALLOWED_ROOT`) para su propio sandboxing de filesystem.
- Usar una lista blanca de nombres de archivo permitidos en vez de aceptar cualquier path.
- Rechazar el input si contiene `..` o separadores de directorio ANTES de construir la ruta (frágil si es la única medida, pero válido como capa adicional).

## Mitigaciones que NO cuentan para esta categoría (aunque estén presentes en el código)
- HTML-escaping, escapado SQL -- no tienen nada que ver con la resolución de rutas de archivo.
- Verificar que el archivo "existe" -- no impide que la ruta resuelta esté fuera del directorio esperado.
- Chequear la extensión del archivo -- no impide traversal, un atacante puede seguir usando `../../etc/passwd` sin importar qué extensión "espere" el código.

## Regla práctica
Si el valor no confiable llega a un constructor de `File`/`Path` sin canonicalizar-y-verificar contra un directorio base, y la única protección visible es para otro sink -- ES una vulnerabilidad real de esta categoría.