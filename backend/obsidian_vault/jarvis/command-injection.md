---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- vulnerabilidad
- owasp
- python
- shell
- powershell
title: Command Injection
updated: '2026-07-28T00:00:00.000000+00:00'
---

Subtipo de [[OWASP A03 - Injection]]. El sink es el shell del sistema operativo: input no confiable llega a una función que invoca un intérprete de comandos, y el atacante inyecta comandos adicionales que corren con los permisos del proceso.

## Ejemplo vulnerable → seguro (Python)
```python
import subprocess, os

# vulnerable: shell=True + f-string, el shell interpreta metacaracteres del input
subprocess.run(f"ping -c 1 {host}", shell=True)
# host = "8.8.8.8; rm -rf /" ejecuta el segundo comando también

# vulnerable: os.system tiene el mismo problema, siempre pasa por el shell
os.system(f"convert {filename} output.png")

# seguro: lista de argumentos, sin shell=True -- no hay intérprete que parsee metacaracteres
subprocess.run(["ping", "-c", "1", host], shell=False)
```

## Ejemplo vulnerable → seguro (Node.js)
```javascript
const { exec, execFile } = require("child_process");

// vulnerable: exec pasa el string entero por /bin/sh
exec(`ping -c 1 ${host}`);

// seguro: execFile no invoca un shell, los args van directo al binario
execFile("ping", ["-c", "1", host]);
```

## Ejemplo vulnerable (Shell/Bash) -- ver también [[Seguridad en Shell y Bash]]
```bash
# vulnerable: variable sin comillas y sin validar, se re-interpreta
eval "process_file $1"

# seguro
process_file -- "$1"
```

## Ejemplo vulnerable (PowerShell) -- ver también [[Seguridad en PowerShell]]
```powershell
# vulnerable: Invoke-Expression sobre un string armado con input externo
Invoke-Expression "Get-Item $userPath"

# seguro: cmdlet nativo con el path como parámetro tipado, sin pasar por el parser de expresiones
Get-Item -Path $userPath
```

## Por qué `shell=True` / `exec()` / `Invoke-Expression` son la raíz del problema
Todas estas APIs delegan el parseo del comando a un intérprete de shell, que trata ciertos caracteres (`;`, `|`, `&`, `` ` ``, `$()`, `>`) como control de flujo en vez de datos literales. Las alternativas seguras (`subprocess.run([...], shell=False)`, `execFile`, cmdlets nativos de PowerShell) pasan los argumentos directamente al proceso hijo sin que ningún shell los reinterprete.

## Detección
Bandit: `B602`/`B605` (subprocess con `shell=True`), `B607`/`B609` (paths parciales, wildcard injection). Semgrep tiene reglas equivalentes multi-lenguaje (`p/command-injection`). Ver [[Bandit en la Práctica]] y [[Semgrep en la Práctica]].

## Mitigación
Evitar el shell por completo cuando se pueda (listas de argumentos, APIs nativas). Si es inevitable pasar por un shell, validar el input contra una allowlist estricta de caracteres permitidos antes, nunca intentar "escapar" manualmente los caracteres peligrosos (se olvida alguno, siempre).
