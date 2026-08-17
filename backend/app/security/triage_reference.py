"""Referencia curada por categoría para el triage de seguridad (Opción C,
2026-08-11) -- diseño acordado con Damian tras el primer resultado real del
triage contra OWASP Benchmark (score 44.0% -> 37.6%, empeoró: el modelo
confundía mitigaciones de una categoría de vulnerabilidad con otra, ej. dar
por resuelto un Trust Boundary Violation con un escape de HTML, que en
realidad mitiga XSS, no CWE-501).

Diferencia clave con `research_topic`/`obsidian_search_notes`: acá NO hay
búsqueda semántica. Cada hallazgo de Semgrep ya trae su `rule_id` exacto, que
mapea determinísticamente a UNA categoría (ver `rule_categories.py`) -- así
que la nota correcta se resuelve por lookup directo (categoría -> note_id
fijo), no por similitud. Las notas siguen viviendo en el vault de Obsidian
como cualquier otra (revisables/editables a mano ahí) -- lo que cambia es
solo el mecanismo de acceso.

Empieza con las 3 categorías que peor salieron en la corrida real
(trustbound, ldapi, pathtraver) -- las demás categorías no tienen nota
curada todavía a propósito (`get_reference_for_category` devuelve `None`
para ellas, y el prompt de triage sigue sin referencia extra, sin cambios de
comportamiento ahí). Agregar una categoría nueva es solo sumarla a
`_CURATED_CONTENT`."""

from __future__ import annotations

from ..obsidian import vault

_NOTE_ID_PREFIX = "jarvis/triage-referencia-"
_CATEGORY_TAG = "triage-referencia"
_CATEGORY_FOLDER = "seguridad-triage"

_CURATED_CONTENT: dict[str, tuple[str, str]] = {
    # categoria -> (titulo, contenido)
    "trustbound": (
        "Trust Boundary Violation (CWE-501): qué mitigación es válida y cuál no",
        """## Qué es el problema real
Trust Boundary Violation (CWE-501) NO es "el dato se muestra mal" ni "el dato rompe una consulta" -- es que un dato que viene de una fuente NO CONFIABLE (un parámetro HTTP, un header, un input de usuario) se guarda en una estructura que el resto del sistema trata como CONFIABLE (típicamente la sesión HTTP, `HttpSession.setAttribute`/`putValue`) sin validarlo antes de cruzar esa frontera. El problema es el CRUCE en sí, no lo que pase con el dato después en otro punto del flujo.

## Mitigaciones que SÍ cuentan para esta categoría
- Validar el valor contra una lista blanca / formato esperado ANTES de guardarlo en la sesión.
- No guardar el dato tal cual en la sesión -- guardar solo un identificador/referencia ya validado, y resolver el valor real desde una fuente confiable.
- Re-validar el valor en cada punto donde se LEE de la sesión, tratándolo como si siguiera siendo no confiable.

## Mitigaciones que NO cuentan para esta categoría (aunque estén presentes en el código)
- **HTML-escaping** (`StringEscapeUtils.escapeHtml`, `encodeForHTML`, etc.) -- mitiga XSS (que el dato se renderice como código en el navegador), NO mitiga que el dato haya cruzado la frontera de confianza sin validar. Son problemas distintos sobre el mismo dato.
- Parametrización SQL / `PreparedStatement` -- mitiga SQL injection, no trust boundary.
- Logging o auditoría del valor -- no es una mitigación, es solo registro.
- Cualquier sanitización pensada para OTRO sink (HTML, SQL, shell) que no sea específicamente "esto ya fue validado antes de guardarse en la sesión".

## Regla práctica
Si ves `session.setAttribute(...)`/`session.putValue(...)` con un valor que viene directo de un parámetro HTTP, y la única "protección" visible es escapado para HTML o similar -- ES una vulnerabilidad real de esta categoría. El escapado para otro sink no absuelve el cruce de frontera sin validar.""",
    ),
    "ldapi": (
        "LDAP Injection (CWE-90): qué mitigación es válida y cuál no",
        """## Qué es el problema real
LDAP Injection (CWE-90) pasa cuando un dato no confiable se concatena directo en un filtro de búsqueda LDAP (ej. `"(uid=" + userInput + ")"`), permitiendo que caracteres especiales de LDAP (`* ( ) \\` y NUL) alteren la lógica del filtro.

## Mitigaciones que SÍ cuentan para esta categoría
- Escapar específicamente los caracteres especiales de LDAP con una función dedicada a esto (un encode real para LDAP, no una función genérica).
- Construir el filtro con una API programática que arme la consulta sin concatenar strings (evita el problema de raíz).

## Mitigaciones que NO cuentan para esta categoría (aunque estén presentes en el código)
- HTML-escaping -- no toca los metacaracteres de LDAP, son alfabetos de escape completamente distintos.
- Escapado/parametrización SQL -- protege un motor de consultas distinto, no protege LDAP.
- Validación genérica de "es alfanumérico" SIN que se haya confirmado explícitamente que excluye los metacaracteres de LDAP.

## Regla práctica
Si el valor llega a un filtro LDAP armado con concatenación de strings y la única sanitización visible es para otro sink (HTML, SQL) o es una validación genérica sin mención explícita de los caracteres de LDAP -- ES una vulnerabilidad real de esta categoría.""",
    ),
    "pathtraver": (
        "Path Traversal (CWE-22): qué mitigación es válida y cuál no",
        """## Qué es el problema real
Path Traversal (CWE-22) pasa cuando un dato no confiable se usa para construir una ruta de archivo, permitiendo que secuencias como `../` (o variantes codificadas) escapen del directorio esperado y accedan a archivos fuera de él.

## Mitigaciones que SÍ cuentan para esta categoría
- Canonicalizar la ruta resuelta (`getCanonicalPath()`/equivalente) y verificar explícitamente que el resultado sigue DENTRO de un directorio base permitido, comparando la ruta resuelta contra ese base -- mismo patrón que ya usa este propio proyecto (`_resolve()`/`FS_ALLOWED_ROOT`) para su propio sandboxing de filesystem.
- Usar una lista blanca de nombres de archivo permitidos en vez de aceptar cualquier path.
- Rechazar el input si contiene `..` o separadores de directorio ANTES de construir la ruta (frágil si es la única medida, pero válido como capa adicional).

## Mitigaciones que NO cuentan para esta categoría (aunque estén presentes en el código)
- HTML-escaping, escapado SQL -- no tienen nada que ver con la resolución de rutas de archivo.
- Verificar que el archivo "existe" -- no impide que la ruta resuelta esté fuera del directorio esperado.
- Chequear la extensión del archivo -- no impide traversal, un atacante puede seguir usando `../../etc/passwd` sin importar qué extensión "espere" el código.

## Regla práctica
Si el valor no confiable llega a un constructor de `File`/`Path` sin canonicalizar-y-verificar contra un directorio base, y la única protección visible es para otro sink -- ES una vulnerabilidad real de esta categoría.""",
    ),
}


