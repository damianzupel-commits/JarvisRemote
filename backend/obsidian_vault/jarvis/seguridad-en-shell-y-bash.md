---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- shell
- sast
title: Seguridad en Shell y Bash
updated: '2026-07-28T00:00:00.000000+00:00'
---

Shell/Bash es uno de los lenguajes que indexa Codebase — omnipresente en scripts de build, deploy y CI/CD, donde suele recibir menos escrutinio de seguridad que el código de aplicación aunque a menudo corre con más privilegios (root en contenedores de build, credenciales de deploy en el entorno).

## Vulnerabilidades más comunes
| Riesgo | Ejemplo del problema | Nota relacionada |
|---|---|---|
| Variables sin comillas | word splitting + expansión de glob inesperada | ver abajo |
| `eval` sobre input externo | ejecuta cualquier comando | [[Command Injection]] |
| Command injection vía interpolación en subcomandos | `` `cmd $var` ``/`$(cmd $var)` con `$var` no confiable | [[Command Injection]] |
| Secretos en variables de entorno logueadas o en `set -x` | quedan en logs de CI | [[Secretos Hardcodeados en Código]] |
| `curl \| bash` sin verificar integridad | ejecución de script remoto no verificado | [[OWASP A08 - Fallas de Integridad de Software y Datos]] |
| Uso de `/tmp` sin nombre único/permisos correctos | race condition (TOCTOU) o symlink attack | ver abajo |

## El error #1: variables sin comillas
```bash
# vulnerable: sin comillas, bash hace word splitting y expansión de glob sobre $file
rm $file
# file="-rf ~" -- con espacios o con inicio de flag, cambia el comando ejecutado por completo
# file="* -rf" en un directorio con archivos glob-eables, expande a algo no intencionado

# seguro: comillas dobles previenen word splitting y expansión de glob
rm -- "$file"
```
`--` antes del argumento evita además que un `$file` que empiece con `-` sea interpretado como flag. Esta es la clase de bug más frecuente en shell scripting, y la más fácil de introducir sin darse cuenta.

## Command injection clásico
```bash
# vulnerable
user_input="$1"
eval "process $user_input"
# user_input="; rm -rf ~" ejecuta el comando adicional

# vulnerable de forma menos obvia: interpolación dentro de un subcomando
result=$(grep "$pattern" file.txt)
# si $pattern viene de afuera y contiene backticks o $(), bash lo puede re-evaluar
# dependiendo de cómo se construya el comando completo alrededor

# seguro: pasar como argumento posicional, nunca interpolar en el string del comando
process -- "$user_input"
```

## `curl | bash`: instalar software sin verificar integridad
```bash
# vulnerable: si el servidor es comprometido o hay un MITM sin pinning, se
# ejecuta lo que sea, con los permisos de quien corre el script
curl -fsSL https://example.com/install.sh | bash

# más seguro: descargar, verificar checksum contra un valor publicado por un
# canal separado y confiable, después ejecutar
curl -fsSL https://example.com/install.sh -o install.sh
echo "expectedsha256  install.sh" | sha256sum -c -
bash install.sh
```

## `/tmp` inseguro (TOCTOU / symlink attacks)
```bash
# vulnerable: nombre predecible en directorio compartido -- otro proceso puede
# crear un symlink en esa ruta antes de que este script escriba ahí
echo "$data" > /tmp/myapp_output

# seguro: archivo temporal único, generado atómicamente
tmpfile=$(mktemp) || exit 1
echo "$data" > "$tmpfile"
```

## Buenas prácticas
- `set -euo pipefail` al principio de scripts no interactivos: falla rápido en vez de continuar con errores silenciosos (`-e` sale en el primer error, `-u` trata variables no definidas como error, `-o pipefail` propaga errores dentro de un pipe).
- Comillas dobles alrededor de toda expansión de variable (`"$var"`, `"${arr[@]}"`) salvo que se necesite explícitamente word splitting/globbing.
- `mktemp` para archivos/directorios temporales, nunca nombres fijos en `/tmp`.
- Evitar `eval` casi por completo; si es indispensable, validar el input contra una allowlist muy estricta antes.

## Herramientas
**ShellCheck** es el linter/SAST de facto para shell scripts — detecta la gran mayoría de los patrones de arriba (variables sin comillas, `eval` peligroso, quoting incorrecto) con altísima precisión y casi sin falsos positivos, es la primera herramienta a correr sobre cualquier `.sh`. Semgrep tiene soporte más limitado para Bash que para lenguajes de aplicación; ShellCheck sigue siendo la referencia principal para este lenguaje.
