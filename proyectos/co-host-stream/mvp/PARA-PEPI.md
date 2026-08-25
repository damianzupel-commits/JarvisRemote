# Co-host de stream — Instrucciones rápidas (para Pepi)

Prueba técnica: mira tu pantalla cada X segundos y comenta lo que ve, por texto.
Todavía SIN voz ni personaje — es solo para confirmar que funciona.

## Requisitos
- Python instalado (con "Add Python to PATH").
- Una cuenta de **OpenRouter** con un poco de crédito y una **API key**.
- El modelo tiene que ser de **visión** (multimodal). Recomendado: `qwen/qwen3.7-flash`.

## Pasos (3 clics)
1. **Doble clic en `setup.bat`** → instala las dependencias y crea el archivo `.env`.
2. **Abrí `.env`** con el Bloc de notas y pegá tu API key de OpenRouter en:
   ```
   OPENROUTER_API_KEY=sk-or-v1-TU_KEY_ACA
   VISION_MODEL=qwen/qwen3.7-flash
   CAPTURE_INTERVAL_SECONDS=10
   ```
   Guardá y cerrá.
3. **Doble clic en `run.bat`** → arranca. Cada 10 segundos vas a ver una línea con lo que el modelo ve en tu pantalla.

Para cortarlo: cerrá la ventana negra o apretá Ctrl+C.

## Ojo
- La API key va SOLO en el `.env`, nunca la compartas por chat.
- Cuesta centavos (~US$0.11–0.21 por hora). Con poco crédito te sobra para probar.
- Apuntalo a la ventana del juego, no a tu escritorio con datos privados (más adelante).
