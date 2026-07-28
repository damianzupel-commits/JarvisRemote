---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A09 - Fallas de Registro y Monitoreo de Seguridad
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #9 del [[OWASP Top 10 - Resumen]]. No es sobre prevenir un ataque, es sobre poder *darse cuenta* de que ocurrió — la diferencia entre un incidente detectado en minutos y uno descubierto meses después (o nunca).

## Patrones concretos a buscar en código
- Eventos de seguridad sin loguear: intentos de login fallidos, cambios de permisos/rol, accesos denegados por autorización, cambios de contraseña o de email de recuperación.
- Logs que **sí** loguean de más: passwords, tokens de sesión, números de tarjeta, o cualquier PII en texto plano en los logs — esto convierte el sistema de logging en un activo sensible por sí mismo (y suele violar cumplimiento tipo PCI-DSS/GDPR).
- Logs solo en almacenamiento local del propio servidor (si el servidor se compromete, el atacante borra su propio rastro).
- Ausencia de alertas automáticas ante patrones sospechosos (múltiples fallos de login, spike de errores 403/401, acceso fuera de horario habitual).
- Mensajes de log sin suficiente contexto para investigar después (sin timestamp, sin ID de usuario/request, sin IP de origen).

## Ejemplo
```python
# vulnerable: loguea el password en texto plano
logger.info(f"Login attempt: user={username} password={password}")

# vulnerable: falla silenciosa, sin registro de un evento de seguridad relevante
try:
    verify_permission(user, resource)
except PermissionDenied:
    pass  # nadie se entera de que alguien intentó esto

# seguro
logger.warning("auth.denied", extra={"user_id": user.id, "resource": resource.id, "ip": request.ip})
```

## Cómo detectarlo estáticamente (parcial)
Grep/reglas semánticas para: bloques `except` de errores de auth/permisos que no loguean nada; llamadas a `logger.*` con variables que coinciden con nombres típicos de secretos (`password`, `token`, `secret`, `api_key` — mismo patrón que [[Secretos Hardcodeados en Código]] pero para el sink de logging en vez de un literal en código). Ausencia total de infraestructura de logging estructurado es más una revisión arquitectónica que un finding de SAST puntual.

## Mitigación
Logging estructurado centralizado (no archivos locales sueltos), alertas automáticas sobre patrones de abuso, y política explícita de qué campos NUNCA se loguean (passwords, tokens, secretos — nunca, ni siquiera en debug). Ver [[Defensa en Profundidad]]: el logging es la capa que permite detectar cuándo las demás capas fallaron.
