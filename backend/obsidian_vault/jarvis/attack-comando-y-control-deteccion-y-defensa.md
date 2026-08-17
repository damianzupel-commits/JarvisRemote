---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- comando-y-control
- c2
- deteccion
- defensa
title: 'ATT&CK Comando y Control - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0011**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el implante **se comunica con la infraestructura del atacante** para recibir órdenes y devolver datos. La detección aquí es sobre todo **análisis de tráfico de red**.

## T1071 — Application Layer Protocol (HTTPS, DNS, correo como canal)
**Qué es.** Esconder el C2 dentro de protocolos comunes (HTTP/S, DNS, SMTP) para mezclarse con tráfico legítimo.
**Uso del adversario (conceptual).** El implante hace "beaconing": llama a casa a intervalos regulares por HTTPS a un dominio controlado, recibe tareas y responde.
**Detección.** **Beaconing** = conexiones periódicas y regulares al mismo destino (patrón temporal detectable con Zeek/NetFlow); user-agents raros; JA3/JA3S de TLS anómalos; dominios de baja reputación o recién registrados; ratio de bytes subida/bajada atípico. Enlaza con proxy/DNS logging.
**Mitigación/endurecimiento.** Proxy con inspección TLS y control por categoría/reputación; bloqueo por reputación de dominio; egress filtering (default-deny saliente); DNS filtering.
**Prueba atómica.** Atomic Red Team T1071.001 genera tráfico HTTP saliente a un endpoint de prueba para validar detección de C2/egress.

## T1071.004 / T1572 — DNS Tunneling y Protocol Tunneling
**Qué es.** Codificar datos/comandos dentro de consultas DNS (o túneles sobre otros protocolos) para exfiltrar y controlar sin abrir puertos raros.
**Detección.** Consultas DNS anómalas: nombres muy largos, alta entropía, muchos subdominios únicos bajo un mismo dominio, volumen de TXT/NULL inusual. Los resolvers deben loguear y analizarse.
**Mitigación.** DNS a través de resolvers corporativos con logging y análisis; bloquear DoH no autorizado; alertar sobre volumen/entropía de DNS.

## T1573 — Encrypted Channel / T1090 — Proxy (incl. Tor, domain fronting)
**Qué es.** Cifrar el canal (más allá de TLS estándar) y/o pasar por proxies/Tor/domain fronting para ocultar el destino real.
**Detección.** Tráfico a nodos Tor conocidos; certificados autofirmados/anómalos; domain fronting (SNI ≠ Host). Feeds de IOC.
**Mitigación.** Bloqueo de Tor/anonimizadores donde la política lo permita; inspección TLS; reputación.

## T1105 — Ingress Tool Transfer
**Qué es.** Descargar herramientas/etapas adicionales desde el C2 al host.
**Detección.** Descarga de ejecutables desde dominios de baja reputación; `certutil`/`bitsadmin`/`curl`/PowerShell `DownloadString` trayendo binarios (LOLBins de descarga); escritura de un EXE seguido de su ejecución.
**Capacidad Jarvis.** La regla `Suspicious_PowerShell_Obfuscation` de `starter.yar` matchea el patrón `DownloadString`/`IEX(New-Object` del stager que trae la siguiente etapa.
**Mitigación.** Egress filtering; application control; bloqueo de LOLBins de descarga no necesarios.

## T1008 — Fallback Channels / T1571 — Non-Standard Port
**Qué es.** Canales de respaldo y uso de puertos no estándar para el protocolo (ej. HTTP en 8443, TLS en 4444).
**Detección.** Protocolo detectado ≠ puerto esperado (Zeek); conexiones a puertos altos inusuales persistentes.
**Mitigación.** Egress default-deny por puerto; inspección de protocolo.

## Referencias
- MITRE ATT&CK TA0011 (Command and Control).
- Zeek/Suricata para detección de beaconing y anomalías de protocolo; feeds de IOC de dominios/IP C2.
- Atomic Red Team — atomics T1071.*, T1105, T1572.
