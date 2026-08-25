"""
Prueba tecnica minima del co-host de stream.

SIN personalidad, SIN voz, SIN OBS. Solo comprueba el circuito:
    captura de pantalla -> modelo de vision (OpenRouter) -> print en consola.

Corre en loop cada N segundos. Ctrl+C corta limpio.
"""

import base64
import io
import os
import sys
import time
from datetime import datetime

import mss
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

# Prompt NEUTRO a proposito: esto es solo la prueba tecnica, sin personaje.
PROMPT = "Describi brevemente que esta pasando en esta pantalla, en una o dos frases."

# Ancho al que reducimos la captura antes de mandarla (baja costo/tokens).
TARGET_WIDTH = 1024


def cargar_config():
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("VISION_MODEL", "google/gemini-flash-1.5")
    try:
        interval = float(os.getenv("CAPTURE_INTERVAL_SECONDS", "10"))
    except ValueError:
        interval = 10.0

    if not api_key or api_key.startswith("sk-or-v1-TU_KEY"):
        print("ERROR: falta OPENROUTER_API_KEY. Copia .env.example a .env y "
              "pone tu key real.")
        sys.exit(1)

    return api_key, model, interval


def capturar_pantalla_base64():
    """Captura el monitor principal, la reduce a TARGET_WIDTH y devuelve JPEG base64."""
    with mss.mss() as sct:
        # sct.monitors[0] es la union de todos; [1] es el monitor principal.
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.rgb)

    if img.width > TARGET_WIDTH:
        ratio = TARGET_WIDTH / img.width
        nuevo_alto = int(img.height * ratio)
        img = img.resize((TARGET_WIDTH, nuevo_alto), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def comentar_pantalla(client, model, img_b64):
    """Manda la imagen al modelo de vision y devuelve el texto de la respuesta."""
    respuesta = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        },
                    },
                ],
            }
        ],
    )
    return respuesta.choices[0].message.content


def main():
    api_key, model, interval = cargar_config()
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    print(f"Co-host MVP arrancado. Modelo: {model}. Intervalo: {interval}s. "
          "Ctrl+C para cortar.\n")

    try:
        while True:
            ts = datetime.now().strftime("%H:%M:%S")
            try:
                img_b64 = capturar_pantalla_base64()
                comentario = comentar_pantalla(client, model, img_b64)
                print(f"[{ts}] {comentario}\n")
            except Exception as e:
                # Si la API o la captura falla, log y seguimos.
                print(f"[{ts}] ERROR: {e}\n")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nCortado por el usuario. Chau.")


if __name__ == "__main__":
    main()
