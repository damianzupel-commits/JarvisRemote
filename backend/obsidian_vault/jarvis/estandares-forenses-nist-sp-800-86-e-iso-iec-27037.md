---
author: jarvis
category: estandares-forenses
created: '2026-08-13T00:00:24.372276+00:00'
tags:
- forense-digital
- estandares
- nist
- iso-27037
- pfa-ingreso
title: 'Estándares Forenses: NIST SP 800-86 e ISO/IEC 27037'
updated: '2026-08-13T00:00:24.372276+00:00'
---

## NIST SP 800-86 -- "Guide to Integrating Forensic Techniques into Incident Response"

Publicación del **National Institute of Standards and Technology** (EE. UU.), disponible públicamente en el Computer Security Resource Center (CSRC). No es un manual paso a paso ni un documento legal -- se presenta explícitamente desde una **perspectiva de TI**, no de aplicación de la ley, orientada a ayudar a organizaciones a investigar incidentes de seguridad y resolver problemas operativos de TI aplicando técnicas forenses.

**Estructura del proceso forense según NIST SP 800-86** (proceso genérico de 4 fases, reutilizado y citado en casi toda la bibliografía forense posterior):

1. **Recolección (Collection)**: identificar, etiquetar, registrar y adquirir datos de las fuentes relevantes, siguiendo procedimientos que preserven la integridad de los datos.
2. **Examen (Examination)**: procesar los datos recolectados con herramientas forenses (combinando extracción automática y revisión manual), evaluando y extrayendo los datos de interés preservando su integridad.
3. **Análisis (Analysis)**: analizar los resultados del examen usando métodos técnica y legalmente justificables para obtener información útil que responda las preguntas que motivaron la recolección.
4. **Reporte (Reporting)**: presentar los resultados del análisis, incluyendo una descripción de las acciones realizadas, explicación de las herramientas y procedimientos elegidos, y recomendaciones de mejora a políticas, guías, herramientas u otros aspectos del proceso forense.

Cubre cuatro categorías principales de fuentes de datos: **archivos, sistemas operativos, tráfico de red y aplicaciones**, con técnicas de recolección, examen y análisis específicas para cada una.

## ISO/IEC 27037:2012 -- "Guidelines for identification, collection, acquisition and preservation of digital evidence"

Estándar internacional de la **ISO/IEC** (comité de seguridad de la información), referencia global para el tratamiento de evidencia digital y su **admisibilidad legal** entre jurisdicciones. Define cuatro procesos centrales, distintos de los de NIST 800-86 pero complementarios (ISO se enfoca en la etapa previa al análisis: cómo asegurar que la evidencia llega intacta y documentada al analista):

1. **Identificación (Identification)**: reconocer qué constituye evidencia digital potencialmente relevante para la investigación.
2. **Recolección (Collection)**: reunir la evidencia digital de forma que se preserve su integridad -- típicamente implica remover el dispositivo físico.
3. **Adquisición (Acquisition)**: crear una copia (imagen forense) de la evidencia digital para su análisis, garantizando que el original queda inalterado.
4. **Preservación (Preservation)**: proteger la evidencia digital de alteración o destrucción durante todo el proceso de investigación (custodia, almacenamiento, control de acceso).

Aplica a medios de almacenamiento digital estándar (discos rígidos, ópticos, magneto-ópticos), y también a teléfonos móviles, PDAs, dispositivos electrónicos personales y tarjetas de memoria.

## Cómo se combinan en la práctica

ISO/IEC 27037 gobierna el momento de **contacto inicial con la evidencia** (identificar-recolectar-adquirir-preservar, con foco en no contaminarla), y NIST SP 800-86 gobierna lo que ocurre **después**, cuando un analista ya tiene una copia forense y necesita examinarla, analizarla y reportar hallazgos. Ambos comparten el principio rector de [[Cadena de Custodia Digital]]: cada paso debe quedar documentado y ser reproducible.

## Fuentes

- [NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response -- CSRC (NIST)](https://csrc.nist.gov/pubs/sp/800/86/final)
- [NIST SP 800-86 -- PDF completo, NIST Legacy Publications](https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-86.pdf)
- [ISO/IEC 27037:2012 -- ISO.org (ficha oficial del estándar)](https://www.iso.org/standard/44381.html)
- [ISO/IEC 27037:2012(en) -- Online Browsing Platform, ISO](https://www.iso.org/obp/ui/#iso:std:iso-iec:27037:ed-1:v1:en)
- [Guidelines for Identification, Collection, Acquisition and Preservation of Digital Evidence -- UNODC (resumen educativo)](https://www.unodc.org/e4j/data/_university_uni_/guidelines_for_identification_collection_acquisition_and_preservation_of_digital_evidence.html)