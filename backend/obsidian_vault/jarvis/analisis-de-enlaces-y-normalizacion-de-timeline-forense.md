---
author: jarvis
category: analisis-de-enlaces
created: '2026-08-13T00:01:24.560722+00:00'
tags:
- analisis-de-enlaces
- forense-digital
- grafos
- pfa-ingreso
title: Análisis de Enlaces y Normalización de Timeline Forense
updated: '2026-08-13T00:01:24.560722+00:00'
---

## Análisis de enlaces (link analysis) y teoría de grafos

El análisis de enlaces modela una investigación como un **grafo**: entidades (personas, cuentas, direcciones IP, dispositivos, transacciones) como **nodos**, y relaciones entre ellas (comunicación, transferencia, co-ocurrencia) como **aristas**. El objetivo es encontrar patrones estructurales que no son evidentes mirando cada entidad por separado -- quién conecta a quién, quién es un intermediario clave, qué grupos están más conectados entre sí que con el resto de la red. Ver también [[Algoritmo de Dijkstra]] para el algoritmo base de camino más corto sobre el que se apoyan varias de estas métricas.

**Centralidad de intermediación (betweenness centrality)**: mide cuántas veces un nodo aparece en el camino más corto entre otros dos nodos del grafo. Un nodo con alta centralidad de intermediación es un **puente o cuello de botella** -- en una investigación, suele señalar un intermediario clave (una cuenta, un dispositivo, una persona) por el que pasa comunicación o flujo entre grupos que de otro modo no estarían conectados, aunque ese nodo no sea el de mayor actividad individual.

**Detección de comunidades (community detection)**: identifica subgrupos ("comunidades") dentro de una red donde hay estadísticamente más conexiones internas que hacia el resto del grafo. Un algoritmo clásico es **Girvan-Newman**: elimina iterativamente las aristas con mayor centralidad de intermediación de arista (edge betweenness), lo que separa progresivamente al grafo en comunidades -- las aristas que "conectan" comunidades distintas tienden a tener alta centralidad de intermediación porque son la única vía entre grupos. En una investigación, esto ayuda a distinguir, por ejemplo, distintas células o grupos dentro de una red más amplia de contactos.

Este es exactamente el tipo de análisis que aplica el módulo de investigación de Jarvis (`app/investigation/`) sobre el grafo de entidades y relaciones que arma a partir de la evidencia cargada -- la teoría es la misma que describe esta nota, aplicada a un caso concreto en vez de a datos genéricos.

## Normalización de timeline forense a UTC

En cualquier investigación con más de una fuente de datos (logs de distintos sistemas, metadatos de distintos dispositivos, capturas de red), los timestamps llegan en **formatos, resoluciones y zonas horarias distintas** -- algunos en hora local del dispositivo, otros en UTC, algunos en ASCII legible, otros en formatos binarios propietarios. Mezclar zonas horarias sin normalizar es una de las formas más comunes de arruinar una reconstrucción de línea de tiempo (un evento puede parecer ocurrir "antes" de su causa solo por un desfase de huso horario no corregido).

**Buena práctica estándar en DFIR (Digital Forensics and Incident Response)**: normalizar **todos** los timestamps a **UTC** y a un formato estandarizado como **ISO 8601**, antes de construir o comparar la línea de tiempo. Esto permite:
- Comparar directamente eventos de fuentes distintas sin conversión mental de husos horarios.
- Ordenar cronológicamente de forma confiable (sort correcto) todos los eventos del caso.
- Evitar errores de causalidad aparente por mezclar hora local y UTC en la misma tabla.

Antes de normalizar, es necesario **verificar la zona horaria original de cada fuente** (la del sistema operativo del dispositivo, la del servidor de logs, la del propio reloj de captura) -- normalizar mal (asumir una zona horaria incorrecta) es peor que no normalizar, porque genera una falsa sensación de certeza en el orden de los eventos.

Esta es la misma lógica que aplica el módulo de investigación de Jarvis al normalizar timestamps de evidencia heterogénea antes de construir el timeline del caso.

## Fuentes

- [Community Detection -- ScienceDirect Topics](https://www.sciencedirect.com/topics/computer-science/community-detection)
- [A Comparative Analysis of Community Detection Algorithms on Artificial Networks -- Scientific Reports (Nature)](https://www.nature.com/articles/srep30750)
- [Organization Network Analysis & Community Detection of Graphs -- IJERT](https://www.ijert.org/organization-network-analysis-community-detection-of-graphs)
- [SoK: Timeline based event reconstruction for digital forensics -- arXiv](https://arxiv.org/html/2504.18131v1)
- [Was the clock correct? Exploring timestamp interpretation through time anchors for digital forensic event reconstruction -- ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2666281724000787)
- [Chronos vs Chaos: The Art (and Pain) of Building a DFIR Timeline -- Mathias Fuchs (Medium)](https://medium.com/@mathias.fuchs/chronos-vs-chaos-the-art-and-pain-of-building-a-dfir-timeline-a40c6e37106d)