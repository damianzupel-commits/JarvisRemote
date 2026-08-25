# 📖 El Recetario — Biblioteca de procedimientos repetibles

> Creado: 2026-08-24. Es **documentación operativa**, versionada en el repo. No
> toca código, no commitea, no pushea. Complementa a [`../docs/LA-BRIGADA.md`](../docs/LA-BRIGADA.md)
> (cómo pienso la cocina) y a [`../COMANDAS.md`](../COMANDAS.md) (qué se cocina
> ahora). La Brigada explica *quién* trabaja; el Recetario explica *cómo se hace
> cada plato*.

---

## Qué es el recetario

Un cocinero bueno no improvisa el plato estrella cada noche: sigue una **receta**.
La receta es lo que hace que el plato salga **igual de bueno la vez número 1 y la
número 100**, lo cocine él o lo cocine otro. Sin receta, cada servicio depende de
que ese día te acuerdes de todos los pasos y no te saltees ninguno.

Este recetario es eso, aplicado a Raphael y a mi PC: una **biblioteca de
procedimientos repetibles**. Cada vez que resolví algo que voy a volver a hacer
—blindar una PC, cambiarle el cerebro a Raphael, montar el laboratorio— lo dejo
escrito acá como receta. La lógica es simple:

> **Procedimiento repetible = consistencia = escalabilidad.**
> Una receta bien escrita sale igual siempre. Eso es lo que me deja **vender un
> servicio** (el cliente recibe siempre la misma calidad) y **delegar a la
> brigada** (un agente ejecuta la receta sin que yo esté encima).

Las recetas más maduras —las que ya hago tantas veces que quiero que salgan solas—
**se gradúan a skill**: dejan de ser un papel que leo y pasan a ser una capacidad
que Raphael dispara con un comando. El recetario es la **antesala de los skills**:
primero receta a mano, después, si vale la pena, automatización.

---

## La metáfora

Todo el proyecto se ordena con la cocina (ver [`../docs/LA-BRIGADA.md`](../docs/LA-BRIGADA.md)):

- **El plato** = el resultado que produce la receta (una PC blindada, un modelo
  cambiado, el laboratorio montado).
- **La estación** = dónde se cocina y quién la cocina (Seguridad/Pentest,
  Config/Modelo, Sistema/Red, etc. — los puestos de la brigada).
- **La receta** = el procedimiento paso a paso, versión operativa y concisa. El
  diseño largo y el porqué viven en su doc fuente; la receta linkea a él y da la
  versión "para cocinar".
- **Graduarse a skill** = cuando una receta se hace tan seguido y tan igual que
  conviene que Raphael la ejecute solo.

---

## Estados

| Símbolo | Significado |
|---|---|
| 📝 | **Receta a mano** — procedimiento escrito, lo ejecuta Damian (o un agente guiado) paso a paso. |
| 🤖 | **Ya es skill de Raphael** — automatizada, se dispara con un comando/tool. |
| ⭐ | **Candidata a graduarse a skill** — receta madura y repetible que conviene automatizar pronto. |

---

## Las recetas

| # | Receta | Qué produce (el plato) | Estación / especialista | Estado |
|---|---|---|---|---|
| 01 | [Blindaje de seguridad de una PyME](01-blindaje-seguridad-pyme.md) | Una PC/red de PyME endurecida "kernel-grade" con herramientas gratis — **el servicio que se vende** | Seguridad / Garde-manger (defensor) | ⭐ **LA receta que monetiza** |
| 02 | [Cambiar el cerebro de Raphael](02-cambiar-cerebro-modelo-llm.md) | Raphael corriendo sobre otro modelo LLM (cloud o local) | Config/Modelo (Dueño + Jefe de cocina) | 📝 |
| 03 | [Ingesta de playlist de YouTube al vault](03-ingesta-youtube-vault.md) | Videos de la playlist convertidos en notas del vault | El pase / Bibliotecario (vault) | 🤖 **ya es skill** |
| 04 | [Montar el cyber range](04-montar-cyber-range.md) | Laboratorio aislado `10.13.37.0/24` con blancos para practicar | Seguridad / Pentest | 📝 |
| 05 | [Estrés de detección nocturno (Raphael-vs-Raphael)](05-estres-deteccion-nocturno.md) | Reporte de qué detecta y qué se le escapa al defensor, tras una noche de emulación | Seguridad / Garde-manger | 📝 |
| 06 | [Endurecer/auditar un sistema (Hardening Fase 1)](06-hardening-auditar-sistema.md) | Batería de tests adversariales corrida contra un sistema, con gaps documentados | Seguridad / Pentest | ⭐ **candidata a skill** (parte del servicio vendible) |
| 07 | [Levantar el co-host de stream](07-cohost-stream.md) | MVP del co-host que mira la pantalla y comenta | Código / Co-host (primo separado) | 📝 |
| 08 | [Shell del celular por SSH + Tailscale](08-shell-celular-ssh-tailscale.md) | Terminal de la PC desde el celular, seguro sobre Tailscale | Sistema / Red | 📝 |
| 09 | [Respaldo del proyecto](09-respaldo-proyecto.md) | El repo respaldado local (horario) y en GitHub | Sistema / git (commis) | 📝 |

---

## Candidatas a graduarse a skill

Tres recetas concentran el valor de automatizar:

- **⭐ 01 — Blindaje de seguridad de una PyME.** Es el servicio que se vende. Si se
  gradúa a skill, cada cliente recibe exactamente el mismo endurecimiento, con el
  mismo rigor y el mismo reporte. Escala el negocio de "yo lo hago a mano por
  cliente" a "Raphael lo ejecuta y yo superviso". La más importante del recetario.
- **⭐ 06 — Hardening / auditar un sistema (Fase 1).** La batería de tests
  adversariales (escape de sandbox, path traversal, inyecciones, auth, scope). Es
  repetible por definición y también es parte de lo vendible: correrla como skill
  la vuelve consistente y auditable.
- **🤖 03 — Ingesta de YouTube al vault.** Ya está graduada: existe como módulo
  (`youtube_ingest_playlist`) y como tool del agente. Es el ejemplo de una receta
  que completó el viaje de papel → skill.

El resto (02, 04, 05, 07, 08, 09) son **📝 recetas a mano** por ahora: se hacen lo
suficientemente poco, o dependen de pasos que solo puede hacer un humano (cargar
crédito, instalar con UAC, aprobar reglas), como para no justificar todavía la
automatización completa.
