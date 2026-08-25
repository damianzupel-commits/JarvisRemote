# 07 — Levantar el co-host de stream

> Armar el MVP de un **co-host de stream con IA**: un compañero que mira la pantalla
> en vivo, decide si vale la pena hablar, y comenta con personalidad. Es un **primo
> separado** de Raphael (su propio repo/proceso), que reúsa piezas y patrones.
>
> Basada en [`../proyectos/co-host-stream/DISENO.md`](../proyectos/co-host-stream/DISENO.md).

## Qué produce

**MVP (Fase 1):** el bucle mínimo funcionando — captura la ventana del juego cada
~10 s → modelo de visión describe qué pasa → un personaje decide si comentar y qué
decir → aparece en texto (consola/pantalla), **sin voz todavía**. Valida lo más
difícil: que **vea bien** y que el **pacing** no lo haga hablar sin parar.

## Estación / especialista

Código / **Co-host** (proyecto primo, separado de Raphael). **Requiere PC.**
Corresponde a las comandas del co-host en [`../COMANDAS.md`](../COMANDAS.md).

## Ingredientes (requisitos previos)

- **Cuenta de OpenRouter + crédito** con un **modelo de VISIÓN** elegido (no de solo
  texto — un modelo de texto no puede ver el screenshot). Arranque sugerido:
  `deepseek/deepseek-v4-flash-vision-exp` (el más barato capaz) o
  `google/gemini-3.7-flash` (mejor equilibrio). Para depurar sin gastar, un `:free`
  con visión (`google/gemma-4-31b-it:free`) — no aguanta un stream real, solo prueba.
- La captura de pantalla reusable de Raphael: `backend/app/tools/desktop.py`
  (`desktop_screenshot`, `desktop_list_windows`, `desktop_focus_window`) — código
  casi reutilizable; falta recortar a una ventana específica.
- El patrón de conexión OpenRouter (receta 02), apuntando a un modelo de visión.
- Definido: 1 personaje para el MVP (nombre + personalidad/estilo).

## Pasos

1. **Setup de visión.** Cuenta OpenRouter + crédito, elegir modelo de visión, probar
   la conexión con un `:free` primero. Armar la llamada multimodal (imagen + prompt)
   al endpoint OpenAI-compatible.
2. **Captura acotada.** Extender el screenshot de `desktop.py` para capturar **solo
   la ventana del juego** (o mejor, la salida de OBS), **nunca el escritorio
   entero** — regla de oro de privacidad (§6 del diseño): si captura todo, puede leer
   en voz alta un DM, una notificación o una contraseña al aire.
3. **El bucle mínimo.** Cada ~10 s: captura → manda al modelo de visión → el motor de
   comentarios (LLM en personaje) decide **si** comentar y **qué** decir → sale en
   texto. Con **pacing** (¿pasó suficiente tiempo?, ¿cambió la escena?, ¿no está
   hablando ya?) y **memoria corta** (no repetirse). Muchas vueltas terminan en
   **silencio a propósito** — eso separa "co-host" de "loro que no calla".
4. **Probar y afinar el pacing** con un modelo `:free` para no gastar mientras se
   depura. Confirmar que ve bien y que calla cuando no aporta.

**Fases siguientes (fuera del MVP):** Fase 2 = TTS local (Piper/Kokoro) → el
personaje habla, salida a OBS. Fase 3 = biblioteca de personajes intercambiables.
Fase 4 = integración fina con OBS (overlay, disparadores, comentar selectivo por
cambio de escena para bajar costo) + capa de moderación.

## Tiempo estimado

MVP (Fase 1): unas sesiones de desarrollo. El setup de visión + captura acotada es
lo primero; el pacing es lo que lleva iteración.

## Notas / errores comunes

- **Es un primo SEPARADO de Raphael**, no una función suya: vive en su propio repo y
  proceso. Comparten ADN (captura, config OpenRouter, idea de personas, molde de
  skills), no cuerpo.
- **Sin visión no hay co-host.** El DeepSeek V4 de texto que usa Raphael no sirve
  acá; hace falta un modelo multimodal.
- **Costo realista:** con un modelo de visión barato, mirar la pantalla cada 5–10 s
  cuesta ~$0.10–$0.45 por hora de stream. Palancas para bajarlo: muestrear menos
  seguido, bajar resolución del screenshot, y comentar selectivo (solo llamar al
  modelo caro cuando la escena cambió, con hash perceptual local gratis).
- **La voz hay que construirla nueva:** Raphael tiene entrada de voz (wake word en
  `voice_listener.py`) pero **no** salida (TTS). El TTS del co-host es capacidad
  nueva.
- **Moderación no es opcional** (para cuando hable): filtro antes del TTS, reglas por
  personaje, botón de pánico/mute. Ante la duda, callar — un silencio es mejor que un
  ban del canal.

## ¿Candidata a skill?

**📝 receta a mano.** Es un proyecto separado en construcción, no un procedimiento
que Raphael repita. No aplica graduarlo a skill de Raphael; su propia arquitectura
de "personajes" es el equivalente al molde de skills, pero dentro del co-host.
