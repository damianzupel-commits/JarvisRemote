"""Módulo de investigación (análisis de enlaces y evidencia digital) --
tercer dominio de grafo de Jarvis, además del de código y el de conocimiento
(Obsidian). Spec original: `jarvismoduloinvestigacionspec.md` (Damian,
2026-08-12).

Alcance explícito (sección 8 de la spec, no negociable): esta herramienta
analiza material que Damian YA TIENE legítimamente. Nunca hace scraping, ni
consulta agregadores de datos personales, ni deanonimiza o geolocaliza
personas, ni sale a buscar nada por su cuenta. Ver también el rol acotado
del LLM en `models.py`/futuros módulos de esta carpeta: NER, normalización,
hipótesis y borradores -- nunca concluye, nunca puntúa culpabilidad, nunca
escribe sin confirmación humana.
"""
