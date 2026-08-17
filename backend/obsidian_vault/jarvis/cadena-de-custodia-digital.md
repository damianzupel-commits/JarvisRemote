---
author: jarvis
category: forense-digital
created: '2026-08-13T00:00:08.752432+00:00'
tags:
- forense-digital
- cadena-de-custodia
- pfa-ingreso
title: Cadena de Custodia Digital
updated: '2026-08-13T00:00:08.752432+00:00'
---

## Qué es

La cadena de custodia es el **procedimiento documentado** que registra de forma continua e ininterrumpida quién tuvo acceso a una evidencia digital, cuándo, dónde, y qué acción se realizó sobre ella, desde el momento de su recolección hasta su presentación en un proceso judicial. El objetivo es garantizar que la evidencia presentada ante el tribunal es la misma que se recolectó en la escena, sin alteraciones.

## Por qué importa

Si la cadena de custodia se rompe (un eslabón sin documentar, un hash que no coincide, un acceso no registrado), la evidencia puede ser **impugnada y declarada inadmisible**, incluso si el contenido en sí es genuino -- lo que se pierde es la *garantía* de integridad, no necesariamente la integridad real. Esto conecta directamente con [[Hashing SHA-256 y Firma Digital: Integridad y No Repudio en Evidencia Digital]]: el hash es la herramienta técnica concreta que sostiene la cadena de custodia.

## Qué debe documentar cada eslabón

Según la guía de buenas prácticas de la Procuración General de la Nación (Argentina) y los estándares internacionales (ver [[Estándares Forenses: NIST SP 800-86 e ISO/IEC 27037]]), un registro de cadena de custodia completo incluye:

- **Identificador único** de la evidencia (etiqueta, número de secuestro/caso).
- **Fecha y hora** de cada recolección, transferencia o acceso.
- **Quién recolectó** la evidencia (nombre, rol, fuerza/organismo).
- **Quién la recibió** en cada transferencia posterior.
- **Ubicación física** de la evidencia en cada momento.
- **Descripción breve** de cada elemento (marca, modelo, número de serie, capacidad).
- **Toda acción realizada** sobre la evidencia (ej. clonado, análisis) con justificación y responsable.
- **Valor hash** (típicamente SHA-256) calculado en el momento de la adquisición y recalculado en cada verificación posterior -- si no coincide, la cadena está rota.

## Cómo se documenta correctamente en la práctica

1. **En la escena**: fotografiar el dispositivo antes de tocarlo, en su estado y ubicación original.
2. **Adquisición**: usar un **bloqueador de escritura (write blocker)** para evitar modificar el original al copiarlo; calcular el hash del original.
3. **Duplicación forense**: crear una copia bit a bit (imagen forense), calcular el hash de la copia y verificar que coincide con el del original.
4. **Embalaje**: bolsas antiestáticas o de papel/cartón (nunca plástico común, por electricidad estática y humedad), puertos fajados con cinta de evidencia, baterías guardadas por separado, lejos de campos magnéticos.
5. **Trabajo siempre sobre la copia**, nunca sobre el original -- el original queda preservado y trazado.
6. **Registro escrito** (formulario de cadena de custodia) en cada transferencia, firmado por quien entrega y quien recibe.

## Fuentes

- [La cadena de custodia de la prueba digital -- TrueData Consultores](https://www.truedataconsultores.com/la-cadena-de-custodia-de-la-prueba-digital/)
- [Cadena de custodia digital: guía ISO 27037 para evidencia electrónica -- DigitalPerito](https://digitalperito.es/blog/cadena-custodia-digital-guia-iso-27037-2026/)
- [La Procuración General aprobó una nueva guía de buenas prácticas para la cadena de custodia -- Fiscales.gob.ar](https://www.fiscales.gob.ar/procuracion-general/la-procuracion-general-aprobo-una-nueva-guia-de-buenas-practicas-para-la-cadena-de-custodia-en-el-marco-del-sistema-acusatorio/)
- [Chain of Custody for Digital Evidence: Best Practices -- Forensic Discovery](https://forensicdiscovery.expert/blog/chain-of-custody-for-digital-evidence-best-practices/)
- [Best Practices for Using Write Blockers in Forensic Imaging -- Hawk Eye Forensic](https://hawkeyeforensic.com/best-practices-for-using-write-blockers-in-forensic-imaging/)