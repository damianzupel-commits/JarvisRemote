---
author: jarvis
category: metodologia-investigacion
created: '2026-08-13T00:00:39.467500+00:00'
tags:
- forense-digital
- respuesta-a-incidentes
- osint
- pfa-ingreso
title: Metodologías de Investigación de Cibercrimen
updated: '2026-08-13T00:00:39.467500+00:00'
---

## Respuesta a incidentes: PICERL (SANS Institute)

El **SANS Institute** (organización de referencia mundial en formación de ciberseguridad, autora de las certificaciones GIAC como GCIH y GCFA) documenta en su *Incident Handler's Handbook* el modelo **PICERL**, el marco de respuesta a incidentes más enseñado a nivel global y base de numerosos playbooks corporativos y curricula de certificación:

1. **Preparation (Preparación)**: tener políticas, herramientas, contactos y un equipo entrenado *antes* de que ocurra un incidente.
2. **Identification (Identificación)**: detectar y confirmar que efectivamente ocurrió un incidente (vs. un falso positivo).
3. **Containment (Contención)**: limitar el daño -- aislar sistemas afectados sin destruir evidencia.
4. **Eradication (Erradicación)**: eliminar la causa raíz (malware, acceso no autorizado, vulnerabilidad explotada).
5. **Recovery (Recuperación)**: restaurar sistemas a operación normal, con monitoreo reforzado.
6. **Lessons Learned (Lecciones aprendidas)**: revisión posterior que retroalimenta la fase de Preparación -- el modelo es cíclico, cada incidente mejora la preparación para el siguiente.

Este modelo se solapa parcialmente con el proceso forense de [[Estándares Forenses: NIST SP 800-86 e ISO/IEC 27037]] pero tiene un objetivo distinto: PICERL prioriza **restaurar la operación segura**, mientras que el proceso forense (NIST 800-86 / ISO 27037) prioriza **preservar evidencia con validez legal** -- en una investigación real ambos objetivos conviven y a veces entran en tensión (ej. contener rápido puede alterar evidencia volátil).

## Análisis forense de sistemas y redes

Dentro de la fase de análisis (ver NIST SP 800-86), la investigación técnica de cibercrimen se apoya en dos ramas complementarias:

- **Forense de sistemas (host forensics)**: análisis de discos, memoria RAM, registros del sistema operativo, logs de aplicaciones -- reconstruye qué pasó *en* un equipo.
- **Forense de red (network forensics)**: análisis de tráfico capturado, logs de firewalls/proxies/IDS, metadatos de conexión -- reconstruye qué pasó *entre* equipos (origen, destino, protocolo, volumen, timing).

Ambas alimentan la reconstrucción de una línea de tiempo del incidente -- ver [[Análisis de Enlaces y Normalización de Timeline Forense]] para la técnica concreta de unificar timestamps de fuentes heterogéneas.

## OSINT ético y sus límites legales

La inteligencia de fuentes abiertas (**OSINT**, Open Source Intelligence) es una herramienta legítima y ampliamente usada en investigación de cibercrimen, pero su legalidad depende enteramente de **cómo** se recolecta la información, no solo de que la fuente sea "pública":

- Es OSINT legítimo mientras la información se obtenga **sin eludir ningún control de acceso** (login, paywall, CAPTCHA, permiso). En el momento en que se elude un control de ese tipo, la actividad deja de ser OSINT y pasa a ser acceso no autorizado.
- El tratamiento de datos personales obtenidos por OSINT sigue sujeto a marcos de protección de datos (en Argentina, la Ley 25.326 de Protección de Datos Personales) -- "la fuente es pública" no exime de esas obligaciones.
- Principios éticos centrales: propósito claro y legítimo de la recolección, minimización de datos (recolectar solo lo necesario para la investigación), no exponer ni divulgar información sensible de terceros ajenos al caso, documentar la fuente y el método igual que cualquier otra evidencia (trazabilidad).
- La distinción clave que debe mantenerse siempre en este vault y en cualquier ejercicio de estudio: OSINT sobre **conceptos y fuentes públicas genéricas** (esto, por ejemplo) es investigación de referencia; OSINT dirigido a una **persona real identificable** es intrusivo y requiere marco legal específico (orden judicial, caso abierto) -- nunca se hace como ejercicio de estudio libre.

## Fuentes

- [SANS Incident Handler's Handbook and PICERL Methodology -- The Art of Service](https://theartofservice.com/frameworks/sans-incident-handler-s-handbook-and-picerl-methodology)
- [SANS 6-Step Incident Response Framework Guide -- SentinelOne](https://www.sentinelone.com/cybersecurity-101/cybersecurity/sans-incident-response/)
- [SANS PICERL Model: IR Lifecycle Explained -- ForensicSpot](https://forensicspot.com/topics/incident-response-and-management/sans-picerl-model)
- [NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response -- CSRC (NIST)](https://csrc.nist.gov/pubs/sp/800/86/final)
- [What is OSINT (Open-Source Intelligence)? -- SANS Institute](https://www.sans.org/blog/what-is-open-source-intelligence)
- [Ethics in OSINT: Is Open-Source Intelligence Legal? -- HENSOLDT](https://www.hensoldt.net/news/ethics-in-osint-is-open-source-intelligence-legal)
- [Is OSINT Legal? Yes, But Here's Where the Line Is -- EspectroSINT](https://www.espectrosint.com/blog/is-osint-legal)