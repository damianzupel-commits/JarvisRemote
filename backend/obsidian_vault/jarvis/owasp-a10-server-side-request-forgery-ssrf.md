---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A10 - Server-Side Request Forgery (SSRF)
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #10 del [[OWASP Top 10 - Resumen]], nueva en 2021 (antes formaba parte de otras categorías). El servidor hace una request HTTP (u otro protocolo) a una URL que el atacante controla total o parcialmente, y el atacante la usa para llegar a recursos que normalmente no podría alcanzar desde afuera.

## Por qué es peligroso específicamente
El servidor suele tener acceso de red a cosas que el mundo exterior no tiene: metadata de cloud (`http://169.254.169.254/` en AWS/GCP/Azure — de ahí se roban credenciales IAM temporales), servicios internos sin autenticación porque "están detrás del firewall", o el propio filesystem vía `file://`.

## Patrón concreto
```python
# vulnerable: la URL viene directo del usuario, sin restricción
@app.post("/fetch-preview")
def fetch_preview(url: str):
    resp = requests.get(url)  # el atacante manda http://169.254.169.254/latest/meta-data/
    return resp.text
```
Casos típicos donde aparece: previsualización de links/imágenes, webhooks configurables por el usuario, integraciones que "importan desde una URL", conversores de PDF/imagen que aceptan una URL remota, SSO/OAuth con `redirect_uri` no validado estrictamente.

## Mitigación (en capas, ninguna sola alcanza)
1. **Allowlist de dominios/hosts permitidos** — la defensa más fuerte cuando es viable (ej. solo permitir `api.partner.com`).
2. Si se necesita aceptar URLs arbitrarias: resolver el DNS *antes* de conectar y validar que la IP resuelta no sea privada/loopback/link-local (`127.0.0.0/8`, `169.254.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `::1`) — y volver a validar después de seguir redirects, porque el atacante puede hacer que la primera URL sea "segura" y redirija a una interna.
3. Deshabilitar schemes no-HTTP (`file://`, `gopher://`, `dict://`) en el cliente HTTP.
4. Aislar de red el proceso que hace estas requests (egress firewall) como capa adicional — ver [[Defensa en Profundidad]].

## Detección estática
Buscar llamadas a clientes HTTP (`requests.get`, `httpx`, `fetch`, `axios`, `urllib`) donde el argumento de URL/host proviene de input del usuario sin pasar por una función de validación de allowlist en el medio — mismo patrón fuente→sink que el resto de [[OWASP A03 - Injection]], aunque SSRF tiene categoría propia por su impacto particular (acceso a red interna/metadata de cloud).
