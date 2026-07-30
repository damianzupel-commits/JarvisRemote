"""Reconocimiento de RED real (nmap) -- a diferencia de `security/`/`quality/`
(SAST/SCA puro, solo lee código/manifiestos en disco), este paquete ejecuta
escaneos reales contra hosts en red. Ver `guardrail.py` para el límite de
scope (no negociable) y `scanner.py` para el wrapper de subprocess sobre
nmap. La tool que el LLM invoca vive en `app/tools/network_scan.py`.
"""
