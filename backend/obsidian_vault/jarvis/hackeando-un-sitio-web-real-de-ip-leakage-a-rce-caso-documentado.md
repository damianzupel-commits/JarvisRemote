---
author: jarvis
category: pentesting
created: '2026-08-16T19:52:10.836906+00:00'
tags:
- info-para-jarvis
- video
- pentest
- caso-real
title: 'Hackeando un sitio web real: de IP leakage a RCE (caso documentado)'
updated: '2026-08-16T19:52:10.836906+00:00'
---

Resumen generado por NotebookLM a partir del video de YouTube "Hackeando Un Sitio Web. (REAL) (EXPLICADO)", de la playlist personal de Damian "Info para Jarvis".

## Fuente
- Video: https://www.youtube.com/watch?v=iXOlQszplC8
- Canal: 0xFaluch0
- Duración: 30:18
- Generado con: NotebookLM (Google), a partir de la transcripción del video

## Resumen
Este video documenta un ataque de ciberseguridad real y autorizado contra el sitio web Rosed, estructurado en las fases de reconocimiento, explotación y reporte. El proceso comienza identificando un IP leakage causado por una cabecera de redirección que permitió evadir la protección de Cloudflare, exponiendo la dirección IP verdadera del servidor y su base de datos PostgreSQL a internet. Al aprovechar credenciales por defecto halladas en un repositorio de GitHub, el atacante logra acceso total a la información de los usuarios y escala el ataque mediante una ejecución remota de código (RCE) para obtener una consola dentro del sistema operativo Linux. Finalmente, el autor demuestra cómo un intruso puede realizar un escalamiento de privilegios y subraya que la seguridad informática depende críticamente de una configuración correcta y de evitar la exposición innecesaria de servicios internos.

## Temas clave
- Reconocimiento de activos
- Evasión de protección Cloudflare (IP leakage)
- Filtración de IP real del servidor
- Explotación de bases de datos expuestas
- Ejecución remota de código (RCE) y escalamiento de privilegios

## Notas relacionadas
- [[Índice: pentesting]]
- [[Playlist: Información para Jarvis (YouTube)]]
- [[Credenciales por defecto en dispositivos IoT y como se explotan]]