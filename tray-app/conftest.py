import os
import sys
from pathlib import Path

# Los módulos de tray-app usan imports planos (`import config`, `import
# process_manager`, etc.), no un paquete instalado -- sin esto pytest no los
# encuentra al correr los tests desde tests/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Mismo motivo que en tray.py: QtWebEngine (test_graph_view.py construye un
# QWebEngineView real) crashea de forma reproducible en esta GPU si se le deja
# el compositor de Chromium con aceleración por GPU prendida -- sin esto,
# correr la suite de tests entera se cuelga/crashea en vez de solo fallar los
# tests de WebGL. `--disable-gpu-compositing` (no `--disable-gpu` a secas)
# porque los tests de test_graph_view.py necesitan WebGL real funcionando, no
# solo que no crashee. Tiene que setearse antes de que cualquier test importe
# PySide6/QtWebEngine.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-compositing")
