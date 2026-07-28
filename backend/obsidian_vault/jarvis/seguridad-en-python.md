---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- python
- sast
title: Seguridad en Python
updated: '2026-07-28T00:00:00.000000+00:00'
---

Python es uno de los lenguajes que indexa Codebase, y el lenguaje del propio backend de Jarvis — relevante tanto para auditar proyectos de terceros como el propio repo. Herramienta de referencia: [[Bandit en la Práctica]] (SAST específico de Python), más [[Semgrep en la Práctica]] para reglas cross-lenguaje.

## Vulnerabilidades más comunes en Python (mapeadas a Bandit/CWE)
| Riesgo | Ejemplo del problema | Nota relacionada |
|---|---|---|
| `eval()`/`exec()` sobre input externo | ejecuta código Python arbitrario | [[Command Injection]] |
| `subprocess` con `shell=True` | inyección de comandos de shell | [[Command Injection]] |
| `pickle.loads()` sobre datos no confiables | RCE vía deserialización | [[Insecure Deserialization]] |
| `yaml.load()` sin `SafeLoader` | mismo problema que pickle | [[Insecure Deserialization]] |
| SQL armado con f-string/`.format()` | SQL injection | [[SQL Injection]] |
| `os.path.join` con input sin validar | path traversal | [[Path Traversal]] |
| `hashlib.md5`/`sha1` para passwords | hash débil | [[OWASP A02 - Fallas Criptográficas]] |
| `requests.get(..., verify=False)` | TLS sin verificar | [[OWASP A02 - Fallas Criptográficas]] |
| `random` (no `secrets`) para tokens | PRNG no criptográfico | [[Criptografía Aplicada: Qué NO Hacer]] |
| `assert` para validación de seguridad | se elimina con `python -O` | ver abajo |

## Gotcha específico de Python: `assert` no es validación
```python
# vulnerable: con optimizaciones (-O) los asserts se eliminan del bytecode
def transfer(user, amount):
    assert user.is_authorized, "no autorizado"
    do_transfer(amount)

# seguro: raise explícito, no depende de flags de ejecución
def transfer(user, amount):
    if not user.is_authorized:
        raise PermissionError("no autorizado")
    do_transfer(amount)
```

## Buenas prácticas de secure coding específicas de Python
- Usar `secrets` (no `random`) para tokens, claves de sesión, y cualquier cosa criptográficamente sensible.
- `pathlib.Path.resolve()` + `is_relative_to()` para validar rutas de archivo con input externo.
- Type hints + validación real de entrada (Pydantic en APIs) en el borde del sistema — los type hints de Python no se verifican en runtime por sí solos, son solo documentación/lint estático salvo que algo como Pydantic los haga cumplir.
- `subprocess.run([...], shell=False)` como default; justificar explícitamente cualquier `shell=True`.
- Entornos virtuales + `requirements.txt`/`poetry.lock` siempre commiteados, para builds reproducibles y auditables por SCA — ver [[OWASP A06 - Componentes Vulnerables y Desactualizados]].
- `python -m pip install --require-hashes` en pipelines de CI para verificar integridad de paquetes descargados.

## Herramienta principal: Bandit
Bandit es el SAST de facto para Python, corre rápido y sin configuración inicial (`bandit -r .`). Ver [[Bandit en la Práctica]] para reglas específicas, cómo leer el output, y falsos positivos comunes (uso legítimo de `subprocess` con `shell=True` en scripts internos de infra, por ejemplo).
