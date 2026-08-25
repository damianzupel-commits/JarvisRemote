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

## Definir qué corre en Windows vs Linux (arquitectura híbrida)
**Anotado: 2026-08-24**

Surgió la idea de "usar Linux como base para todo". Conclusión: NO migrar — la arquitectura correcta es híbrida, y ya lo es. Definir formalmente el reparto cuando se arme la orquestación:
- **Windows:** escritorio/uso diario de Damian + **el blanco defensivo y el producto que se vende** (Defender, ASR, AppLocker, WDAC, DPAPI, Sysmon son SOLO Windows; los clientes PyME usan Windows).
- **Linux:** el servidor-agente always-on, lo ofensivo/lab (Kali, nmap, sqlmap, Metasploit, ZAP), la contención en contenedor, y Tailscale SSH (que no funciona como servidor en Windows). Vive en WSL2 o un contenedor.
- Razón de no migrar: se perdería todo el stack defensivo Windows (el producto monetizable) y migrar bases descarrila el servicio. Es un tema de la fase de orquestación/contención, no de ahora.

---
