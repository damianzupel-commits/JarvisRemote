---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- python
- javascript
title: Insecure Deserialization
updated: '2026-07-28T00:00:00.000000+00:00'
---

Subtipo de [[OWASP A08 - Fallas de Integridad de Software y Datos]]. Ocurre cuando una app deserializa (reconstruye un objeto/estructura a partir de) datos que vienen de una fuente no confiable, usando un formato cuyo proceso de deserialización puede tener side-effects arbitrarios — en el peor caso, ejecución de código remoto (RCE).

## El caso más peligroso: `pickle` en Python
```python
import pickle

# extremadamente vulnerable: pickle.loads puede instanciar CUALQUIER clase
# y ejecutar su __reduce__/__setstate__, incluyendo llamadas a os.system
data = pickle.loads(request.body)
```
`pickle` no es un formato de datos, es un formato de *serialización de objetos Python arbitrarios*, incluyendo instrucciones de qué clase instanciar y con qué llamar. Un payload de pickle armado a mano puede ejecutar cualquier código Python al deserializarse. **Nunca usar `pickle.loads` sobre datos que no fueron generados por el propio sistema con una clave/firma de confianza.**

## YAML: el mismo problema, menos conocido
```python
import yaml

# vulnerable en versiones viejas de PyYAML, o si se usa yaml.Loader explícito
config = yaml.load(untrusted_yaml, Loader=yaml.Loader)
# YAML permite tags como !!python/object/apply:os.system ["rm -rf /"]

# seguro: SafeLoader (o directamente yaml.safe_load) solo construye tipos básicos
config = yaml.safe_load(untrusted_yaml)
```

## Java (para referencia -- si aparece código legacy o interop)
`ObjectInputStream.readObject()` sobre bytes no confiables es el equivalente Java de `pickle.loads` — mismo problema estructural, ha sido la causa raíz de RCEs históricos de gran impacto en frameworks Java (ej. varias CVEs de Apache Commons Collections encadenadas con deserialización).

## Node.js
`node-serialize` y librerías similares que deserializan funciones (no solo datos) tienen el mismo problema. `JSON.parse` de por sí es seguro en este sentido (solo construye datos, nunca ejecuta código) — el riesgo en JS aparece con librerías de serialización *más* permisivas que JSON, no con JSON mismo.

## Regla general
Si el formato de serialización puede representar "instanciar esta clase" o "llamar a esta función", no es seguro para datos no confiables — usar JSON (o un formato explícitamente de-solo-datos) para cualquier cosa que cruce un límite de confianza, y reservar pickle/YAML-loader-completo/`ObjectInputStream` solo para datos generados y consumidos por el propio sistema.

## Detección
Bandit: `B301`/`B403` (import/uso de pickle), `B506` (`yaml.load` sin `SafeLoader`). Semgrep tiene reglas equivalentes (`p/insecure-deserialization`). Ver [[Bandit en la Práctica]] y [[Semgrep en la Práctica]].
