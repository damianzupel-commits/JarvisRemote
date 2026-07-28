---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- javascript
- typescript
- sast
title: Seguridad en JavaScript y TypeScript
updated: '2026-07-28T00:00:00.000000+00:00'
---

JS/TS es uno de los lenguajes que indexa Codebase. Ecosistema con superficie doble: código que corre en el navegador (riesgo típico: XSS, exposición de datos en el cliente) y código que corre en Node.js server-side (riesgo típico: inyección clásica, SSRF, prototype pollution). TypeScript reduce bugs de tipo pero **no** es una capa de seguridad — `any`, `as`, y `!` (non-null assertion) apagan el chequeo justo donde más importaría, y el output sigue siendo JS ejecutado sin ninguna garantía en runtime.

## Vulnerabilidades más comunes
| Riesgo | Ejemplo del problema | Nota relacionada |
|---|---|---|
| `innerHTML`/`dangerouslySetInnerHTML` con input de usuario | XSS | [[Cross-Site Scripting (XSS)]] |
| `eval()`, `new Function()`, `setTimeout(string)` | ejecución de código arbitrario | [[Command Injection]] |
| `exec()` de `child_process` con string | command injection | [[Command Injection]] |
| Prototype pollution | ver abajo | — |
| Dependencias de npm sin lockfile/auditar | [[OWASP A06 - Componentes Vulnerables y Desactualizados]] | [[Snyk en la Práctica]] |
| Secretos en `.env` commiteado o en el bundle del cliente | [[Secretos Hardcodeados en Código]] | — |
| CORS `*` en Express/APIs | [[OWASP A05 - Configuración de Seguridad Incorrecta]] | — |

## Prototype pollution (específico del lenguaje)
```javascript
// vulnerable: un merge/asignación recursiva sin filtrar __proto__/constructor
function merge(target, source) {
  for (const key in source) {
    target[key] = source[key];
  }
}
merge({}, JSON.parse(untrustedInput));
// untrustedInput = '{"__proto__": {"isAdmin": true}}'
// contamina Object.prototype -- TODO objeto en el proceso hereda isAdmin=true

// seguro: bloquear claves peligrosas explícitamente, o usar Object.create(null)
// como base, o una librería de merge que ya mitiga esto (ej. lodash reciente)
const DANGEROUS_KEYS = new Set(["__proto__", "constructor", "prototype"]);
function safeMerge(target, source) {
  for (const key in source) {
    if (DANGEROUS_KEYS.has(key)) continue;
    target[key] = source[key];
  }
}
```
Es un bug casi exclusivo de JS por cómo funciona la cadena de prototipos; no tiene equivalente directo en Python/Kotlin.

## Cliente vs. servidor: qué NO poner en código de frontend
Todo lo que termina en el bundle de JS que se sirve al navegador es público, sin excepción — incluidas API keys "solo de lectura", lógica de negocio que valida permisos, y comentarios. La validación de seguridad real siempre tiene que estar server-side; validación en el cliente es solo UX, nunca control de acceso.

## Buenas prácticas
- `Content-Security-Policy` estricta (sin `unsafe-inline`/`unsafe-eval`) como mitigación en capas contra XSS.
- `npm audit` / [[Snyk en la Práctica]] en CI, `package-lock.json` siempre commiteado.
- Node: usar `execFile`/`spawn` con array de args en vez de `exec` con string — ver [[Command Injection]].
- Validar y tipar el *borde* del sistema (body de requests) con algo como Zod, no confiar en los tipos de TypeScript para eso (se borran en compile-time).

## Herramientas
ESLint con plugins de seguridad (`eslint-plugin-security`, `eslint-plugin-no-unsanitized`) para SAST liviano en cada save; [[Semgrep en la Práctica]] tiene rulesets específicos para React/Express/Node; [[Snyk en la Práctica]] es fuerte específicamente en el ecosistema npm.
