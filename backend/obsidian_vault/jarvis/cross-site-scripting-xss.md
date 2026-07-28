---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- javascript
- typescript
title: Cross-Site Scripting (XSS)
updated: '2026-07-28T00:00:00.000000+00:00'
---

Subtipo de [[OWASP A03 - Injection]]. El sink es el DOM del navegador de otro usuario: input no confiable termina interpretado como HTML/JS y se ejecuta en el contexto de sesión de la víctima (puede robar cookies de sesión, hacer acciones en su nombre, etc.).

## Los tres tipos
- **Reflejado**: el payload viene en la request (típicamente un query param) y se refleja en la respuesta sin sanitizar. Requiere que la víctima haga click en un link armado por el atacante.
- **Almacenado (stored)**: el payload se guarda en la base de datos (ej. un comentario, un nombre de perfil) y se sirve a *todos* los que ven ese contenido — más peligroso porque no depende de que la víctima haga click en nada.
- **DOM-based**: la sanitización server-side puede estar perfecta, pero JS en el cliente mete input no confiable en el DOM vía un sink peligroso (`innerHTML`, `document.write`) sin pasar nunca por el servidor.

## Ejemplo vulnerable → seguro
```javascript
// vulnerable: innerHTML interpreta el string como HTML
element.innerHTML = userComment;

// seguro: textContent no interpreta HTML
element.textContent = userComment;

// si hace falta HTML real (ej. un editor rich-text), sanitizar explícitamente
import DOMPurify from "dompurify";
element.innerHTML = DOMPurify.sanitize(userComment);
```
```jsx
// React escapa por defecto -- esto es seguro:
<div>{userComment}</div>

// vulnerable: dangerouslySetInnerHTML hace explícito el bypass del escape automático
<div dangerouslySetInnerHTML={{ __html: userComment }} />
```
```python
# vulnerable en templates Jinja2/Django si se desactiva el autoescape
{{ user_comment | safe }}   {# Jinja2: 'safe' filter desactiva el escape para ese valor #}
{{ user_comment|safe }}     {# Django: mismo efecto #}

# seguro: dejar el autoescape default (activo) y no marcar como safe contenido de usuario
{{ user_comment }}
```

## Por qué frameworks modernos redujeron mucho el riesgo (pero no lo eliminaron)
React, Vue, Angular y los template engines server-side (Jinja2, Django templates) escapan por defecto. El riesgo real hoy se concentra en los "escape hatches" explícitos: `dangerouslySetInnerHTML`, `v-html`, `{% autoescape off %}`, el filtro `|safe`, o manipulación directa del DOM fuera del framework (`innerHTML` a mano en un `useEffect`).

## Mitigación
Nunca usar el escape hatch con datos de usuario sin sanitizar con una librería dedicada (DOMPurify para HTML rico). Content-Security-Policy como capa adicional (bloquea ejecución de scripts inline aunque algo se cuele) — ver [[Defensa en Profundidad]]. `HttpOnly` en cookies de sesión para que ni siquiera un XSS exitoso pueda leerlas vía `document.cookie`.

## Detección
Semgrep tiene reglas específicas por framework para los escape hatches mencionados arriba (`p/react`, `p/django`, `p/flask`). Ver [[Semgrep en la Práctica]] y [[Seguridad en JavaScript y TypeScript]].
