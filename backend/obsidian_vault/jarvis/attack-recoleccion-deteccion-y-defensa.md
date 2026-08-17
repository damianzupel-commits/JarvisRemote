---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- recoleccion
- deteccion
- defensa
title: 'ATT&CK Recolección - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0009**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **junta los datos de interés** antes de sacarlos (ver [[ATT&CK Exfiltración - Detección y Defensa]]).

## T1005 — Data from Local System / T1039 — Data from Network Shared Drive
**Qué es.** Recorrer discos locales y shares de red copiando documentos, bases y config de valor.
**Uso del adversario (conceptual).** Busca por extensión/keyword (docs, planillas, credenciales, PII) y consolida en una carpeta de staging.
**Detección.** Lectura masiva de archivos por un proceso en poco tiempo; acceso a shares sensibles fuera de patrón; creación de una carpeta de staging con muchos archivos copiados. UEBA/DLP.
**Mitigación/endurecimiento.** Mínimo privilegio sobre datos; DLP; canary/honey files que alertan al ser leídos; auditoría de acceso a repositorios sensibles.

## T1560 — Archive Collected Data (compresión/cifrado previo a exfiltrar)
**Qué es.** Comprimir/cifrar lo recolectado (ZIP/RAR/7z, a veces con contraseña) para exfiltrar en un solo blob y evadir inspección.
**Detección.** Creación de archivos comprimidos grandes en temp/appdata; uso de `rar`/`7z`/`tar` por procesos anómalos; archivos protegidos con contraseña recién creados. Alta entropía (ver heurística de entropía de Jarvis en `behavioral_watcher.py`, misma señal que ransomware).
**Mitigación.** DLP que inspeccione o bloquee archivos cifrados salientes; alertar sobre staging; egress filtering.
**Prueba atómica.** Atomic Red Team T1560.001 crea un archivo comprimido de datos de prueba para validar la detección de staging.

## T1114 — Email Collection / T1213 — Data from Information Repositories
**Qué es.** Recolectar correo (buzones, PST, reglas de auto-forward) o datos de repos internos (SharePoint, wikis, Confluence, código).
**Detección.** Reglas de reenvío automático nuevas (señal clásica de BEC); descargas masivas de un repositorio; exportación de buzones.
**Mitigación.** Alertar sobre reglas de auto-forward; DLP en correo; mínimo privilegio y auditoría en repos.

## T1056 — Input Capture (keylogging) / T1113 — Screen Capture / T1123 — Audio Capture
**Qué es.** Capturar teclas, pantalla o audio del usuario comprometido.
**Detección.** Hooks de teclado (SetWindowsHookEx); acceso a APIs de captura de pantalla/audio por procesos no esperados; archivos de log de teclas. Comportamiento típico de spyware/RAT (ver [[Familias de Malware - Taxonomía Detección y Defensa]]).
**Mitigación.** EDR conductual; mínimo privilegio; alertar sobre acceso a webcam/mic.

## Referencias
- MITRE ATT&CK TA0009 (Collection).
- DLP y canary files como controles de detección temprana.
- Atomic Red Team — atomics T1005, T1560.*, T1114, T1056.*.
