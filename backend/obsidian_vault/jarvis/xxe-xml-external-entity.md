---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- python
title: XXE - XML External Entity
updated: '2026-07-28T00:00:00.000000+00:00'
---

Subtipo de [[OWASP A03 - Injection]]. El sink es un parser XML mal configurado que resuelve entidades externas (`<!ENTITY>`) definidas dentro del propio documento XML — el atacante define una entidad que apunta a un archivo local o a una URL, y el parser la resuelve como parte del documento.

## Ejemplo vulnerable
```xml
<?xml version="1.0"?>
<!DOCTYPE data [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<data>&xxe;</data>
```
Si el parser resuelve `&xxe;`, el contenido de `/etc/passwd` termina insertado en el XML parseado y disponible para la app (y a veces reflejado de vuelta en la respuesta).

## Impactos posibles
- **Lectura de archivos locales** del servidor (como en el ejemplo de arriba).
- **SSRF**: la entidad externa apunta a una URL interna en vez de a un archivo — ver [[OWASP A10 - Server-Side Request Forgery (SSRF)]], el parser XML actúa como el cliente HTTP que hace la request.
- **Billion Laughs / entity expansion DoS**: entidades anidadas que se expanden exponencialmente, agotando memoria.

## Ejemplo vulnerable → seguro (Python)
```python
from lxml import etree

# vulnerable: resolve_entities habilitado (default histórico en algunas configuraciones)
parser = etree.XMLParser(resolve_entities=True)
tree = etree.parse(untrusted_xml, parser)

# seguro: deshabilitar entidades externas y DTD explícitamente
parser = etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False)
tree = etree.parse(untrusted_xml, parser)
```
La librería estándar `xml.etree.ElementTree` de Python es, desde hace varias versiones, más segura por defecto contra esto que `lxml` (que requiere configuración explícita) — pero conviene no asumir y siempre verificar la configuración del parser específico que usa el proyecto, incluyendo parsers de SOAP/RSS/SVG que internamente procesan XML sin que sea obvio a primera vista.

## Dónde aparece sin que sea obvio
Cualquier formato basado en XML: SOAP, RSS/Atom feeds, SVG (subida de imágenes SVG procesadas server-side), DOCX/XLSX (son ZIPs con XML adentro), configuración de algunos frameworks. Un endpoint de "subí tu avatar en SVG" puede ser un vector de XXE tan válido como un endpoint de API XML explícito.

## Mitigación
Deshabilitar resolución de entidades externas y de DTDs a nivel de configuración del parser, siempre, salvo necesidad explícita y justificada. Cuando sea posible, preferir JSON sobre XML para APIs nuevas (elimina la clase de bug por completo).

## Detección
Semgrep tiene reglas específicas por librería de parsing XML (`p/xxe`, reglas para `lxml`, `xml.sax`, parsers Java). Ver [[Semgrep en la Práctica]].
