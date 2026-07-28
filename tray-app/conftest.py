import sys
from pathlib import Path

# Los módulos de tray-app usan imports planos (`import config`, `import
# process_manager`, etc.), no un paquete instalado -- sin esto pytest no los
# encuentra al correr los tests desde tests/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
