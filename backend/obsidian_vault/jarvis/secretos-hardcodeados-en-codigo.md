---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- secretos
title: Secretos Hardcodeados en Código
updated: '2026-07-28T00:00:00.000000+00:00'
---

Relacionado con [[OWASP A02 - Fallas Criptográficas]] y con [[OWASP A05 - Configuración de Seguridad Incorrecta]]. Es probablemente el finding más común y de mayor impacto directo que produce un escaneo de código: API keys, tokens, contraseñas de base de datos, claves privadas o secretos de firma escritos literalmente en el código fuente.

## Por qué es tan grave incluso en repos privados
- Cualquiera con acceso de lectura al repo (incluyendo ex-empleados, contratistas, CI/CD, herramientas de terceros conectadas) tiene el secreto.
- Si el repo se hace público por error, o un fork/mirror queda expuesto, el secreto queda expuesto también.
- **El secreto queda en el historial de git para siempre**, aunque se borre en un commit posterior — hay que rotarlo, no solo borrarlo del archivo actual (`git log -p` o herramientas como `trufflehog`/`gitleaks` lo encuentran igual escaneando el historial completo).

## Patrones típicos que detectan las herramientas
```python
# vulnerable: distintas formas del mismo problema
AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE"
DATABASE_URL = "postgres://admin:SuperSecret123@prod-db.internal:5432/app"
STRIPE_API_KEY = "sk_live_51H..."

client = OpenAI(api_key="sk-proj-...")  # hardcodeado en vez de leído de env
```
```javascript
// vulnerable
const JWT_SECRET = "my-super-secret-key-2024";
```
Las herramientas de detección de secretos (Gitleaks, TruffleHog, y las reglas de secretos de Semgrep/GitHub Advanced Security) usan combinación de:
1. **Patrones de formato conocidos** — prefijos característicos (`sk_live_`, `AKIA`, `ghp_`, `xoxb-`) que identifican el *tipo* de secreto con alta confianza.
2. **Entropía** — strings con alta aleatoriedad asignados a variables con nombres sospechosos (`_key`, `_secret`, `_token`, `_password`) aunque no calcen con ningún prefijo conocido.

## Falsos positivos comunes (importante para no generar ruido)
- Placeholders/ejemplos en docs o tests: `API_KEY = "your-api-key-here"`, `password = "changeme"` — baja entropía real, se filtran fácil.
- UUIDs y hashes que no son secretos (IDs públicos, hashes de commit) pero tienen alta entropía — más difícil de filtrar automáticamente, requiere revisión humana o allowlist explícita del repo.
- Claves de test/sandbox explícitamente públicas de algunos proveedores (Stripe publica claves `pk_test_` de ejemplo en su propia documentación).

## Mitigación
Nunca secretos en código fuente, ni siquiera "temporalmente". Variables de entorno + un gestor de secretos real para producción. Ver [[Gestión de Secretos]] para el detalle completo, y [[Herramientas SAST y SCA - Resumen]] para dónde encaja el escaneo de secretos en el pipeline (idealmente como pre-commit hook, además de en CI).
