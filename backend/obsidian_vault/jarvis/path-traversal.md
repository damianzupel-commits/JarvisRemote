---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- python
title: Path Traversal
updated: '2026-07-28T00:00:00.000000+00:00'
---

También llamado directory traversal. Variante de [[OWASP A03 - Injection]] con sink = filesystem: input del usuario se usa para construir una ruta de archivo, y el atacante inyecta secuencias `../` (o equivalentes) para salir del directorio esperado y leer/escribir archivos arbitrarios del sistema.

## Ejemplo vulnerable → seguro (Python)
```python
import os

# vulnerable: filename viene directo del usuario, sin validar
@app.get("/download")
def download(filename: str):
    path = os.path.join("/var/app/uploads", filename)
    return send_file(path)
    # filename = "../../../../etc/passwd" escapa del directorio uploads

# seguro: resolver la ruta absoluta y verificar que quede DENTRO del directorio base
from pathlib import Path

def download(filename: str):
    base = Path("/var/app/uploads").resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(400, "ruta inválida")
    return send_file(target)
```
`os.path.join("/var/app/uploads", "../../etc/passwd")` **no** lanza error — simplemente construye la ruta que resulta, incluyendo la salida del directorio. La validación tiene que pasar por resolver la ruta final y compararla contra el directorio base, no por revisar el string de entrada en busca de `..` (hay formas de codificar lo mismo: URL-encoding `%2e%2e%2f`, encoding doble, backslashes en Windows, symlinks).

## Variantes menos obvias
- **Zip Slip**: al descomprimir un `.zip`/`.tar` subido por el usuario, las entradas del archivo pueden tener nombres con `../` que escriben fuera del directorio de extracción esperado — mismo bug, sink distinto (extracción de archivo en vez de lectura).
- **Null byte injection** (legacy, en runtimes viejos): `archivo.txt%00.jpg` truncaba la validación de extensión en algunos lenguajes con bindings a C — mayormente mitigado en runtimes modernos pero vale conocerlo si aparece código muy viejo.

## Detección
Bandit no tiene una regla dedicada fuerte para esto (es más un problema de lógica que de sintaxis simple); Semgrep sí tiene reglas que buscan `os.path.join`/`open()` con input de request sin pasar por una función de resolución+validación antes. CodeQL, con su análisis de flujo de datos, es la herramienta más efectiva acá porque puede rastrear el input desde el request handler hasta la llamada a `open()`. Ver [[Semgrep en la Práctica]] y [[CodeQL en la Práctica]].

## Mitigación
Resolver la ruta absoluta final y verificar que esté dentro del directorio base permitido (`Path.resolve()` + `is_relative_to()` en Python 3.9+, o equivalente). Cuando sea posible, no usar el input del usuario como parte de una ruta de archivo en absoluto — usar un identificador opaco (UUID) que mapea a la ruta real en una tabla, sin relación directa con el filesystem.
