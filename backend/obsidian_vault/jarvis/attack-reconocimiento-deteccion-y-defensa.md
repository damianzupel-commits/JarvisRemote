---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- reconocimiento
- resource-development
- deteccion
- defensa
title: 'ATT&CK Reconocimiento - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0043**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Fase **pre-compromiso**: el adversario recolecta información para planear la intrusión, antes de tocar nada. Cubre también, al final, la táctica hermana **Resource Development (TA0042)**.

Nota transversal relacionada: [[Fundamentos de Nmap y Tipos de Escaneo]] (reconocimiento activo de red del lado propio/autorizado).

## T1595 — Active Scanning
**Qué es.** Sondeo directo de la infraestructura del objetivo: barridos de IP, escaneo de puertos, fingerprint de servicios y web.
**Uso del adversario (conceptual).** Envía tráfico a rangos y puertos de la víctima para mapear qué está expuesto y con qué versión, insumo para elegir vector de acceso.
**Detección.** Muchas conexiones a puertos secuenciales/cerrados desde una misma fuente en poco tiempo; picos de SYN sin completar handshake; hits a rutas web inexistentes. Se ve en logs de firewall/IDS y access logs del servidor.
**Mitigación/endurecimiento.** Minimizar superficie expuesta a Internet; rate-limiting y geobloqueo donde aplique; WAF; no publicar banners con versión. El escaneo en sí no se puede "prevenir", pero sí reducir lo que revela.
**Prueba atómica.** Atomic Red Team T1595 incluye pruebas que lanzan escaneos de puertos/servicios contra un objetivo de laboratorio para verificar si el IDS/firewall los registra.

## T1590/T1591/T1589 — Gather Victim Info (red, org, identidad)
**Qué es.** Recolección **pasiva** vía fuentes abiertas (OSINT): registros DNS/WHOIS, rangos IP, organigrama, emails, tecnologías usadas.
**Uso del adversario.** Arma la lista de objetivos y el pretexto de phishing sin tocar la red de la víctima (casi indetectable desde el lado defensivo).
**Detección.** Muy limitada por diseño (ocurre fuera del perímetro). Señales indirectas: consultas WHOIS/DNS anómalas, scraping de sitios corporativos/LinkedIn.
**Mitigación.** Reducir huella pública (datos de empleados, metadatos en documentos, subdominios olvidados); monitorear registros de dominios parecidos (typosquatting) como insumo anti-phishing; concientización.
**Prueba atómica.** T1589/T1590 tienen atomics que ejecutan consultas OSINT/DNS de reconocimiento para probar visibilidad de egress.

## T1598 — Phishing for Information
**Qué es.** Engaño para que la víctima revele información (no entregar malware todavía), ej. falsos formularios o llamadas de "soporte".
**Detección.** Filtros de correo (dominios recién registrados, enlaces a portales de captura), reportes de usuarios, dominios look-alike.
**Mitigación.** MFA resistente a phishing (FIDO2), gateway de correo, entrenamiento y un botón fácil de "reportar phishing".

## Resource Development (TA0042) — preparación del atacante
**Qué es.** El adversario **construye/compra su infraestructura**: registra dominios (T1583), levanta o alquila servidores (T1584), crea cuentas (T1585), desarrolla o compra malware y capacidades (T1587/T1588).
**Detección (indirecta, del lado defensor).** Threat intel feeds de dominios/IP recién registrados o maliciosos; certificados TLS de dominios look-alike (Certificate Transparency); correlación con IOCs conocidos.
**Mitigación.** Bloqueo por reputación/edad de dominio; monitoreo de marca y typosquatting; integrar feeds de IOC en el DNS y el proxy.

## Referencias
- MITRE ATT&CK TA0043 (Reconnaissance) y TA0042 (Resource Development).
- CISA — reducción de superficie de ataque expuesta a Internet.
- Atomic Red Team — atomics de las técnicas T1595, T1589, T1590, T1598.
