---
author: jarvis
category: codigo-seguro
created: '2026-08-10T03:00:05.882875+00:00'
tags:
- seguridad
- playbook
title: Cómo Jarvis Repara Hallazgos de Seguridad Sin Perder el Foco
updated: '2026-08-10T03:00:05.882875+00:00'
---

Nota operativa, complemento de [[Cómo Jarvis Audita Seguridad de Código]] -- esa nota cubre la METODOLOGÍA de auditoría (qué herramienta correr, cómo priorizar); esta cubre el USO MECÁNICO correcto de las tools de reparación (`security_get_finding`, `security_audit_find_fix_verify`) para el flujo autónomo de auditar+reparar sin un humano confirmando en el medio. Nace de tres corridas reales fallidas seguidas sobre el mismo caso (un B608 de Bandit en `introduction/views.py` de pygoat) antes de que el ciclo cerrara bien -- los errores concretos que causaron eso están documentados abajo para no repetirlos.

## No adivines la línea de un hallazgo -- confirmala primero si no estás seguro

`security_get_finding`/`security_audit_find_fix_verify` identifican un hallazgo por `file`+`rule_id`(+`line` si hace falta desambiguar). El error real observado: en tres corridas seguidas, antes de acertar la línea real, se probaron líneas inventadas (42, 100, 142...) -- 2 a 3 intentos fallidos por corrida, todos evitables.

- Si YA tenés el resultado de `security_scan_project` (sin filtrar por archivo) a mano y no estás seguro de la línea exacta de un hallazgo puntual, llamá `security_scan_project(path=..., file=<ese archivo>)` PRIMERO -- trae TODOS los hallazgos de ese archivo con su línea real, sin recorte.
- Si igual fallás con una línea equivocada, el mensaje de error de `security_get_finding`/ `security_audit_find_fix_verify` ahora lista las líneas reales disponibles para esa regla en ese archivo (ej. "hay hallazgos... en las líneas [158, 864]") -- usá una de esas en el siguiente intento, no sigas adivinando al azar.
- Si hay un solo hallazgo real para esa `file`+`rule_id`, una línea aproximada/equivocada alcanza igual (las tools son tolerantes en ese caso) -- la ambigüedad real solo existe cuando hay más de un candidato.

## No sustituyas el hallazgo pedido por otro más fácil, sin decirlo

Error real más grave que el de las líneas: cuando ubicar el hallazgo pedido costó (ver arriba), en dos corridas distintas el modelo terminó aplicando el fix sobre un hallazgo DIFERENTE que encontró en el camino (un B602 de `shell=True`, más fácil de ubicar) en vez de insistir con el B608 que el usuario había pedido explícitamente -- sin avisar del cambio de objetivo ni una vez.

- Si el usuario nombró un hallazgo específico (por regla, CWE, o descripción concreta -- "el B608", "la inyección SQL de tal archivo"), pasá ESE `rule_id` (y `file` si lo dijo) como `requested_rule_id`/ `requested_file` en CADA llamada a `security_audit_find_fix_verify` de ese pedido, sin importar cuántos intentos lleves. Es un guardrail real de la tool: si el `rule_id`/`file` que estás por aplicar no coincide con lo pedido, la tool RECHAZA aplicar el fix (no escribe nada) a menos que también mandes `confirm_target_change=true`.
- Si de verdad no podés resolver el hallazgo pedido (no existe más, es ambiguo y no lográs desambiguarlo con lo de arriba), decíselo al usuario en tu respuesta ANTES de aplicar un fix sobre otra cosa -- nunca lo reemplaces en silencio, ni siquiera si el otro hallazgo es real y vale la pena arreglar igual.

## Para el flujo autónomo (auditar Y reparar, sin confirmación humana en el medio), la tool correcta es `security_audit_find_fix_verify`, no `code_apply_fix`

`code_apply_fix` es dry-run por default (necesita una segunda llamada con `confirm=true` para escribir de verdad) -- pensada para cuando un humano va a revisar el diff antes de aplicarlo. En el flujo autónomo, quedarse en el dry-run y devolverle el diff al usuario pidiendo que lo confirme él mismo ES el bug que este flujo tiene que evitar. `security_audit_find_fix_verify` aplica, commitea, Y re-escanea para confirmar la resolución, todo en un solo tool call -- usala directo, sin dry-run previo, cuando el pedido ya autorizó reparar sin supervisión.

## Reportar el resultado REAL, no asumir éxito por el commit solo

`security_audit_find_fix_verify` devuelve `finding_resolved` (booleano, calculado re-escaneando el archivo después del commit) -- leelo y reportalo tal cual. Un commit exitoso (`committed: true`) no garantiza que el hallazgo puntual haya quedado resuelto (el fix puede ser cosmético, o tocar el snippet equivocado); `finding_resolved: false` con `committed: true` es un resultado real y hay que decirlo, no maquillarlo como éxito.

## Ver también
[[Cómo Jarvis Audita Seguridad de Código]], [[Bandit en la Práctica]], [[Semgrep en la Práctica]], [[Prevencion de SQL injection en distintos lenguajes]]