def _note_id_for(category: str) -> str:
    return f"{_NOTE_ID_PREFIX}{category}"


def ensure_reference_notes() -> list[str]:
    """Crea (o actualiza, si ya existen) las notas curadas en el vault --
    idempotente, seguro de llamar de nuevo. Devuelve los note_id creados/
    actualizados. Separado de `get_reference_for_category` a propósito: esto
    escribe al vault, lo otro solo lee -- el triage normal nunca debería
    escribir notas como efecto secundario de revisar un hallazgo."""
    note_ids = []
    for category, (title, content) in _CURATED_CONTENT.items():
        note = vault.save_note(
            title=title,
            content=content,
            author="jarvis",
            tags=[_CATEGORY_TAG, category],
            category=_CATEGORY_FOLDER,
            note_id=_note_id_for(category),
        )
        note_ids.append(note.id)
    return note_ids


def get_reference_for_category(category: str | None) -> str | None:
    """Lookup DETERMINÍSTICO (categoría -> note_id fijo), nunca búsqueda
    semántica. Lee el vault en vivo en cada llamada (no cachea en memoria) a
    propósito: si Damian edita la nota curada a mano en Obsidian, el próximo
    triage ya usa la versión editada, sin reiniciar nada. El costo real de
    un `read_note` (I/O a disco) es insignificante comparado con la llamada
    al LLM (~5s) que sigue después.

    Devuelve `None` si la categoría no tiene nota curada todavía (todas
    menos trustbound/ldapi/pathtraver por ahora) o si la nota no existe en
    el vault -- en ambos casos el triage sigue funcionando igual que antes,
    sin la referencia extra."""
    if category is None or category not in _CURATED_CONTENT:
        return None
    try:
        note = vault.read_note(_note_id_for(category))
    except FileNotFoundError:
        return None
    return note.content
