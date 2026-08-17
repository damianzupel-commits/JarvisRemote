"""Formularios/registros web completados por Jarvis (spec de Damian,
2026-08-16 -- "completar formularios web y registrarse en sitios cuando yo
se lo pida, incluso lejos de la PC"). Reusa el navegador ya controlado por
`app/tools/browser.py` (Playwright + Edge del sistema) para el lado de
interacción con la página; este paquete es la parte de estado propio:
generación y guarda cifrada (DPAPI) de contraseñas generadas para esos
registros, ver `credential_store.py`.
"""
