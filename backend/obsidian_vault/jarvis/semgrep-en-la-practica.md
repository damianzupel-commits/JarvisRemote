---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- herramienta
- sast
- semgrep
title: Semgrep en la Práctica
updated: '2026-07-28T00:00:00.000000+00:00'
---

SAST multi-lenguaje. Ver [[Herramientas SAST y SCA - Resumen]] para dónde encaja frente a las demás herramientas. Su gran ventaja operativa: las reglas se escriben en una sintaxis que se parece al código que buscan, no en un DSL abstracto — bajísima barrera para escribir una regla custom en minutos.

## Uso básico
```bash
# correr rulesets públicos preconfigurados, sin escribir nada propio
semgrep --config auto .
semgrep --config p/security-audit --config p/owasp-top-ten .
semgrep --config p/python --config p/javascript .

# output en JSON para procesar programáticamente (relevante para integrar en Jarvis)
semgrep --config auto --json -o findings.json .
```

## Cómo se escribe una regla propia
Una regla de Semgrep usa "metavariables" (`$X`, `$FUNC`) que actúan como wildcards que además preservan la identidad entre coincidencias del mismo patrón:
```yaml
rules:
  - id: subprocess-shell-true
    languages: [python]
    severity: ERROR
    message: "subprocess con shell=True es vulnerable a command injection si $CMD no es 100% estático"
    patterns:
      - pattern: subprocess.run($CMD, shell=True, ...)
    metadata:
      cwe: "CWE-78"
      owasp: "A03:2021"
```
Esta regla matchea cualquier llamada a `subprocess.run` con `shell=True` sin importar qué más se le pase (el `...` es "cualquier otro argumento"). Ver [[Command Injection]] para el detalle del bug que esta regla busca.

## Cómo leer un finding
Cada finding trae: archivo + línea, el patrón que matcheó, severidad, y (en rulesets buenos) el CWE/OWASP category asociado — eso es lo que permite mapear directo a las notas de esta base (ej. `cwe: CWE-89` → [[SQL Injection]]).

## Falsos positivos comunes (para no generar ruido)
- **Contexto no capturado por el patrón**: una regla que busca `subprocess.run(..., shell=True)` marca también los casos donde el comando SÍ es un string 100% estático sin ninguna variable interpolada — ahí no hay vulnerabilidad real, aunque el patrón coincida. Requiere revisar si el string es dinámico o no.
- **Sanitización ya aplicada pero no reconocida por la regla**: si el proyecto ya escapa/valida el input antes de que llegue al sink, una regla sintáctica simple (sin dataflow) no lo sabe y sigue marcando el sink como vulnerable.
- **Tests y fixtures**: código de test que deliberadamente construye un payload de inyección para probar que la app lo rechaza — Semgrep lo marca igual salvo que el path esté excluido explícitamente (`.semgrepignore`, similar a `.gitignore`).
- **Rulesets genéricos aplicados a un contexto que no corresponde**: una regla pensada para apps web marcando código de un script CLI interno sin superficie de ataque real — la regla no está "mal", pero el riesgo real es distinto.

## Nivel gratuito vs. Pro
La CLI open-source hace matching sintáctico y dataflow *intra*-procedural (dentro de una sola función). El dataflow *inter*-procedural completo (seguir el taint a través de varias funciones/archivos) es una feature de Semgrep Pro/AppSec Platform — para eso, [[CodeQL en la Práctica]] es la alternativa completamente gratuita y open-source con mejor cobertura de flujo de datos real.
