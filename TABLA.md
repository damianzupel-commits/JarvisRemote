# 🔪 La Tabla — ideas crudas

> Acá cae toda idea recién pensada, sin procesar. No se cocina desde acá: se captura para que no se pierda. Cuando una idea se decide cocinar, pasa al riel (`COMANDAS.md`).

---

## El Restaurante Virtual (tablero visual en vivo)
**Anotado: 2026-08-24**

Una herramienta visual donde Damian ve su "restaurante" funcionando en tiempo real: los agentes/cocineros moviéndose entre estaciones, las comandas viajando por el pase, el runner llevando el plato, cómo se comunican entre sí (hub-and-spoke + pizarra). Un "kitchen sim" atado a la actividad REAL de los agentes de Raphael.

- **Qué es:** dashboard de observabilidad renderizado como una cocina visual (agentes = sprites en estaciones, comandas = tickets que fluyen, estados en vivo). Se alimenta del stream de eventos del backend FastAPI (WebSocket).
- **Por qué es un plato de postre, no de entrada:** requiere que la cocina de agentes exista primero (el sous-chef, los jefes de partida y el router son Fase 1, sin construir). Hoy visualizaría una cocina vacía.
- **Valor extra:** cuando Raphael sea real, este visual en vivo es una **carta de presentación para vender** — mostrarle a un cliente una cocina de IA de seguridad funcionando impresiona.
- **Depende de:** orquestación construida (Fase 1) + un canal de eventos en tiempo real.

**Flujo visual completo que Damian quiere ver (spec):**
1. La **comanda entera** que entró (la orden completa).
2. Cómo el **sous-chef la dividió** en sub-tareas (árbol de descomposición).
3. A qué **estación/agente** fue cada pedazo (el ruteo).
4. El **estado de cada parte, en vivo**:
   - 🔥 cocinándose (agente trabajando)
   - ✅ parte lista (el agente terminó su pedazo)
   - 👍 aprobada (pasó su gate de confirmación)
5. El **emplatado**: cómo las partes se juntan en el plato final.
6. **Servido**: sale al pase / se entrega.

En resumen: un tablero tipo árbol/kanban por comanda, mostrando descomposición + estado por agente + estados de aprobación (gates), todo actualizándose en tiempo real.

**Dónde vive (metáfora: cámaras de seguridad de la cocina):**
- **Las cámaras** = el backend FastAPI de Raphael emite un stream de eventos en vivo (WebSocket/SSE): qué agente cocina qué, estados, aprobaciones.
- **El monitor** = una página web (dashboard) servida por el mismo backend, como una superficie más (junto a tray-app y Android).
- **Se mira desde:** localhost en la PC + remoto por Tailscale en el celular (como chequear las cámaras de seguridad desde el teléfono, privado por la red de Tailscale).
- Reusa: backend FastAPI (ya existe) + Tailscale (ya diseñado en ORQUESTACION-REMOTA-DESIGN).

---

## Hub de orquestación único (celu + PC) — Raphael + IAs gratis
**Anotado: 2026-08-30**

Idea: un **solo lugar** (interfaz única en celu y PC) desde donde usar Raphael + varios
modelos **gratis** (OpenRouter free / local), con un orquestador que rutee entre ellos
según la tarea. Se cruza con [[Restaurante Virtual]], [[Herdr]] y la brigada de agentes.

**Verdad estructural (importante, no olvidar):** "Claude Dispatch" **NO se puede meter
como nodo programático** del orquestador — es un sistema hosted de Anthropic (esta interfaz),
sin API para enchufarlo dentro del backend de Raphael. "Claude en el loop" = sesiones de
planificación/arquitectura/builds difíciles con Claude, NO un agente dentro del sistema.
Lo que SÍ se construye: interfaz única sobre **Raphael + modelos gratis**, con Raphael/DeepSeek
(u otro) como orquestador que rutea.

**Por qué NO ahora:** es un build de varias sesiones (Fase 1 de orquestación), no un apuro.
Requiere diseño dedicado. Cimiento ya puesto (2026-08-30): acceso remoto celu↔PC por Tailscale.

---

