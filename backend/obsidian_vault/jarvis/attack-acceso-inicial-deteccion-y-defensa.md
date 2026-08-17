---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- acceso-inicial
- phishing
- deteccion
- defensa
title: 'ATT&CK Acceso Inicial - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0001**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario logra **su primer punto de apoyo** dentro del entorno.

## T1566 — Phishing (y subtécnicas: adjunto, enlace, vía servicio)
**Qué es.** Correo/mensaje engañoso que entrega un adjunto malicioso o un enlace a un sitio de captura/descarga.
**Uso del adversario (conceptual).** Vector de acceso #1 en la práctica. El adjunto suele ser un documento con macro, un contenedor (ISO/ZIP/LNK) o un instalador troyanizado; el objetivo es que el usuario ejecute algo. Enlaza con [[ATT&CK Ejecución - Detección y Defensa]] (T1204 User Execution).
**Detección.** Gateway de correo (sandboxing de adjuntos, reputación de enlaces, SPF/DKIM/DMARC fallidos, dominios recién registrados); en el endpoint, procesos hijos anómalos de Office/lectores de PDF (ej. Word lanzando PowerShell o cmd — señal fuerte); reportes de usuarios.
**Mitigación/endurecimiento.** MFA resistente a phishing (FIDO2/WebAuthn); bloqueo de macros de Internet (Mark-of-the-Web) por política; deshabilitar montaje automático de ISO; filtrado de tipos de adjunto peligrosos; entrenamiento y botón de reporte.
**Prueba atómica.** Atomic Red Team T1566.001 simula la entrega de un adjunto con macro en laboratorio para validar el filtrado y la detección en endpoint.
**Capacidad Jarvis.** La regla `Suspicious_PowerShell_Obfuscation` de `starter.yar` matchea el dropper típico que un adjunto de phishing suele lanzar (ver [[Familias de Malware - Taxonomía Detección y Defensa]]).

## T1190 — Exploit Public-Facing Application
**Qué es.** Explotación de una vulnerabilidad en un servicio expuesto (web, VPN, correo, API).
**Uso del adversario (conceptual).** Aprovecha CVEs sin parchear o fallas de configuración para ejecutar código o autenticarse sin credenciales. *(No se documentan payloads; ver el lado defensivo del código en [[Cómo Jarvis Audita Seguridad de Código]] y [[OWASP Top 10 - Resumen]].)*
**Detección.** WAF/IDS con firmas del CVE; anomalías en logs del servidor (500s, rutas raras, user-agents de herramientas); un proceso del servidor web lanzando un shell (patrón webshell → ver regla `Suspicious_PHP_Webshell` de `starter.yar`); egress inesperado desde el servidor.
**Mitigación/endurecimiento.** Parcheo priorizado por exposición (SLA corto para servicios en Internet); virtual patching en el WAF; segmentación (DMZ); mínimo privilegio del proceso del servicio; gestión de vulnerabilidades continua.
**Prueba atómica.** Emulación con un CVE de laboratorio controlado; Atomic Red Team cubre variantes de web shell drop bajo T1505.003.

## T1133 — External Remote Services
**Qué es.** Uso de servicios de acceso remoto legítimos (VPN, RDP, VDI) con credenciales válidas robadas.
**Detección.** Logins desde geografías/horarios imposibles; primer acceso de un usuario desde una IP nueva; ausencia de MFA. UEBA es clave (ver guía CISA/LOTL).
**Mitigación.** MFA en todo acceso remoto; no exponer RDP directo a Internet; listas de acceso condicional; bloqueo de "viaje imposible".

## T1199 — Trusted Relationship / T1195 — Supply Chain Compromise
**Qué es.** Entrar a través de un tercero de confianza (proveedor MSP, software actualizado con backdoor).
**Detección.** Cambios inesperados en binarios firmados; comportamiento anómalo tras una actualización; conexiones salientes nuevas desde software confiable. Enlaza con [[ATT&CK Ejecución - Detección y Defensa]] y con integridad de archivos.
**Mitigación.** Verificación de firmas y hashes; SBOM y control de dependencias (ver [[Herramientas SAST y SCA - Resumen]]); mínimo privilegio para accesos de terceros; segmentación.
**Capacidad Jarvis.** El file integrity monitoring (`app/malware/integrity.py`) detecta modificación no autorizada de binarios/config críticos, señal directa de compromiso de cadena de suministro o troyanización.

## T1078 — Valid Accounts
**Qué es.** Uso de cuentas legítimas (default, huérfanas, o robadas) para entrar sin explotar nada.
**Detección.** Uso de cuentas dormidas; cuentas de servicio interactivas; ver [[Credenciales por defecto en dispositivos IoT y como se explotan]].
**Mitigación.** Rotación y baja de cuentas; deshabilitar defaults; MFA; principio de mínimo privilegio.

## Referencias
- MITRE ATT&CK TA0001 (Initial Access).
- CISA — MFA resistente a phishing; guías de mitigación de phishing.
- Atomic Red Team — atomics T1566, T1190, T1505.003.
