# 🍳 COMANDAS — El riel de Raphael

El tablero de trabajo de Damian, con la metáfora de cocina.

## El flujo de un plato (4 pasos)

1. **Entra la comanda** — una orden confirmada entra al riel.
2. **Se ponen los ingredientes en la tabla** — mise en place: se prepara todo lo
   necesario para cocinarla.
3. **Pasa al fuego y se cocina** — se ejecuta. **Regla de oro: UNA sola en el
   fuego a la vez.** Nada de saltar entre ollas.
4. **Se emplata y se entrega** — se sirve y se registra.

> **Tabla de ideas crudas** = ideas todavía SIN confirmar como comanda. Viven en
> `TABLA.md`, no acá. Solo cuando se deciden cocinar bajan al paso 1.

Última actualización: **2026-08-26** (cierre de un día de 5 platos servidos).

---

## 🔥 Paso 3 — En el fuego (una sola)

- *Libre.* El próximo en entrar al fuego es **la primera venta** (ver Paso 2).

---

## 🔪 Paso 2 — En la tabla (ingredientes puestos, listo para cocinar)

- **Primera venta / primer ingreso** — oferta y checklist de "Blindaje PyME"
  listas (`Escritorio/Blindaje-PyME-Checklist-15min.md`). Falta ejecutar: entrar
  a los primeros cafés/negocios con el guion. *Agendado: en 3-4 días. Estación:
  Dueño (esto lo cocina Damian, es humano/ventas).*
- **Ingesta: cola final** — 3 videos restantes esperando que se destrabe la IP de
  YouTube (bloqueo temporal por muchos pedidos). Re-run cuando levante.

---

## 📋 Paso 1 — Entra la comanda (pedidas, esperando turno)

- **Probar el MVP del co-host** en tu PC (main.py con qwen visión) + sumar
  personalidad y llevarlo a Pepi. *Estación: Código/Co-host. Requiere PC.*
- **SSH desde el celular** (OpenSSH Server + Tailscale + Termius). *Sistema/Red.*
- **Terminar el doble modo supervisado/autónomo** (se cortó por límite semanal).
  *Seguridad/Código backend.*
- **Validar los parches en Windows real** (tests: sandbox FS, reintentos,
  LLM_API_KEY, web_forms/DPAPI, ingesta). *Código/Testing.*
- **Activar la auto-ingesta de la playlist** (schtasks). *Scheduler.*
- **Ordenar la PC / mise en place** (estaciones 0-Tabla…3-Gourmet). *Sistema.*
- **Endurecimiento Fase 1** ⬅️ *al frente de la cola.* Tests adversariales
  (escape de sandbox + prompt injection) y **cyber range / VM lab**
  (Raphael-vs-Raphael, receta 04). ⚠️ Requiere jaula herméticamente aislada
  ANTES de tirar nada — se hace con cabeza fresca, no apurado. *Seguridad/Pentest.*

---

## 🍽️ Paso 4 — Emplatado y entregado

### Servidas hoy (2026-08-26)

- ✅ **Cambio de cerebro a DeepSeek V4** — crédito cargado, `.env` a
  `deepseek/deepseek-v4-pro-0813`, andando. (Backup de config local en
  `.env.bak-openrouter`.)
- ✅ **Respaldo/push a GitHub** (`f1017f2`) — trabajo del día a salvo.
- ✅ **49 de 52 videos nuevos ingeridos** con discernimiento de relevancia + **fix
  de traducción** (portugués→es/en) y pin `youtube-transcript-api>=1.2`.
  Committeado.
- ✅ **Oferta + checklist "Blindaje PyME"** — herramienta de venta lista.
- ✅ **Investigación de apellidos** (Zupel / Pucheta / Lovey).

### Servidas anteriores

> Detalle completo, rotulado y fechado, en
> `_cocina-claude/REGISTRO-DE-SERVICIO.md`.

- Documentación completa de Raphael (`docs/raphael/`)
- La Brigada (`docs/LA-BRIGADA.md`)
- Pipeline de ingesta YouTube con discernimiento
- Registro de servicio + cocina de prueba

---

*Nota de uso: toda orden nueva entra al Paso 1. Solo pasa al fuego (Paso 3)
cuando el fuego está libre. Al servir, se mueve al Paso 4 con la fecha.*
