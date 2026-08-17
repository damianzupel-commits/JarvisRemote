---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- deteccion
- firmas
- comportamiento
- defensa
title: 'Higiene de Detección - Firmas vs Comportamiento'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Nota transversal de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Los dos grandes enfoques de detección son complementarios, no rivales. Entender cuándo sirve cada uno evita puntos ciegos.

## Detección por firma (estática, basada en indicadores conocidos)
**Qué es.** Matchear patrones conocidos: hashes, strings, reglas YARA, firmas de AV, IOCs (dominios/IP/URLs).
**Fortalezas.** Rápida, barata, muy pocos falsos positivos, atribución clara ("esto es X"). Ideal para amenazas conocidas y a escala.
**Debilidades.** **Ciega ante lo nuevo**: no ve malware polimórfico (cambia su código), fileless (no hay archivo) ni zero-days. Siempre reactiva — llega después de que alguien ya vio la muestra.
**En Jarvis.** El motor YARA (`yara_scanner.py` + `starter.yar`) y ClamAV (`clamav_scanner.py`) son detección por firma. La propia regla `Suspicious_Persistence_Registry_Run_Key` documenta su límite en el `meta`: "sola no es concluyente, combinar con otro motor/contexto".

## Detección por comportamiento (dinámica, basada en lo que hace)
**Qué es.** Observar acciones y secuencias: process ancestry anómala, inyección de memoria, cifrado masivo, beaconing, ráfagas de discovery. Incluye heurística, anomalía y UEBA.
**Fortalezas.** Detecta amenazas **desconocidas** por su comportamiento, aunque el binario nunca se haya visto. Cubre fileless, polimórfico y zero-day.
**Debilidades.** Más falsos positivos (actividad legítima puede parecer maliciosa); necesita **baselines** buenas y telemetría rica; más costosa de operar y afinar.
**En Jarvis.** La heurística de ransomware de `behavioral_watcher.py` (≥15 eventos de archivo en 15s con entropía ≥7.5) es detección conductual pura: no le importa qué binario cifra, solo el patrón — por eso cubre ransomware sin firma. El `process_monitor.py` vigila el propio proceso.

## Por qué se combinan (defensa en capas)
Ninguno solo alcanza. La firma limpia rápido el ruido conocido y libera al motor conductual para lo raro; el comportamiento cubre el hueco que la firma no puede ver. Es [[Defensa en Profundidad]] aplicada a detección: superponer capas con modos de falla distintos.

## Enfoques modernos que las cruzan
- **IOAs (Indicators of Attack)** vs IOCs: describir la *intención/comportamiento* (ej. "proceso de Office lanzando PowerShell que descarga y ejecuta") en vez de un artefacto puntual — sobrevive a que el atacante cambie hashes/dominios.
- **Detección basada en ATT&CK**: escribir reglas mapeadas a técnicas y medir cobertura (ver [[MITRE ATT&CK - Fundamentos del Marco]]).
- **ML/EDR conductual**: modelos sobre secuencias de eventos; potentes pero requieren datos y validación (los números "99%" de laboratorio no se trasladan directo a producción).
- **Threat hunting**: búsqueda proactiva de hipótesis de compromiso sobre la telemetría, sin esperar una alerta.

## Higiene práctica
1. **Telemetría primero**: sin logs (line-command, Script Block Logging, red por proceso) no hay ninguna de las dos. Ver [[Hardening y Endurecimiento del Endpoint]].
2. **Baselines**: lo que es "normal" en tu entorno; sin eso la anomalía no significa nada (recomendación central de CISA/LOTL).
3. **Reducir falsos positivos con contexto**: combinar señales (como hacen las reglas de `starter.yar` que exigen "3 de estos indicadores").
4. **Probar la detección**: emular técnicas y verificar que dispara — un control no probado es un control roto (ver [[Probar la Detección de Forma Segura - EICAR Atomic Red Team Emulación]]).
5. **Feeds de IOC actualizados** para la capa de firma; **afinado continuo** para la conductual.

## Referencias
- MITRE ATT&CK (detección por técnica; data sources).
- CISA/NSA/FBI — LOTL (baselines, UEBA, process ancestry).
- Documentación de Jarvis: `app/malware/` (firma YARA/ClamAV + heurística conductual conviviendo en el mismo pipeline `engine.py`).
