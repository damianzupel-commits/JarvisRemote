---
author: jarvis
category: seguridad-informatica
created: '2026-08-26T16:17:29.410139+00:00'
relevancia: útil
relevancia_score: 5
tags:
- info-para-jarvis
- video
- seguridad-informatica
title: 'Ataque de Phishing Invisibles: Cómo los atacantes roban cuentas incluso con
  2FA'
updated: '2026-08-26T16:17:29.410139+00:00'
---

Resumen automático generado a partir de la transcripción del video de YouTube "UNDETECTABLE PHISHING | How they steal your account even with 2FA", de la playlist personal de Damian "Info para Jarvis".

## Fuente
- Video: https://www.youtube.com/watch?v=dft1n1Kr168
- Canal: Roger Biderbost
- Duración: 21:19
- Generado con: resumen automático

## Resumen
Este video explica una técnica avanzada de phishing conocida como 'browser in the browser' (BitB), donde la víctima accede a una página legítima como Gmail o WhatsApp, pero dentro de un navegador controlado por el atacante. A diferencia del phishing tradicional, no hay dominios sospechosos ni errores visuales, ya que el sitio real se carga dentro de un entorno manipulado. El atacante utiliza una VPS con Docker para ejecutar un Firefox en un contenedor, capturando todo lo tecleado mediante una extensión tipo keylogger. Mientras la víctima ingresa credenciales y el segundo factor, el atacante monitorea en tiempo real y, al detectar el acceso, bloquea la conexión legítima y toma el control de la cuenta. El ataque es especialmente peligroso porque evade incluso el 2FA, ya que la autenticación ocurre en el entorno controlado. El video demuestra el proceso paso a paso con herramientas como SSH, Docker, y configuraciones de DNS, destacando la importancia de reconocer señales de alerta como navegadores anómalos o comportamientos inusuales.

## Temas clave
- browser in the browser
- phishing avanzado
- captura de credenciales
- 2FA bypass
- Docker y contenedores
- keylogger en navegador

## Relevancia
- Veredicto: útil
- Puntaje: 5/5
- Razón: El video explica detalladamente un ataque de ciberseguridad ofensiva avanzado, específicamente el 'browser in the browser', relevante para la defensa y comprensión de técnicas de phishing modernas.

## Notas relacionadas
- [[Índice: seguridad-informatica]]
- [[Playlist: Información para Jarvis (YouTube)]]