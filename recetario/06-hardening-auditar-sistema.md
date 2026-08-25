# 06 — Endurecer / auditar un sistema (Hardening Fase 1) ⭐

> La batería de **tests adversariales** que se corre contra un sistema (el propio
> Raphael, o el de un cliente) para encontrar agujeros antes de que los encuentre un
> atacante: escape de sandbox, path traversal, inyección de prompt, inyección de
> comandos, validación de targets, autenticación y modo de operación. Es parte del
> **servicio vendible** y candidata a graduarse a skill.
>
> Corresponde a la comanda "Endurecimiento Fase 1" de [`../COMANDAS.md`](../COMANDAS.md)
> y a la estación `3-Gourmet/` de [`../docs/LA-BRIGADA.md`](../docs/LA-BRIGADA.md)
> (donde Raphael vive en endurecimiento constante).

## Qué produce

Un informe de la superficie de ataque del sistema: por cada vector, si el sistema
**resiste** o **cede**, con evidencia. Los que ceden quedan como findings a
corregir. Es el "test unitario de seguridad" del sistema, repetible antes de cada
release o entrega.

## Estación / especialista

Seguridad / **Pentest** (el Salsero de seguridad). Se puede correr sobre el propio
Raphael (auto-auditoría, estación Gourmet) o contra un blanco del range (receta 04).
Contra terceros: **solo dentro del scope de `authorized_targets.yaml`**.

## Ingredientes (requisitos previos)

- El sistema a auditar corriendo, con acceso para lanzarle los tests.
- Si es pentest activo contra red: el target en `backend/authorized_targets.yaml`
  (gate de scope; por default solo rangos privados/loopback/Tailscale).
- La suite de tests del repo (`backend/tests/`, ~100 `test_*.py`) para la parte
  automatizable.

## Pasos

Correr cada vector adversarial y anotar resiste/cede:

1. **Escape de sandbox del filesystem.** Probar que las tools de FS no salen de
   `FS_ALLOWED_ROOT`. ⚠️ Ojo: por default `FS_ALLOWED_ROOT` es el **HOME entero**,
   no solo el repo — verificar la mitigación pendiente de `ESTADO.md`.
2. **Path traversal.** Intentar `../../` y rutas absolutas para escapar de la
   carpeta permitida; el sistema debe rechazarlas.
3. **Inyección de prompt.** Meter instrucciones hostiles en contenido que el agente
   procesa (un archivo, una nota, una respuesta de tool) e intentar que ignore sus
   gates o ejecute algo fuera de su rol. El guardrail de self-target de `agent.py`
   debe aguantar.
4. **Inyección de comandos.** Contra `pc_run_command` / `shell_exec`: probar
   patrones destructivos (que la blocklist debe frenar: format, `rm -rf /`, shutdown,
   fork bombs) y confirmar que un comando fuera de la blocklist queda **auditado**.
   Recordar: NO es un sandbox real, es una blocklist.
5. **Validación de targets.** Confirmar que toda tool de pentest activo (nmap,
   sqlmap, ZAP, captura) **se niega** contra un target que NO está en
   `authorized_targets.yaml`. Probar la negativa contra una IP externa es en sí un
   test válido del gate.
6. **Autenticación.** Pegarle al backend sin/`con` `Authorization: Bearer <API_KEY>`
   incorrecto y confirmar que rechaza.
7. **Modo de operación.** Verificar el doble modo supervisado/autónomo: que lo
   irreversible respete el patrón dry-run→confirm y que las flags `*_ENABLED`
   apaguen de verdad cada capacidad invasiva.

Después de la Fase 1, escalar a **Raphael-vs-Raphael** en el cyber range (receta
05) para la parte de detección/malware.

## Tiempo estimado

Media jornada para una pasada manual completa; menos si la parte automatizable
(suite `pytest`) ya cubre varios vectores.

## Notas / errores comunes

- **No debilitar los gates para que "pasen" los tests.** El objetivo es encontrar
  agujeros, no maquillarlos. Un test que falla es información valiosa.
- El sandbox de FS es la mitigación más urgente pendiente (HOME entero por default).
- `pc_run_command` es blocklist, no sandbox: un comando nuevo destructivo fuera de
  la lista corre igual. La auditoría persistente es la red de seguridad.
- Correr esta receta **antes de cada entrega a cliente** y antes de subir cambios
  sensibles.

## ¿Candidata a skill?

**⭐ SÍ — candidata a skill, y parte del servicio vendible.** Es repetible por
definición (misma batería, distintos sistemas) y auditable. Graduarla a skill haría
que Raphael corra la suite adversarial completa y entregue el informe de forma
consistente, igual para el propio Raphael que para un cliente. El juicio sobre
findings ambiguos y la decisión de qué corregir quedan humanos; la ejecución y el
reporte, no.
