---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- herramienta
- sast
- bandit
- python
title: Bandit en la Práctica
updated: '2026-07-28T00:00:00.000000+00:00'
---

SAST específico de Python. Ver [[Herramientas SAST y SCA - Resumen]] y [[Seguridad en Python]]. A diferencia de Semgrep, Bandit no es multi-lenguaje ni configurable con reglas propias en YAML tan flexible — a cambio, viene con un set de reglas curado específicamente para los antipatrones más comunes de Python, sin configuración inicial.

## Uso básico
```bash
bandit -r ./mi_proyecto
bandit -r . -f json -o findings.json    # output estructurado
bandit -r . -ll                          # solo reportar severidad medium/high
bandit -r . -x tests/,venv/              # excluir paths
```

## Reglas más relevantes (IDs que va a ver en el output)
| ID | Qué detecta | Nota relacionada |
|---|---|---|
| B105/B106/B107 | posibles passwords/secretos hardcodeados | [[Secretos Hardcodeados en Código]] |
| B301-B306 | uso de `pickle`, `marshal`, `xml` parsers inseguros | [[Insecure Deserialization]], [[XXE - XML External Entity]] |
| B324 | uso de hash débil (`md5`, `sha1`) | [[OWASP A02 - Fallas Criptográficas]] |
| B501 | `requests` con `verify=False` | [[OWASP A02 - Fallas Criptográficas]] |
| B506 | `yaml.load` sin `SafeLoader` | [[Insecure Deserialization]] |
| B602/B605 | `subprocess`/`os.system` con `shell=True` | [[Command Injection]] |
| B608 | posible SQL injection por construcción de query con string | [[SQL Injection]] |
| B701 | Jinja2 con autoescape deshabilitado | [[Cross-Site Scripting (XSS)]] |

## Cómo leer el output
```
>> Issue: [B608:hardcoded_sql_expressions] Possible SQL injection vector through string-based query construction.
   Severity: Medium   Confidence: Low
   Location: app/db.py:42:12
```
Dos ejes separados, no uno solo: **Severity** (qué tan grave sería si es real) y **Confidence** (qué tan seguro está Bandit de que el patrón realmente aplica acá). Un finding "Medium severity / Low confidence" merece una mirada rápida pero no es alarma inmediata; "High severity / High confidence" sí es prioridad de revisión real.

## Falsos positivos comunes
- **B101 (`assert` usado)**: Bandit marca *todo* uso de `assert`, incluyendo el uso normal en tests con pytest (donde `assert` es el mecanismo esperado, no un bug) — hay que excluir el directorio de tests o filtrar este check ahí. El riesgo real de `assert` (ver [[Seguridad en Python]]) es solo cuando se usa para validación de seguridad en código de producción.
- **B608 (SQL injection) sobre queries 100% estáticos**: si el string interpola solo constantes (nombres de tabla fijos, nunca input de usuario), es un falso positivo — Bandit no distingue interpolación de datos estáticos vs. dinámicos con certeza, solo ve la forma sintáctica (f-string/`.format()` cerca de `.execute()`).
- **B404/B603 (`subprocess` importado/usado)**: marca el uso de `subprocess` en general con confidence baja; la mayoría de usos legítimos con `shell=False` y lista de argumentos no son un problema real, solo importa revisar los que además tienen `shell=True` (B602).

## Suprimir un finding puntual (con criterio)
```python
query = f"SELECT * FROM {TABLE_NAME}"  # nosec B608 -- TABLE_NAME es una constante del módulo, no input externo
cursor.execute(query)
```
El comentario `# nosec` suprime el finding en esa línea — usarlo siempre con una justificación en el mismo comentario, nunca en silencio, para que quede auditable por qué se descartó.