## 🐞 BUG: el selector de la tray pisa la config de DeepSeek
**Anotado: 2026-08-30**

El selector de modelo de la tray-app (Lite/Medio/Hard) sobrescribe `LMSTUDIO_MODEL`
en `.env` con uno de los `jarvis-text-*` locales, pero **no toca `LMSTUDIO_BASE_URL`**.
Resultado: si estás en DeepSeek (base_url=OpenRouter) y tocás el selector, queda
`base_url=OpenRouter + model=jarvis-text-v2` → **config rota** (OpenRouter no tiene
ese modelo). Pasó el 2026-08-30. Arreglo posible: que el selector sume una opción
"Cloud/DeepSeek" o que no pise la config manual / que setee base_url coherente con
el tier. Mientras tanto: **si usás DeepSeek, no toques el selector de la tray.**
Es un ítem de "mejorar el harness / pantalla de uso".

---

## DeepSeek: experimentos y mejoras (post cambio de cerebro)
**Anotado: 2026-08-26**

Ideas que surgieron apenas DeepSeek quedó funcionando, capturadas para no dispersarse:

- **Harness engineering / mejorar el harness:** revisar el loop del agente y las tools a la luz de los videos ingeridos ("Harness Engineering", "Jerarquía: Modelos, Harness y Orquestadores"). OJO: Jarvis YA es un harness; esto es *mejorar*, no crear uno nuevo.
- **Mejorar la "pantalla de uso"** (la interfaz/tray) — UI, no bloquea nada.
- **Usar DeepSeek como orquestador de otras IAs/agentes** — es la orquestación de la brigada (Fase 1), el plato grande. Se cruza con [[Herdr]] y con el Restaurante Virtual. Requiere decidir el modelo de orquestación antes de construir.

Todo esto es *agregar/mejorar*, no *endurecer*. Va después de la prioridad actual (primera venta) y del endurecimiento Fase 1.

---

## Herdr — multiplexor de terminal para orquestar agentes de código
**Anotado: 2026-08-25**

Herramienta open-source (TUI, multiplataforma) que corre varios agentes de código CLI (Claude Code, Codex, Kimi, OpenCode…) en paneles dentro de una misma terminal, con sesiones persistentes (servidor por detrás), plugins, y un skill para que un agente lea la salida de otro y se pasen tareas. Fuente: video de Fazt Code (transcripción en uploads).

- **Qué NO es:** no es el "restaurante virtual" (el dashboard visual de los agentes de Raphael). Herdr son paneles de terminal, no sprites en una cocina, y no conoce Raphael ni sus tools.
- **Dónde podría encajar (futuro):** en la *orquestación* — Claude orquesta, varios agentes trabajan y se pasan el laburo. O como entorno de desarrollo para Damian (trabajar en Raphael con varios asistentes a la vez).
- **Por qué NO ahora:** cada agente necesita su suscripción/config aparte; es un contenedor de CLIs externos, no integrado con Raphael; adoptarlo es meter un ingrediente nuevo grande (contra "endurecer, no agregar").
- **Depende de:** decidir el modelo de orquestación de la brigada (Fase 1) antes de elegir si Herdr es la herramienta o no.

---

## Definir qué corre en Windows vs Linux (arquitectura híbrida)
**Anotado: 2026-08-24**

Surgió la idea de "usar Linux como base para todo". Conclusión: NO migrar — la arquitectura correcta es híbrida, y ya lo es. Definir formalmente el reparto cuando se arme la orquestación:
- **Windows:** escritorio/uso diario de Damian + **el blanco defensivo y el producto que se vende** (Defender, ASR, AppLocker, WDAC, DPAPI, Sysmon son SOLO Windows; los clientes PyME usan Windows).
- **Linux:** el servidor-agente always-on, lo ofensivo/lab (Kali, nmap, sqlmap, Metasploit, ZAP), la contención en contenedor, y Tailscale SSH (que no funciona como servidor en Windows). Vive en WSL2 o un contenedor.
- Razón de no migrar: se perdería todo el stack defensivo Windows (el producto monetizable) y migrar bases descarrila el servicio. Es un tema de la fase de orquestación/contención, no de ahora.

---
