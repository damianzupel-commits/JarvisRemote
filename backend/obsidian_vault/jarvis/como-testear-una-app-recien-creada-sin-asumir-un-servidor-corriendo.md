---
author: jarvis
category: codigo-seguro
created: '2026-08-10T07:43:53.835667+00:00'
tags:
- testing
- buenas-practicas
- flask
title: Cómo Testear una App Recién Creada Sin Asumir un Servidor Corriendo
updated: '2026-08-10T07:43:53.835667+00:00'
---

Nota operativa, nace de un test real (2026-08-10): se le pidió a Jarvis crear una todo-list en Flask desde cero (`fs_create_dir`/`fs_write_file`/`pc_run_command`) y después auditarla -- el create funcionó bien (venv real, `pip install`, app funcional con rutas CRUD), pero el paso de auto-verificación (correr `pytest`) falló dos veces seguidas por el mismo motivo evitable, documentado abajo para no repetirlo.

## Si un comando falla con "No module named X", el siguiente paso es instalar X -- no escribir más código asumiendo que ya funciona

Error real observado: se corrió `.venv\Scripts\python.exe -m pytest` sin que `pytest` estuviera en `requirements.txt` ni instalado en el venv -- falló con `No module named pytest`. En vez de instalar `pytest` (`pip install pytest`) y reintentar, el siguiente paso fue escribir un archivo de test nuevo y correr `pytest` otra vez, con el mismo entorno roto -- falló exactamente igual la segunda vez.

- Ante "No module named X" (o cualquier "command not found"/"no such file" al correr una herramienta), el diagnóstico es mecánico: la herramienta no está instalada en el entorno que se está usando. El fix es instalarla (`pip install X`, agregarla a `requirements.txt` o a un `requirements-dev.txt` separado si es solo para testing) ANTES de reintentar el comando que la necesita.
- Reintentar el mismo comando en el mismo entorno esperando un resultado distinto sin cambiar nada es un desperdicio de una vuelta completa del loop (arrancar un turno del agente, en un contexto ya grande, puede tardar varios minutos) -- diagnosticar la causa real del fallo antes de reintentar es más rápido que reintentar a ciegas.

## Para testear una app Flask, usá `app.test_client()` -- no asumas un servidor externo corriendo

Error real observado: el test escrito importaba `requests` (biblioteca externa, tampoco instalada) y apuntaba a `http://127.0.0.1:5000` -- un test así solo puede pasar si HAY un proceso de Flask corriendo en ese puerto en paralelo, algo que ninguna tool disponible (`pc_run_command` es síncrono, espera a que el comando termine) puede dejar corriendo en background mientras corre `pytest` en el mismo turno.

- Flask expone `app.test_client()` específicamente para este caso: permite mandar requests HTTP simulados directo al objeto `app` sin levantar un servidor real ni un puerto ni un proceso aparte -- el patrón correcto es `client = app.test_client()` y despues `client.get('/')`, `client.post('/api/tasks', json=...)`, etc., todo dentro del mismo proceso de test.
- Este patrón no depende de sockets, puertos libres, ni de ningún proceso en background -- es determinístico y corre con un solo `pytest`, sin pasos previos de "levantar el servidor".

## Declará todas las dependencias reales del proyecto, incluidas las de test

`requirements.txt` solo tenía `Flask` y `python-dotenv` (lo que la app necesita para CORRER) -- nunca se actualizó para incluir `pytest` ni ninguna dependencia de test, a pesar de que el test file sí las necesitaba para poder correr.

- Si el proyecto va a tener tests, sus dependencias (`pytest`, y cualquier librería que el test importe) tienen que quedar declaradas -- en el mismo `requirements.txt` si el proyecto es chico, o en un `requirements-dev.txt` aparte si se quiere separar runtime de testing -- e instalarse antes de intentar correr los tests, no después de que fallen.

## Ver también
[[Cómo Jarvis Repara Hallazgos de Seguridad Sin Perder el Foco]]