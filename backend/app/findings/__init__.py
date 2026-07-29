"""Modelo de hallazgo compartido entre `app/security/` (vulnerabilidades) y
`app/quality/` (bugs generales) -- mismo esquema (archivo, línea, severidad,
regla, mensaje) para que el LLM no tenga que aprender dos formatos distintos
según qué analizador encontró el problema. Ver `models.py`, `binaries.py`
(helpers de proceso reusados por los wrappers de ambos) y `runner_util.py`
(orquestación común de "correr N herramientas, degradar con gracia si falta
alguna")."""
