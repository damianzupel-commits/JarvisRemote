---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- herramienta
- sast
- codeql
title: CodeQL en la Práctica
updated: '2026-07-28T00:00:00.000000+00:00'
---

SAST de GitHub/Microsoft, gratuito para repos públicos y para uso open-source (licencia distinta para uso interno en repos privados de organizaciones — verificar los términos vigentes antes de asumir gratuidad en un caso comercial privado). Ver [[Herramientas SAST y SCA - Resumen]]. Su diferencial frente a Semgrep/Bandit: no hace matching sintáctico sobre patrones de código, sino que **compila el proyecto a una base de datos relacional** (nodos = elementos del AST + call graph + control flow graph) y corre queries sobre esa base con un lenguaje de queries propio (QL) que soporta **taint tracking real, interprocedural**.

## Por qué el dataflow real importa
```python
# Semgrep con reglas puramente sintácticas puede perderse esto: el dato pasa
# por una función intermedia antes de llegar al sink
def get_param(request):
    return request.args.get("q")

def run_query(term):
    cursor.execute(f"SELECT * FROM items WHERE name = '{term}'")  # sink

def handler(request):
    term = get_param(request)       # fuente
    run_query(term)                 # el taint cruzó dos funciones para llegar acá
```
CodeQL rastrea el flujo del dato desde `request.args.get("q")` (fuente, marcada como no confiable en sus librerías estándar de modelado) a través de `get_param` y `run_query` hasta el `.execute()` (sink conocido de [[SQL Injection]]), aunque estén en funciones/archivos distintos. Reglas sintácticas locales (Semgrep sin Pro, Bandit) típicamente no siguen el dato a través de ese salto de función.

## Uso básico
```bash
# crear la base de datos (para lenguajes compilados hace falta poder buildear el proyecto)
codeql database create mi-db --language=python --source-root=.

# correr un query suite estándar de seguridad
codeql database analyze mi-db codeql/python-queries --format=sarif-latest --output=results.sarif
```
El output SARIF es un formato estándar que también producen otras herramientas (incluido Semgrep) — facilita consolidar findings de distintos scanners en un solo pipeline de triage.

## El costo de la precisión: setup más pesado
Para lenguajes compilados (Java, Kotlin, C/C++), CodeQL necesita poder **ejecutar el build real** del proyecto para observar cómo se arma el grafo — eso implica tener el toolchain completo instalado y funcionando, no solo el código fuente. Para lenguajes interpretados (Python, JS) el setup es más liviano porque no hace falta compilar. Esto hace que CodeQL sea más pesado de integrar que Semgrep/Bandit (que solo leen archivos de texto), y usualmente vive en CI (corrida completa, más lenta) en vez de en cada save local.

## Falsos positivos / limitaciones
- **Modelado incompleto de fuentes/sinks custom**: CodeQL viene con librerías estándar que ya saben qué es una "fuente no confiable" o un "sink peligroso" para APIs comunes (Flask, Django, Express) — pero si el proyecto tiene su propio wrapper de framework, CodeQL no sabe automáticamente que ese wrapper también es una fuente, salvo que se modele explícitamente en QL.
- **Sanitización no reconocida**: igual que con cualquier taint tracker, si el proyecto sanitiza el dato con una función interna no estándar, CodeQL puede no reconocerla como "el taint se limpió acá" y seguir marcando el flujo completo como vulnerable — hace falta modelarla como sanitizer explícitamente para bajar ese ruido.
- Menos práctico para checks rápidos de estilo/convención — para eso, Semgrep sigue siendo más ágil de configurar y correr.

## Cuándo priorizarlo sobre Semgrep
Cuando el proyecto tiene lógica de negocio con varias capas entre el input externo y el sink (típico en backends grandes), y los falsos negativos de reglas sintácticas locales importan más que la velocidad de setup.
