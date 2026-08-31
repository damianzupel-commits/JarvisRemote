# VISIÓN — App de celular de Raphael

> Capturado 2026-08-30 (a pedido de Damian, describiéndolo caminando a casa).
> Es el **norte** de lo que la app móvil debería llegar a ser — NO una spec cerrada.
> Cada punto viene con lectura honesta: qué ya existe, qué falta, y qué lleva gate de seguridad.

## Lo que Damian quiere (sus palabras)

1. Permitir a Raphael usar tools **desde la PC (casa)** que afecten en el **punto físico donde está el celular**.
2. Servir como un **"Dispatch"** (superficie móvil de orquestación/control).
3. Tener la **misma invasividad en el celu** que la que Raphael tiene en la PC.
4. Que **aprenda, guarde notas en Obsidian y discierna** cuándo necesita más conocimiento a mano.
5. Que pueda **automejorarse de manera confiable**.
6. Que haga lo mismo con la **app de celular** (que se automejore).

## Lectura honesta (qué existe, qué falta, qué se gatea)

**1 — Tools remotas que actúan donde está el celu → YA EXISTE, expandible.**
Base: `phone_link.py` (WebSocket), tools de phone (`phone_nmap_scan`, cámara, shell Termux), + **Tailscale** (en armado). El cerebro corre en la PC, el celu ejecuta en su ubicación. Gate: el guardrail de scope (`authorized_targets.yaml`) aplica igual — solo redes propias o autorizadas.

**2 — App como Dispatch → BUILDEABLE.**
Un cliente móvil de control para el backend. La parte "de Claude" (Claude ↔ Raphael) NO existe (son sistemas separados, sin cable directo); un **control móvil de Raphael** sí. Foundation: Tailscale + `/api/chat` + WebSocket.

**3 — Misma invasividad en el celu → BUILDEABLE CON CUIDADO.**
Termux + tools de phone ya dan mucho. "Al máximo de una" es riesgoso: el celu va a todos lados y se conecta a redes ajenas → superficie de ataque mayor que la PC fija. Hacerlo **incremental y con los mismos flags/gates** que la PC, no todo junto.

**4 — Aprender + notas Obsidian + discernir conocimiento → CASI LISTO.**
Ya existe: ingesta de YouTube con **discernimiento de relevancia**, tools de Obsidian, `jarvis_reflect`. Falta: que discierna **proactivamente** cuándo le falta conocimiento y lo busque/ingiera solo. Legítimo y de bajo riesgo.

**5 y 6 — Automejora "confiable" (su código + la app) → LO MÁS DIFÍCIL. ⚠️ GATE OBLIGATORIO.**
Honesto y sin vueltas: **"confiable" y "que se automodifique sola" están en tensión.** Un agente que reescribe su propio código puede romperse solo o **desactivar sus propios frenos**. El módulo `selfrepair` YA existe, pero con **gate de aprobación manual** (`proposal_id` + `confirm`) — a propósito. La versión CONFIABLE **mantiene a Damian en el loop aprobando cada cambio**. NO se puede "soltar" autónomo de forma segura con la tecnología de hoy.
Regla firme: **automejora = propone libre (dry-run), aplica SOLO con confirmación humana. Nunca autónoma total.** (Y la app Android es finicky de buildear → verificación humana sí o sí.)

## Orden sugerido (de cimientos a lo más gateado)

1. **Terminar el acceso remoto** (Tailscale + test) → habilita #1 y #2. ← **PRIMER PLATO, ya en curso.**
2. App como **control móvil** de Raphael (#2).
3. **Aprendizaje proactivo** + notas (#4, casi listo).
4. **Más capacidad de celu**, con gates y por partes (#3).
5. **Automejora, SIEMPRE con gate humano** (#5, #6) — lo último, lo más cuidado.

---

*Nota: esto es la visión-norte. El trabajo real sale de a un plato del riel (`COMANDAS.md`), no todo junto.*
