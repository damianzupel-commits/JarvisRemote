---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- herramienta
- sca
- snyk
title: Snyk en la Práctica
updated: '2026-07-28T00:00:00.000000+00:00'
---

SCA (con un componente SAST también) comercial, con tier gratuito para proyectos individuales/open-source. Ver [[Herramientas SAST y SCA - Resumen]]. Su diferenciador frente a Trivy: base de datos de vulnerabilidades curada manualmente por un equipo de investigadores de seguridad (no solo agregada de NVD/OSV automáticamente), y **reachability analysis** más maduro — determina si el código del proyecto realmente invoca la función vulnerable de la dependencia, no solo si la dependencia está presente.

## Uso básico
```bash
snyk auth                 # requiere cuenta (gratuita para uso individual/OSS)
snyk test                 # escanea dependencias del proyecto en el directorio actual
snyk test --all-projects  # monorepo con múltiples manifiestos
snyk monitor              # snapshot continuo -- alerta si sale una CVE nueva para deps ya instaladas
snyk code test            # el componente SAST (Snyk Code), separado del SCA
```

## `snyk test` vs `snyk monitor`: la distinción importante
`snyk test` es un chequeo puntual (para CI, falla el build si hay algo por encima del umbral configurado). `snyk monitor` sube un snapshot de las dependencias actuales y las sigue vigilando en el dashboard de Snyk — si mañana se publica una CVE nueva para una versión que el proyecto ya tenía instalada (y no tocó), Snyk avisa igual, sin necesidad de correr un scan nuevo. Esto cubre el caso de [[OWASP A06 - Componentes Vulnerables y Desactualizados]] donde el riesgo apareció *después* del último build, no en él.

## Reachability analysis (por qué reduce ruido más que otras SCA)
```
✗ High severity vulnerability found in lodash
  Introduced through: my-app > lodash@4.17.15
  This vulnerability is NOT reachable from your code.
```
Snyk indica explícitamente si el path de código del proyecto llega a ejecutar la función específica que tiene la CVE, no solo si la librería está en el árbol de dependencias. Esto es lo más efectivo para bajar el volumen de findings de "sí, técnicamente vulnerable, pero imposible de explotar en este proyecto porque esa función nunca se llama" — el tipo de ruido que más rápido hace que un equipo empiece a ignorar los reportes de SCA en general.

## Fortaleza específica en npm/JS
El ecosistema de mayor cobertura y precisión histórica de Snyk es npm — relevante directo para [[Seguridad en JavaScript y TypeScript]]. Para Python/Kotlin la cobertura es buena pero Trivy es una alternativa gratuita comparable; para JS, la ventaja de Snyk sobre `npm audit` nativo suele notarse más en la calidad de la clasificación de severidad y en menos falsos positivos.

## Falsos positivos / matices
- Igual que con Trivy, una CVE marcada como reachable puede seguir sin ser explotable en la práctica si el input a esa función siempre es controlado internamente (nunca llega dato externo hasta ahí) — reachability analysis dice "el código llega a esa función", no "un atacante puede controlar el input en ese punto". Sigue haciendo falta criterio humano en el último tramo.
- Licencias: Snyk también reporta problemas de *licencia* de dependencias (ej. una GPL en un proyecto propietario) — esto no es una vulnerabilidad de seguridad, es un riesgo legal/compliance distinto; no tratar esos findings con la misma urgencia que una CVE.
