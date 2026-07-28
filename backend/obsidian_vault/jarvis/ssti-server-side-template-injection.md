---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- python
title: SSTI - Server-Side Template Injection
updated: '2026-07-28T00:00:00.000000+00:00'
---

Subtipo de [[OWASP A03 - Injection]]. El sink es el motor de templates (Jinja2, Django templates, Freemarker, Twig, Handlebars...). Ocurre cuando input del usuario se inserta en el **template mismo** (no en una variable pasada al template), y el motor lo interpreta como sintaxis de template en vez de como texto plano.

## La distinción clave: dato en el template vs. dato como template
```python
from jinja2 import Template

# seguro: el input es una VARIABLE, el template en sí es estático y confiable
Template("Hola {{ name }}").render(name=user_input)
# user_input="{{7*7}}" se muestra literal como texto "{{7*7}}", no se evalúa

# vulnerable: el input se concatena para CONSTRUIR el string del template
Template("Hola " + user_input).render()
# user_input="{{7*7}}" el motor SÍ lo interpreta y renderiza "49"
# user_input="{{ self.__init__.__globals__.__builtins__.__import__('os').popen('id').read() }}"
#   en Jinja2 sin sandboxing esto puede llegar a ejecución de comandos del sistema
```
La confusión típica que introduce el bug: alguien arma el string del template dinámicamente (para "personalizar" un email, un reporte, una notificación) y por error concatena el input del usuario ahí, en vez de pasarlo como variable al `render()`.

## Por qué es más grave que XSS
Un XSS exitoso corre en el navegador de la víctima. Un SSTI exitoso corre **en el servidor**, con los permisos del proceso de la aplicación — en template engines potentes como Jinja2 (que expone el árbol de objetos completo de Python vía introspección), SSTI suele escalar directo a RCE.

## Dónde aparece en la práctica
Generadores de reportes/PDFs personalizables por el usuario, sistemas de plantillas de email editables desde un panel de admin, cualquier feature de "template custom" expuesta a usuarios no totalmente confiables, y código que arma un template a partir de un string de config leído de base de datos sin distinguir claramente "esto es confiable" de "esto no".

## Mitigación
Nunca construir el string del template con datos de usuario — el input del usuario siempre debe pasar como variable de contexto (`render(var=user_input)`), nunca como parte del template en sí. Si el producto necesita que usuarios editen templates reales (no solo variables), usar un entorno sandboxed del motor (`jinja2.sandbox.SandboxedEnvironment`, con las limitaciones que igual tiene ese sandbox — hay bypasses conocidos históricamente, no es una garantía absoluta) y tratarlo como superficie de ataque de alto riesgo.

## Detección
Semgrep tiene reglas para detectar concatenación de input en la construcción de un objeto `Template`/`render_template_string` (Flask). Buscar específicamente `render_template_string(f"...")` o equivalentes es una señal casi inequívoca de SSTI potencial. Ver [[Semgrep en la Práctica]] y [[Seguridad en Python]].
