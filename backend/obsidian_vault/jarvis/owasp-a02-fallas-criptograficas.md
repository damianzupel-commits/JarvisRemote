---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
- criptografia
title: OWASP A02 - Fallas Criptográficas
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #2 del [[OWASP Top 10 - Resumen]]. Antes se llamaba "Sensitive Data Exposure" (2017) — el rename a 2021 pone el foco en la *causa raíz* (criptografía mal usada o ausente) en vez del síntoma (datos expuestos).

## Patrones concretos a buscar en código
- Datos sensibles (passwords, tarjetas, tokens, PII) transmitidos o guardados **en texto plano**.
- Uso de algoritmos rotos o débiles: `MD5`, `SHA1` para passwords, `DES`, `RC4`, ECB como modo de cifrado. Detalle completo y ejemplos en [[Criptografía Aplicada: Qué NO Hacer]].
- Claves o IVs hardcodeados, o IVs reutilizados / no aleatorios en cifrado simétrico.
- Generación de tokens/secretos con `random.random()` (Python) o `Math.random()` (JS) en vez de un CSPRNG (`secrets`, `crypto.randomBytes`).
- Certificados TLS con verificación deshabilitada (`verify=False` en `requests`, `NODE_TLS_REJECT_UNAUTHORIZED=0`, `-k`/`--insecure` en curl hardcodeado en scripts).
- Comparación de secretos con `==` en vez de comparación en tiempo constante (habilita timing attacks).

## Ejemplo
```python
# vulnerable
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()

# vulnerable: TLS deshabilitado
resp = requests.get(url, verify=False)

# seguro: hashing de password con salt + costo adaptativo
from argon2 import PasswordHasher
ph = PasswordHasher()
password_hash = ph.hash(password)
```

## Qué buscan las reglas SAST
Bandit tiene reglas dedicadas (`B303`/`B324` uso de hashlib inseguro, `B501` verify=False en requests, `B105`/`B106` posibles secretos hardcodeados). Semgrep tiene rulesets `p/crypto` que cubren varios lenguajes. Ver [[Bandit en la Práctica]] y [[Semgrep en la Práctica]].

## Mitigación
Para passwords: Argon2id o bcrypt, nunca hashes rápidos de propósito general. Para cifrado simétrico: AES-GCM (autenticado). Para TLS: nunca deshabilitar verificación, ni siquiera "temporalmente" en dev (queda). Ver [[Criptografía Aplicada: Qué NO Hacer]] y [[Gestión de Secretos]] para el manejo de las claves en sí.
