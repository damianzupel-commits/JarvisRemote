# 09 — Respaldo del proyecto

> La rutina que hace que nunca se pierda trabajo: un **respaldo horario** que
> auto-commitea local, y el **push a GitHub** que sube todo lo pendiente al remoto.
> El respaldo local corre solo; el push necesita credenciales y hoy queda pendiente
> a mano.
>
> Estado real del respaldo en [`../_backups/ULTIMO-RESPALDO.md`](../_backups/ULTIMO-RESPALDO.md).
> Corresponde a la comanda "Push del repo a GitHub" de [`../COMANDAS.md`](../COMANDAS.md).

## Qué produce

El repo respaldado en **dos niveles**: (1) commits locales automáticos cada hora
(nunca se pierde más de una hora de trabajo), y (2) esos commits subidos a GitHub
(`origin/master`), fuera de la PC.

## Estación / especialista

Sistema / **git** — tarea de **commis** (prep rutinaria). El respaldo local es
automático; el push lo dispara Damian (necesita credenciales de GitHub). **Requiere
PC** para el push.

## Ingredientes (requisitos previos)

- El respaldo horario ya configurado (corre y encadena commits automáticamente).
- Credenciales de GitHub disponibles en el entorno para poder pushear.
- `master` **sin locks obsoletos** (ver Notas — hoy hay `.lock` que bloquean).

## Pasos

1. **El respaldo local ya corre solo.** Cada hora auto-commitea los cambios. Cuando
   no puede tocar `master` (locks o sin credenciales), encadena el commit en una
   rama `respaldo-auto-<fecha>` que desciende linealmente de `master` — **no se
   pierde nada**, queda pendiente de integrar.

2. **Destrabar `master` si hay locks** (PowerShell, con el backend y los editores
   **cerrados**):

   ```powershell
   cd C:\Users\dam\Documents\JarvisRemote
   del .git\index.lock, .git\HEAD.lock, .git\refs\heads\master.lock, .git\refs\heads\master.lock.stale.13985
   git status
   ```

3. **Integrar la rama de respaldo más reciente a `master`** (fast-forward, la cadena
   es lineal):

   ```powershell
   git merge --ff-only respaldo-auto-<fecha-mas-reciente>
   ```

4. **Subir a GitHub:**

   ```powershell
   git push origin master
   ```

5. **Limpiar las ramas de respaldo ya integradas:**

   ```powershell
   git branch -d respaldo-auto-<fecha1> respaldo-auto-<fecha2> ...
   ```

## Tiempo estimado

El respaldo local: cero (automático). El destrabe + push manual: 5–10 minutos cuando
se acumularon ramas.

## Notas / errores comunes

- **⚠️ El remoto es PÚBLICO** (`github.com/damianzupel-commits/JarvisRemote`) — ver
  [`../CLAUDE.md`](../CLAUDE.md). Todo lo que se pushea queda visible para cualquiera.
  **Nunca** commitear secretos, `.env`, `authorized_targets.yaml`, credenciales ni
  targets de pentesting. El respaldo escanea por secretos (patrones `sk-`, `AIza`,
  `ghp_`, claves PEM) antes de commitear, pero revisá igual antes de pushear.
  *(Si la intención es que el repo sea privado, cambiá su visibilidad en GitHub —
  hoy figura como público.)*
- **Locks obsoletos de git** (`index.lock`, `HEAD.lock`, `master.lock*`) bloquean
  `master` y son la causa de que los respaldos se acumulen en ramas. El entorno del
  respaldo no puede borrarlos; hay que hacerlo a mano (paso 2) con todo cerrado.
- **Exclusiones:** `_backups/` está gitignoreado. No se commitea nada >25 MB (venvs,
  binarios, `.onnx`, `.dll`). `cerebro-fenix/_Jarvis-Local/` se omite a propósito.
- El respaldo también zipea el `Vault-Fenix` (no es repo git) reteniendo hasta 24
  zips con rotación.

## ¿Candidata a skill?

**📝 receta a mano** en la parte del push (necesita credenciales + destrabe manual
de locks + revisión de secretos antes de exponer al remoto público). El **commit
horario ya está automatizado**; lo que falta cerrar es el push desatendido, que
depende de resolver credenciales y los locks. Cuando eso se resuelva, el push pasa a
🤖 junto con el commit.
