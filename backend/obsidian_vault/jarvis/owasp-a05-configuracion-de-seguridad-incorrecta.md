---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A05 - Configuración de Seguridad Incorrecta
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #5 del [[OWASP Top 10 - Resumen]]. A diferencia de A04, acá sí hay mucho detectable en código y en archivos de config versionados junto al código — territorio natural de SAST + reglas específicas de IaC.

## Patrones concretos a buscar
- `DEBUG = True` (Django/Flask) o equivalentes hardcodeados para producción — filtra stack traces con paths internos, a veces variables de entorno completas.
- Mensajes de error verbosos expuestos al cliente (stack trace completo en la respuesta HTTP en vez de un error genérico + log interno).
- Headers de seguridad ausentes: falta `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`.
- CORS permisivo por default (`Access-Control-Allow-Origin: *` en frameworks que lo dejan así out-of-the-box).
- Servicios/puertos de admin (paneles de administración, consolas de debug como `Werkzeug` debugger, endpoints de métricas) expuestos sin autenticación.
- Configuración de contenedores: correr como `root` en un `Dockerfile`, imágenes base sin pin de versión (`FROM python:latest`), secrets pasados como `ARG`/`ENV` en build (quedan en las capas de la imagen — ver [[Gestión de Secretos]]).
- Permisos por defecto demasiado abiertos en buckets de storage, colas, o políticas IAM (`"Action": "*", "Resource": "*"`).

## Ejemplo
```python
# vulnerable: debug mode habilitado, expone el Werkzeug interactive debugger
app.run(debug=True, host="0.0.0.0")
```
```dockerfile
# vulnerable
FROM python:latest
USER root
```

## Herramientas
Semgrep tiene rulesets de config para frameworks web comunes; Trivy además de SCA escanea **misconfiguration** de Dockerfiles, Kubernetes manifests y Terraform (no solo vulnerabilidades de dependencias) — ver [[Trivy en la Práctica]]. Es una de las pocas categorías del Top 10 donde el escaneo de IaC pesa tanto como el escaneo de código de aplicación.

## Mitigación
Configuración segura por defecto (secure-by-default), hardening documentado y automatizado (no un checklist manual que se hace una vez), y separar estrictamente config de dev vs. producción vía variables de entorno, nunca vía comentarios `# TODO cambiar antes de deployar`.
