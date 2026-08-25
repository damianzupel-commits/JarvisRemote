# 05 — Estrés de detección nocturno (Raphael-vs-Raphael)

> Poner a prueba —de forma 100% defensiva y contenida— el módulo de detección de
> Raphael (`backend/app/malware/`), emulando técnicas de adversario dentro del
> range aislado, corriendo desatendido "toda la noche" con un bucle que aprende:
> detona técnica → mira si Raphael la detecta → si no, propone una mejora → repite
> hasta converger. Es Raphael atacando (emulando) para que Raphael defienda mejor.
>
> Basada en `lab/DETECCION-ESTRES-NOCTURNO.md`. **⚠️ Nota:** ese doc fuente está
> hoy en **cuarentena del antimalware** (`backend/data/malware_quarantine/af/…_DETECCION-ESTRES-NOCTURNO.md`)
> — la cuarentena es reversible (mover, no borrar); restaurarlo a `lab/` recupera
> el original. Reusa el range y los snapshots de la receta 04.

## Qué produce

Un reporte de **qué detecta y qué se le escapa** al defensor, tras una noche de
emulación: notas de Obsidian por técnica × pase (versionadas), una nota-índice de
convergencia con la cobertura ATT&CK final, y un set de **reglas YARA nuevas
propuestas** (pendientes de aprobación de Damian) para cerrar los gaps encontrados.

## Estación / especialista

Seguridad / **Garde-manger** (el defensor). El "adversario" es un agente de
emulación dentro del blanco; Raphael es el **defensor** que observa. **Requiere** el
range de la receta 04 montado. Corre desatendido; las decisiones humanas (aprobar
reglas para producción) quedan encoladas para la mañana.

## Ingredientes (requisitos previos)

- **Range montado** (receta 04): `10.13.37.0/24` aislado, VM blanco Windows con
  `-BASE-limpio`, colector Caldera en `10.13.37.10`, range en `authorized_targets.yaml`.
- **Atomic Red Team** (`Invoke-AtomicRedTeam`) instalado **dentro de la VM blanco**
  (no en el host). **Hoy NO instalado.**
- **MITRE Caldera v5** (servidor + agente Sandcat) para las cadenas multi-paso.
  **Hoy NO instalado.**
- Detección de Raphael operativa: backend arriba, ClamAV (clamd) corriendo,
  `starter.yar` cargado, **EICAR detecta** (sub-test de sanidad) antes de arrancar.
- *(Opcional pero recomendado)* Sysmon + `SYSMON_ENABLED=true` para T1055/T1003; si
  no, esos quedan como **gap esperado**, no como fallo.
- Carpeta `app/malware/rules/generadas/` creada para las reglas propuestas.

## Pasos

1. **Verificación previa (dry-run corto, NO toda la noche).** Correr **1 técnica
   fácil** de punta a punta: `Invoke-AtomicTest T1059.001` → Raphael detecta
   (`malware_scan_path`) → journaliza a Obsidian → revert de snapshot. Confirmar que
   la nota sale bien formada y que una técnica **no** detectada genera un **gap** +
   una **mejora propuesta**.

2. **Configurar los topes del orquestador nocturno:** `MAX_HORAS_NOCHE` (ej. 8h),
   `MAX_PASES` (ej. 5), `MAX_MIN_TECNICA` (20 min), `MAX_INTENTOS_TECNICA` (6),
   `N_ESTABLE` (3), y la ventana de detección `T_det`.

3. **Elegir el modo de reglas:**
   - **Asistido (default):** las reglas YARA nuevas quedan como propuesta pendiente
     de Damian; el bucle usa una copia de trabajo dentro del range para medir si la
     mejora cierra el gap, sin tocar producción.
   - **Autónomo-en-range:** solo dentro del range, recompila YARA con las reglas
     nuevas (`compile_rules(force=True)`) para medir convergencia real. Nunca
     escribe fuera del range.

4. **Lanzar la corrida.** El **bucle interno** (por técnica): revert a PRE →
   detonar variante (limpia / ofuscada / base64 / hidden / vector alt) → detectar →
   puntuar → journalizar → repetir o avanzar. Se agota una técnica por: detección
   estable (3 seguidas), variantes agotadas, techo de intentos (6) o de tiempo (20
   min). El **bucle externo** (por pases): recorre todo el arsenal, mira los gaps,
   **propone al menos una mejora**, y corre otro pase. **Converge** cuando un pase
   da cero gaps nuevos o llega a plateau (dos pases con la misma cantidad de gaps).

5. **A la mañana: revisar y aprobar.** Leer la nota-índice de convergencia, revisar
   las reglas YARA generadas en `app/malware/rules/generadas/*.propuesta`, y aprobar
   a mano las que valen para producción (gate dry-run→confirm; los umbrales
   conductuales **siempre** son propuesta, nunca auto-aplicados a producción).

## Tiempo estimado

La corrida: hasta `MAX_HORAS_NOCHE` (ej. 8h) desatendida. La preparación (instalar
Atomic + Caldera, verificación dry-run): varias horas de setup, una vez.

## Notas / errores comunes

- **No genera ni despliega malware real.** Solo emula *técnicas* (Atomic/Caldera),
  EICAR (inofensivo, estándar de la industria) y reglas YARA propias. Todo con
  cleanup + revert de snapshot.
- **Anti-ciclo-inútil:** entre pase y pase **debe** aplicarse o proponerse al menos
  una mejora; correr el mismo pase sin cambios encontraría siempre los mismos gaps.
  Si no hay mejora posible, el bucle para y reporta.
- **Gaps honestos esperados** (no son fallos): T1055 Process Injection y C2 sobre
  HTTPS 443 no se ven sin Sysmon/correlación de kernel — coincide con los límites
  documentados en `behavioral_watcher.py` / `process_monitor.py`.
- **Higiene de snapshots:** BASE sagrado; borrar PRE/POST ya journalizados; los
  blancos Windows inflan snapshots rápido.
- Si **EICAR no detecta**, es un gap **crítico de infraestructura** (el motor está
  roto), no de cobertura — arreglar antes de seguir.

## ¿Candidata a skill?

**📝 receta a mano** por ahora — depende de que el range, Atomic y Caldera estén
montados (aún no lo están). El **orquestador nocturno** que describe el diseño es,
de hecho, la forma automatizada de esta receta; cuando exista como código, esta
receta pasaría a 🤖. El gate de aprobación de reglas para producción queda humano.
