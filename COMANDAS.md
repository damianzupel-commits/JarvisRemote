# 🍳 COMANDAS — El riel de Raphael

Este es el tablero de trabajo de Damian, con la metáfora de cocina.

- **Tabla** = ideas crudas, todavía sin confirmar. No están acá; están en la cocina scratch.
- **Comanda** = una orden confirmada, colgada en el riel del pase. Estas sí viven acá.
- **Regla de oro:** SOLO UNA en el fuego a la vez. Es la disciplina del servicio — nada de saltar entre ollas.

Formato de cada comanda: `estado — comanda — especialista/estación que la cocina`.

---

## 🔥 En el fuego (una sola a la vez)

- **Cambio de cerebro a DeepSeek V4** (rotar key OpenRouter + cargar crédito + poner las 3 líneas en backend/.env + probar) — *Estación: Config/Modelo (Dueño + Jefe de cocina). Requiere PC.*

---

## 📋 En el pase (pedidas, esperando el fuego)

- **Terminar el MVP técnico del co-host** (correr main.py con el modelo de visión qwen/qwen3.7-flash y confirmar que describe la pantalla) — *Estación: Código/Co-host. Requiere PC.*
- **Sumar personalidad al co-host + llevarlo a Pepi** (después del MVP) — *Estación: Código/Co-host.*
- **SSH desde el celular** (OpenSSH Server de Windows + Tailscale + Termius) — *Estación: Sistema/Red. Requiere PC con admin.*
- **Terminar el doble modo supervisado/autónomo** (la tarea se cortó por límite semanal) — *Estación: Seguridad/Código backend.*
- **Validar los parches en Windows real** (correr los tests: sandbox FS, reintentos, LLM_API_KEY, web_forms/DPAPI, ingesta) — *Estación: Código/Testing. Requiere PC.*
- **Push del repo a GitHub** (subir todo lo pendiente) — *Estación: Sistema/git (tarea de commis). Requiere PC.*
- **Activar la auto-ingesta de la playlist** (el comando schtasks) — *Estación: El pase/Scheduler. Requiere PC.*
- **Ordenar la PC / mise en place** (crear las estaciones 0-Tabla…3-Gourmet y mover archivos) — *Estación: Plongeur/Sistema. Requiere PC.*
- **Endurecimiento Fase 1** (tests adversariales: escape de sandbox + prompt injection; después Raphael-vs-Raphael en el cyber range) — *Estación: Seguridad/Pentest.*
- **Negocio: primer ingreso** (perfil freelance / primer cliente de seguridad) — *Estación: Dueño + Chef ejecutivo — esto lo cocina Damian, es humano/ventas.*

---

## ✅ Servidas

> Ver el detalle completo, rotulado y fechado, en `_cocina-claude/REGISTRO-DE-SERVICIO.md` (39 documentos).

Muestra de las más recientes:

- Documentación completa de Raphael (`docs/raphael/`)
- La Brigada (`docs/LA-BRIGADA.md`)
- Pipeline de ingesta YouTube con discernimiento
- Registro de servicio + cocina de prueba

---

*Nota de uso: toda orden nueva entra al pase. Solo se pasa al fuego cuando el fuego está libre. Al servir, se mueve a Servidas y se anota la fecha.*
