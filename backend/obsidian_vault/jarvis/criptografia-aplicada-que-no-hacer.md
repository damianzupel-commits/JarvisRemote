---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- concepto
- criptografia
title: 'Criptografía Aplicada: Qué NO Hacer'
updated: '2026-07-28T00:00:00.000000+00:00'
---

Regla de oro de criptografía aplicada: **no diseñar algoritmos criptográficos propios, y no reimplementar primitivas existentes a mano**. Usar siempre implementaciones de librerías estándar, revisadas y maduras. Esta nota es una lista de "qué no hacer" concreta, complementaria a [[OWASP A02 - Fallas Criptográficas]] (que es la categoría OWASP) — acá el foco es el criterio de elección correcto, no solo el bug puntual.

## No hacer #1: hashes rápidos para passwords
```python
# mal: MD5/SHA1/SHA256 son RÁPIDOS por diseño -- eso es bueno para integridad
# de archivos, pésimo para passwords (permite billones de intentos/segundo
# en hardware de GPU/ASIC dedicado)
password_hash = hashlib.sha256(password.encode()).hexdigest()

# bien: función de hashing de password, deliberadamente LENTA y con costo
# configurable, diseñada específicamente para resistir fuerza bruta
from argon2 import PasswordHasher
password_hash = PasswordHasher().hash(password)
```
Orden de preferencia para hashing de passwords: **Argon2id** (ganador de la Password Hashing Competition, recomendado por OWASP hoy) > **bcrypt** (más viejo pero sigue siendo sólido y ampliamente soportado) > **PBKDF2** (aceptable solo si hace falta compliance FIPS específico que no permite las otras dos). Nunca MD5/SHA1/SHA256/SHA512 solos, aunque se les agregue "salt" a mano — el problema no es la falta de salt, es que son demasiado rápidos.

## No hacer #2: ECB como modo de cifrado
ECB (Electronic Codebook) cifra cada bloque de forma independiente e idéntica — bloques de plaintext iguales producen bloques de ciphertext iguales, lo que filtra patrones estructurales del dato original (el ejemplo clásico: cifrar una imagen con ECB y seguir viendo la silueta de la imagen en el resultado). Usar **AES-GCM** (autenticado, protege integridad además de confidencialidad) o, si no hace falta autenticación integrada, AES-CBC con un MAC separado — nunca ECB para nada que no sea un solo bloque de dato sin estructura repetitiva.

## No hacer #3: IVs/nonces reutilizados o predecibles
Para modos de cifrado que usan IV/nonce (CBC, GCM, CTR), reutilizar el mismo IV con la misma clave rompe las garantías de seguridad del modo — en GCM en particular, reutilizar un nonce puede llegar a filtrar la clave de autenticación completa. El IV/nonce se genera con un CSPRNG cada vez que se cifra, nunca se hardcodea ni se deriva de forma predecible (timestamp, contador reseteable).

## No hacer #4: PRNG no criptográfico para material sensible
```python
import random
token = str(random.random())          # mal: Mersenne Twister es predecible
                                        # si se observan suficientes outputs

import secrets
token = secrets.token_urlsafe(32)      # bien: CSPRNG, diseñado para esto
```
```javascript
Math.random()                          // mal, mismo problema que random.random()
crypto.randomBytes(32)                 // bien (Node) / crypto.getRandomValues (browser)
```
Regla simple: si el output se va a usar como secreto, token de sesión, clave, o cualquier cosa donde la predictibilidad importa, usar el módulo criptográfico del lenguaje (`secrets` en Python, `crypto` en Node, `SecureRandom` en Java/Kotlin), nunca el generador de números aleatorios de propósito general.

## No hacer #5: comparación de secretos con `==`
```python
# mal: == compara byte por byte y corta en la primera diferencia -- el tiempo
# de respuesta varía según cuántos bytes coincidieron, filtrando información
# explotable con un timing attack
if hmac_received == hmac_expected:
    ...

# bien: comparación en tiempo constante
import hmac
if hmac.compare_digest(hmac_received, hmac_expected):
    ...
```

## No hacer #6: TLS deshabilitado "temporalmente"
`verify=False` (Python `requests`), `rejectUnauthorized: false` (Node), `-k`/`--insecure` (curl) hardcodeado en un script — cualquiera de estos elimina la protección contra man-in-the-middle. Casi siempre entra "para debuggear un cert self-signed en dev" y queda en el código para siempre. Ver [[OWASP A02 - Fallas Criptográficas]].

## Principio general
No hay "casi seguro" en criptografía — una primitiva mal elegida no degrada la seguridad proporcionalmente, la anula. Ante la duda, usar el default de una librería madura (`argon2-cffi`, `cryptography` en Python; `libsodium`/`tweetnacl` cuando se necesita algo más bajo nivel) en vez de ensamblar primitivas a mano.
