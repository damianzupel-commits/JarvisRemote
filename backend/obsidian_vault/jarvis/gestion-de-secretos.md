---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- concepto
- secretos
title: Gestión de Secretos
updated: '2026-07-28T00:00:00.000000+00:00'
---

Cómo manejar API keys, contraseñas, tokens y claves privadas correctamente, más allá del bug puntual descrito en [[Secretos Hardcodeados en Código]] — esta nota es sobre el flujo completo de vida de un secreto.

## Jerarquía de dónde vive un secreto (de peor a mejor)
1. **Hardcodeado en el código fuente** — nunca. Ver [[Secretos Hardcodeados en Código]].
2. **Variable de entorno cargada desde un archivo `.env` commiteado al repo** — mismo problema que el punto 1, solo con un paso extra de indirección. `.env` tiene que estar en `.gitignore` siempre, y su ausencia en el repo hay que verificarla activamente (es un finding clásico: `.env` trackeado por accidente).
3. **Variable de entorno inyectada por la plataforma de deploy** (sin archivo commiteado, seteada en el panel del proveedor/CI) — aceptable para la mayoría de los casos, mejor que las opciones anteriores pero variables de entorno son legibles por cualquier proceso hijo y a veces terminan en logs de crash/debug si no se tiene cuidado.
4. **Gestor de secretos dedicado** (HashiCorp Vault, AWS Secrets Manager, Google Secret Manager, Azure Key Vault) — el secreto se pide en runtime, con auditoría de quién/qué lo accedió, rotación centralizada, y nunca queda persistido en texto plano en ningún archivo de config. La opción correcta para producción en cualquier sistema con datos sensibles reales.

## Qué mirar en un repo (checklist de auditoría)
- `.env`, `.env.local`, `credentials.json`, `*.pem`, `*.key` — ¿están en `.gitignore`? ¿Aparecen en el historial de git aunque ya no estén en el HEAD actual?
- Archivos de ejemplo (`.env.example`) — deberían tener placeholders, nunca un valor real "de prueba" que en realidad apunta a un recurso real.
- CI/CD: ¿los secrets se pasan como variables de entorno seguras del proveedor (GitHub Actions secrets, etc.) o están en el YAML del pipeline en texto plano?
- Imágenes de Docker: secretos pasados como `ARG`/`ENV` en el `Dockerfile` quedan grabados en las capas de la imagen para siempre, incluso si una capa posterior los "borra" — usar `--secret` de BuildKit o inyectarlos solo en runtime, nunca en build time.

## Rotación: el paso que más se olvida
Si un secreto se filtró (aunque sea brevemente, aunque el repo sea privado, aunque se haya borrado del commit actual), **hay que rotarlo** — el filtrado en sí ya expuso el valor, borrarlo del archivo no deshace eso. Ver [[Secretos Hardcodeados en Código]] para por qué el historial de git preserva el secreto igual. Rotación programada (no solo reactiva ante un incidente) también reduce la ventana de exposición de cualquier filtración no detectada.

## Detección automática
Gitleaks/TruffleHog escanean el **historial completo** de git, no solo el estado actual — importante porque un secreto commiteado y luego "removido" en un commit posterior sigue estando en el historial. Trivy también tiene un modo de escaneo de secretos (`trivy fs --scanners secret`). Ver [[Trivy en la Práctica]] y [[Herramientas SAST y SCA - Resumen]] para dónde encaja esto en un pipeline de CI (idealmente como pre-commit hook, para frenar el secreto *antes* de que llegue al historial, además de en CI como red de seguridad).

## Principio general
Ningún secreto real en texto plano en ningún archivo versionado, nunca, ni siquiera "temporalmente" — no existe el "temporal" en un sistema de control de versiones que preserva historial. Ver también [[Defensa en Profundidad]]: la gestión de secretos es una de las capas donde una sola falla (un secreto filtrado) puede anular todas las demás capas de defensa del sistema.
