---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- exfiltracion
- deteccion
- defensa
title: 'ATT&CK Exfiltración - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0010**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **saca los datos** de la red. Suele venir después de [[ATT&CK Recolección - Detección y Defensa]] y usar el canal de [[ATT&CK Comando y Control - Detección y Defensa]].

## T1041 — Exfiltration Over C2 Channel
**Qué es.** Sacar los datos por el mismo canal C2 ya establecido.
**Uso del adversario (conceptual).** Sube el blob comprimido/cifrado (T1560) a la infraestructura C2, mezclándolo con el beaconing normal.
**Detección.** Volumen de subida (upload) anómalo hacia el destino C2; ratio subida/bajada invertido respecto a la baseline del host; picos de egress fuera de horario. NetFlow + DLP.
**Mitigación/endurecimiento.** DLP saliente; egress filtering default-deny; límites/alertas por volumen de datos salientes; inspección TLS en el proxy.

## T1567 — Exfiltration Over Web Service (nube, code repos, paste sites)
**Qué es.** Usar servicios legítimos (Google Drive, Dropbox, GitHub, pastebin, Telegram) como destino de exfiltración para mezclarse con tráfico confiable.
**Detección.** Subidas grandes a servicios de almacenamiento no aprobados; uploads a repos/paste sites por procesos no esperados; uso de APIs de nube desde hosts que no deberían.
**Mitigación.** CASB / control de aplicaciones en la nube; allowlist de servicios aprobados; DLP; bloqueo de servicios de intercambio no autorizados.
**Prueba atómica.** Atomic Red Team T1567.002 sube un archivo de datos de prueba a un servicio de nube para validar la detección de exfiltración web.

## T1048 — Exfiltration Over Alternative Protocol (DNS, ICMP, FTP)
**Qué es.** Exfiltrar por un protocolo distinto al C2: DNS tunneling, ICMP, FTP/SFTP a un servidor externo.
**Detección.** DNS con nombres largos/alta entropía y volumen alto (mismo indicador que en C2); ICMP con payloads grandes; FTP saliente a destinos no aprobados.
**Mitigación.** DNS por resolvers con análisis; bloquear ICMP saliente arbitrario; egress filtering por protocolo.

## T1030 — Data Transfer Size Limits / T1029 — Scheduled Transfer
**Qué es.** Fragmentar la exfiltración en trozos chicos y/o programarla en horarios "normales" para no disparar umbrales de volumen.
**Detección.** Transferencias periódicas y regulares de tamaño similar (patrón); correlación de muchos envíos chicos al mismo destino a lo largo del tiempo.
**Mitigación.** Baselines de egress por host y por horario; detección de patrón, no solo de volumen puntual.

## Relación con impacto y ransomware
La exfiltración precede a la **doble extorsión**: el atacante roba los datos *antes* de cifrarlos, para amenazar con publicarlos aunque la víctima tenga backups. Detectar exfiltración masiva es a menudo la última ventana antes del cifrado de [[ATT&CK Impacto - Detección y Defensa]].

## Referencias
- MITRE ATT&CK TA0010 (Exfiltration).
- DLP, CASB y egress filtering como controles primarios; NetFlow/Zeek para volumen y patrón.
- Atomic Red Team — atomics T1041, T1567.*, T1048.*.
