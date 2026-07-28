---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- python
- javascript
title: SQL Injection
updated: '2026-07-28T00:00:00.000000+00:00'
---

Subtipo de [[OWASP A03 - Injection]]. El sink es el motor de base de datos: input del usuario se concatena/interpola dentro de un query SQL, y el atacante inyecta SQL propio que el motor ejecuta con los mismos permisos que la app.

## Ejemplo vulnerable → seguro (Python)
```python
# vulnerable: f-string directo al query
def get_user(username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    # username = "' OR '1'='1" devuelve todos los usuarios
    # username = "'; DROP TABLE users; --" en motores que permiten multi-statement

# seguro: parámetros bindeados, el driver separa código de datos
def get_user(username):
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
```

## Ejemplo vulnerable → seguro (Node/JS con un driver SQL típico)
```javascript
// vulnerable
const query = `SELECT * FROM users WHERE id = ${req.params.id}`;
db.query(query);

// seguro: placeholder del driver
db.query("SELECT * FROM users WHERE id = ?", [req.params.id]);
```

## Con ORM no estás automáticamente a salvo
```python
# vulnerable incluso usando SQLAlchemy: raw SQL con f-string
db.session.execute(f"SELECT * FROM users WHERE name = '{name}'")

# vulnerable: .filter con texto crudo
User.query.filter(f"name = '{name}'")

# seguro: API del ORM con parámetros, o text() con bindparams
from sqlalchemy import text
db.session.execute(text("SELECT * FROM users WHERE name = :name"), {"name": name})
```
El ORM protege solo cuando se usa su API de construcción de queries (`.filter_by()`, comparaciones con operadores de Python); en cuanto se cae a SQL crudo con interpolación de string, la protección desaparece.

## Blind SQL injection
Cuando la respuesta no muestra el error ni los datos directamente, el atacante infiere información con preguntas booleanas (`AND 1=1` vs `AND 1=2`) midiendo diferencias de respuesta o de tiempo (`AND SLEEP(5)`) — más lento de explotar pero igual de explotable, y menos visible en logs si no se loguean los queries fallidos.

## Cómo lo detectan las herramientas
Bandit: `B608` (posible SQL injection por construcción de string). Semgrep: reglas `p/sql-injection` que buscan f-strings/concatenación llegando a `.execute()`/`.query()`. CodeQL hace flujo de datos real desde el input HTTP hasta el sink, con menos falsos positivos que las reglas puramente sintácticas. Ver [[Bandit en la Práctica]], [[Semgrep en la Práctica]], [[CodeQL en la Práctica]].

## Mitigación
Prepared statements / parámetros bindeados siempre. Si hace falta SQL dinámico (nombres de tabla/columna, que no se pueden bindear como parámetro), validar contra una allowlist estricta, nunca contra un blocklist de caracteres peligrosos.
