---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- hardening
- endurecimiento
- defensa
- blue-team
title: 'Hardening y Endurecimiento del Endpoint'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Nota transversal de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. El hardening **reduce la superficie de ataque** y encarece cada técnica de las notas de táctica. Es defensa preventiva; se complementa con [[Higiene de Detección - Firmas vs Comportamiento]] (defensa detectiva). Principio rector: [[Defensa en Profundidad]].

## Reducción de superficie de ataque
- **Mínimo privilegio**: usuarios sin admin local; cuentas de servicio con lo justo; separar cuentas admin (tiering). Corta escalación (TA0004) y movimiento lateral (TA0008).
- **Desinstalar/deshabilitar lo innecesario**: servicios, protocolos legacy (SMBv1, LLMNR, NetBIOS), features no usadas. Menos que atacar.
- **Application control** (WDAC/AppLocker en Windows): solo corre software aprobado/firmado. Neutraliza droppers, LOLBins innecesarios y binarios no firmados.
- **Attack Surface Reduction (ASR) rules** (Microsoft Defender): bloquear macros de Office lanzando procesos, robo de credenciales de LSASS, ejecución de contenido descargado, etc. Mitigación concreta de varias técnicas de esta biblioteca.

## Configuración segura (baseline)
- Aplicar **CIS Benchmarks** / Microsoft Security Baselines / DISA STIGs como línea base auditable.
- **Bloqueo de macros de Internet** (Mark-of-the-Web) por política — corta el vector de phishing más común.
- **Deshabilitar montaje automático de ISO/IMG**; filtrar tipos de adjunto peligrosos.
- **PowerShell**: Constrained Language Mode + Script Block Logging + AMSI habilitado.

## Identidad y credenciales
- **MFA en todo**, resistente a phishing (FIDO2/WebAuthn) donde se pueda. Mitiga acceso inicial, movimiento lateral y fuerza bruta de una sola vez.
- **LAPS**: contraseña de admin local única y rotada por host — mata pass-the-hash lateral.
- **Credential Guard** (VBS aísla LSASS); LSASS como PPL; ASR "block credential stealing from LSASS".
- **Tiering administrativo**: cuentas de dominio admin no inician sesión en workstations; jump hosts para administración.

## Parcheo y gestión de vulnerabilidades
- Parcheo priorizado por **exposición** (servicios en Internet primero, SLA corto) y por explotación activa conocida (CISA KEV catalog).
- Blocklist de **drivers vulnerables** (BYOVD) / HVCI.
- SBOM y control de dependencias (ver [[Herramientas SAST y SCA - Resumen]]).

## Red y segmentación
- **Segmentación / microsegmentación**: limita a qué puede hablar cada host; contiene gusanos y movimiento lateral.
- **Egress filtering default-deny**: la salida controlada corta C2 y exfiltración (TA0011/TA0010).
- **DNS filtering** por reputación; proxy con inspección; bloqueo de anonimizadores según política.

## Datos y recuperación
- **Backups 3-2-1 con copia offline/inmutable, probados** — la única garantía real contra ransomware/wiper (TA0040).
- Cifrado de disco en reposo; DLP para datos sensibles; canary/honey files como alerta temprana.

## Arranque e integridad
- **Secure Boot + TPM + arranque medido**; firmware actualizado — base contra rootkits/bootkits.
- **FIM** sobre binarios y config críticos (Jarvis: `app/malware/integrity.py`).

## Telemetría (prerequisito de toda detección)
Sin logs no hay detección. Mínimos: command-line auditing (4688) o Sysmon, PowerShell Script Block Logging (4104), creación de servicios/tareas, modificación de Registro, conexiones de red por proceso — todo **reenviado a un SIEM central** (para que borrar el log local no borre la evidencia). Ver [[MITRE ATT&CK - Fundamentos del Marco]] (data sources).

## Cómo se mide
Emular técnicas de forma controlada y verificar prevención + detección (ver [[Probar la Detección de Forma Segura - EICAR Atomic Red Team Emulación]]). Un control que no se prueba se asume roto.

## Referencias
- CIS Benchmarks, Microsoft Security Baselines, DISA STIGs.
- Microsoft — ASR rules, LAPS, Credential Guard, WDAC.
- CISA — Known Exploited Vulnerabilities (KEV) catalog; #StopRansomware.
