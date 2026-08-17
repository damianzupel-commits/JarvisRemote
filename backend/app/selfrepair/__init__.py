"""Opción C del diseño de auto-reparación de Jarvis (decidido 2026-08-10/11,
ver la sesión de esa fecha): Jarvis puede PROPONER un fix a su propio código
(`backend/`) en modo dry-run -- sin gate, porque no escribe nada -- pero
aplicarlo de verdad requiere un `proposal_id` concreto que Damian confirme a
mano en el chat. El gate vive en `app/agent.py` (mismo lugar que el resto de
los guardrails duros del loop de tool calls); este paquete tiene la lógica
que ese gate reusa (`gate.py`) y el flujo de generar una propuesta
(`propose.py`), conectado a las notas de diagnóstico de `app/introspection/`
(Opción B).

Deliberadamente NO incluye ningún mecanismo de reinicio/watchdog -- eso es
prerrequisito de la Opción A, todavía no construida. Después de aplicar un
fix acá, el backend sigue corriendo con el código VIEJO hasta que alguien lo
reinicia a mano; ese corte es a propósito."""
