---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A07 - Fallas de Identificación y Autenticación
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #7 del [[OWASP Top 10 - Resumen]] (antes "Broken Authentication" en 2017). Cubre todo lo que puede fallar en verificar *quién* es el usuario. Ver [[Autenticación y Autorización]] para el concepto general; esta nota es la lista de fallas concretas a buscar en código.

## Patrones concretos
- Passwords comparados con `==` en vez de una función de verificación de hash con tiempo constante (`hmac.compare_digest`, o el `.verify()` del propio hasher).
- Sin rate limiting / lockout en el endpoint de login → permite fuerza bruta y credential stuffing.
- Passwords sin política mínima de complejidad, o política *excesiva* que empuja a los usuarios a patrones predecibles (rotación forzada frecuente es hoy anti-patrón según NIST 800-63B).
- Session tokens predecibles (secuenciales, timestamp-based) en vez de generados con un CSPRNG.
- Session ID que no se regenera después de un login exitoso (session fixation).
- IDs de sesión expuestos en la URL (quedan en logs de servidor, browser history, header `Referer`).
- JWT con `alg: none` aceptado, o validación de firma ausente/opcional, o secret de firma débil/hardcodeado.
- MFA ausente en cuentas privilegiadas, o MFA "bypasseable" por un flujo alternativo de recuperación más débil.

## Ejemplo
```python
# vulnerable: comparación no es tiempo-constante, filtra info por timing
if user.password_hash == given_hash:
    ...

# vulnerable: JWT sin verificar algoritmo esperado
payload = jwt.decode(token, options={"verify_signature": False})

# seguro
payload = jwt.decode(token, key=SECRET, algorithms=["HS256"])
```

## Mitigación
Delegar a librerías de auth maduras y mantenidas en vez de reimplementar (OAuth2/OIDC para SSO, Argon2id/bcrypt para passwords — ver [[Criptografía Aplicada: Qué NO Hacer]]), rate limiting real en endpoints de auth, rotación de session ID en cada cambio de nivel de privilegio, y MFA para cuentas sensibles. Correlacionar con [[OWASP A02 - Fallas Criptográficas]] (los secretos de firma de sesión/JWT son secretos criptográficos) y con [[Gestión de Secretos]].
