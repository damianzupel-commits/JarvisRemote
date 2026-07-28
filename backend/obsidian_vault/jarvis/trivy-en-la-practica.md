---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- herramienta
- sca
- trivy
title: Trivy en la Práctica
updated: '2026-07-28T00:00:00.000000+00:00'
---

SCA + escáner de misconfiguration, todo en una sola herramienta open-source. Ver [[Herramientas SAST y SCA - Resumen]]. A diferencia de Semgrep/Bandit (que leen código fuente propio), Trivy analiza principalmente **artefactos**: manifiestos de dependencias, imágenes de contenedor completas, filesystems, y definiciones de infraestructura (IaC).

## Los cuatro modos de escaneo principales
```bash
# 1. Dependencias del proyecto (lee requirements.txt, package-lock.json, etc.)
trivy fs --scanners vuln .

# 2. Imagen de contenedor completa -- capas del SO base + paquetes del sistema + deps de la app
trivy image mi-app:latest

# 3. Misconfiguration en IaC (Dockerfile, Kubernetes manifests, Terraform)
trivy config .

# 4. Secretos hardcodeados (Trivy también hace esto, superpuesto con Gitleaks)
trivy fs --scanners secret .
```

## Por qué escanear la imagen completa importa (no solo el manifiesto de deps)
`trivy fs` ve las dependencias que el proyecto declaró explícitamente. `trivy image` ve además el **sistema operativo base** de la imagen (paquetes `apt`/`apk` con sus propias CVEs) y cualquier binario instalado a mano en el Dockerfile que nunca aparece en `requirements.txt`. Una imagen basada en `python:3.9-slim` desactualizada puede tener CVEs críticas en `openssl`/`libc` del SO aunque las dependencias Python del proyecto estén todas al día — esto es directamente [[OWASP A06 - Componentes Vulnerables y Desactualizados]] aplicado a la capa de sistema operativo, no solo a la capa de aplicación.

## Cómo leer el output
```
mi-app:latest (debian 11.6)
=============================
Total: 3 (HIGH: 2, CRITICAL: 1)

┌──────────┬────────────────┬──────────┬───────────────────┬───────────────┐
│ Library  │ Vulnerability  │ Severity │ Installed Version │ Fixed Version │
├──────────┼────────────────┼──────────┼───────────────────┼───────────────┤
│ openssl  │ CVE-2023-XXXXX │ CRITICAL │ 1.1.1n-0+deb11u3   │ 1.1.1n-0+deb11u4 │
└──────────┴────────────────┴──────────┴───────────────────┴───────────────┘
```
La columna clave para priorizar es **Fixed Version**: si existe, es un update directo y de bajo esfuerzo — la prioridad más alta de la lista. Si no hay fix disponible todavía, la mitigación tiene que ser en otra capa (ver [[Defensa en Profundidad]]) hasta que el upstream libere un parche.

## Falsos positivos / ruido común
- **CVEs en paquetes no alcanzables**: una dependencia transitiva con una CVE en una función que el proyecto nunca invoca. Trivy tiene soporte experimental de *reachability* para algunos ecosistemas, pero no es tan maduro como el de Snyk — sin reachability, hay que revisar manualmente si el código realmente usa la parte vulnerable de la librería antes de tratarlo como urgente.
- **CVEs de severidad baja en paquetes del SO base que no se usan directamente**: en una imagen `slim`/`alpine`, suele haber menos de esto, pero imágenes base más completas arrastran paquetes que la app ni siquiera invoca.
- **"Won't fix" del upstream de la distro**: algunas distros marcan una CVE como no aplicable a su build específico; Trivy a veces la sigue reportando si la base de datos de vulnerabilidades no está perfectamente sincronizada con esa decisión.

## Dónde encaja en CI
Correr `trivy image` como último paso del build de la imagen de contenedor, con `--exit-code 1` para HIGH/CRITICAL de forma que el pipeline falle — eso convierte a Trivy en un gate real, no solo un reporte que nadie lee.
