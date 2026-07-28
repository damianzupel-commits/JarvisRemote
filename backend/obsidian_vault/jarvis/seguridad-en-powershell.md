---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- powershell
- sast
title: Seguridad en PowerShell
updated: '2026-07-28T00:00:00.000000+00:00'
---

PowerShell es uno de los lenguajes que indexa Codebase, y se usa en este mismo proyecto (JarvisRemote corre en Windows). Es un lenguaje con doble naturaleza: shell interactivo y lenguaje de scripting con acceso profundo a .NET, lo que lo vuelve particularmente potente tanto para automatizar como para atacar (es el lenguaje de post-explotación más usado en entornos Windows precisamente por eso).

## Vulnerabilidades más comunes
| Riesgo | Ejemplo del problema | Nota relacionada |
|---|---|---|
| `Invoke-Expression` sobre string con input externo | ejecuta cualquier código PowerShell | [[Command Injection]] |
| `Invoke-Command`/`Start-Process` con string construido dinámicamente | command injection | [[Command Injection]] |
| Credenciales en texto plano en el script | `$password = "..."` hardcodeado | [[Secretos Hardcodeados en Código]] |
| `ConvertTo-SecureString -AsPlainText -Force` sobre secretos hardcodeados | falsa sensación de seguridad — el secreto ya estaba expuesto en texto plano antes de convertirlo | [[Gestión de Secretos]] |
| Descarga y ejecución directa desde internet | `IEX (New-Object Net.WebClient).DownloadString(...)` | ver abajo |
| `-ExecutionPolicy Bypass` normalizado en scripts de deploy | debilita una barrera pensada como defensa en capas | [[Defensa en Profundidad]] |

## El patrón más peligroso: descarga + ejecución en una línea
```powershell
# extremadamente vulnerable: descarga y ejecuta código de una URL sin ninguna
# verificación de integridad -- si el servidor remoto es comprometido o el
# tráfico es interceptado (sin pinning), se ejecuta lo que sea
IEX (New-Object Net.WebClient).DownloadString("https://example.com/install.ps1")

# más seguro: descargar, verificar hash contra un valor conocido, después ejecutar
$script = Invoke-WebRequest -Uri "https://example.com/install.ps1" -UseBasicParsing
$hash = Get-FileHash -InputStream ([IO.MemoryStream]::new($script.Content)) -Algorithm SHA256
if ($hash.Hash -ne $expectedHash) { throw "hash mismatch, aborting" }
Invoke-Expression $script.Content
```
Esto es un caso concreto de [[OWASP A08 - Fallas de Integridad de Software y Datos]] aplicado a scripting: ejecutar código remoto sin verificar su integridad.

## `Invoke-Expression` como el `eval()`/`shell=True` de PowerShell
`Invoke-Expression` (alias `IEX`) parsea y ejecuta cualquier string como código PowerShell — mismo problema estructural que `eval()` en Python o `Invoke-Expression`-equivalentes en otros lenguajes (ver [[Command Injection]]). La gran mayoría de usos de `IEX` sobre datos que no son 100% estáticos y confiables son evitables usando cmdlets nativos o `&` (call operator) con argumentos tipados en vez de un string interpretado.

## Buenas prácticas
- Usar `SecretManagement`/`SecretStore` (módulos oficiales de PowerShell) o un vault externo para credenciales, nunca hardcodear ni siquiera "para un script interno" — ver [[Gestión de Secretos]].
- Firmar scripts (`Set-AuthenticodeSignature`) en entornos donde `AllSigned`/`RemoteSigned` son la política — no rutinizar `-ExecutionPolicy Bypass` como solución a fricción, es una señal de que algo en el flujo de firma está mal configurado.
- `$ErrorActionPreference = "Stop"` + manejo explícito de errores en scripts de automatización, para que un fallo no deje al sistema en un estado intermedio inseguro.
- Preferir cmdlets nativos tipados (`Get-Item`, `Copy-Item`, `Invoke-RestMethod`) sobre construir comandos como strings y ejecutarlos.

## Herramientas
**PSScriptAnalyzer** es el linter/SAST estándar de PowerShell (incluye reglas de seguridad como detección de `Invoke-Expression`, credenciales en texto plano, uso de `ConvertTo-SecureString -AsPlainText`). Semgrep tiene soporte más limitado para PowerShell que para Python/JS — para este lenguaje, PSScriptAnalyzer es la primera línea de defensa, no un genérico multi-lenguaje.
