"""Extrae frames de un video para mandárselos a un modelo de visión como una
secuencia de imágenes, en vez de mandar el archivo de video crudo.

Por qué esta estrategia y no mandar el video tal cual: el soporte de LM Studio
(servidor local, motor llama.cpp) para adjuntar un archivo de video crudo en un
mensaje multimodal NO está confirmado de forma confiable — el formato
multimodal de la API estilo OpenAI que expone (`content: [{"type":"image_url",
...}]`) está pensado y probado para imágenes, no para video. En cambio,
extraer varios frames (uno cada `video_frame_interval_seconds`, ver
`config.Settings`) y mandarlos como una secuencia de `image_url` en un solo
mensaje es exactamente el mismo mecanismo ya validado para `phone_take_photo`
— y la gran mayoría de los modelos VL modernos (incluido Qwen3-VL) soportan
múltiples imágenes por prompt de forma nativa. Es la opción robusta: depende
de una capacidad (imágenes múltiples) que sabemos que funciona, en vez de una
(video nativo) que no está garantizada en este server local.

Usa OpenCV (`opencv-python-headless`) para decodificar el video — no depende
de tener `ffmpeg` como binario aparte instalado en la PC.
"""

import base64
import tempfile
from pathlib import Path

import cv2


class VideoDecodeError(RuntimeError):
    """El video no se pudo decodificar (archivo corrupto, códec no soportado, etc.)."""


def extract_frames_from_video_base64(
    video_base64: str,
    interval_seconds: float,
    max_frames: int,
    jpeg_quality: int = 80,
    max_dimension: int = 1024,
) -> list[str]:
    """Decodifica `video_base64` (bytes de un archivo de video, ej. mp4) y devuelve una
    lista de frames como JPEG en base64 (mismo formato que usa `phone_take_photo`),
    tomando uno cada `interval_seconds` hasta un máximo de `max_frames`."""
    video_bytes = base64.b64decode(video_base64)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        temp_path = tmp.name

    try:
        return _extract_frames_from_file(temp_path, interval_seconds, max_frames, jpeg_quality, max_dimension)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def _extract_frames_from_file(
    path: str,
    interval_seconds: float,
    max_frames: int,
    jpeg_quality: int,
    max_dimension: int,
) -> list[str]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        raise VideoDecodeError("No se pudo abrir el video capturado (¿archivo corrupto o códec no soportado?).")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, round(fps * interval_seconds))

        frames_b64: list[str] = []
        frame_idx = 0
        while len(frames_b64) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % frame_interval == 0:
                frame = _resize_frame(frame, max_dimension)
                encoded, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if encoded:
                    frames_b64.append(base64.b64encode(buf.tobytes()).decode("ascii"))
            frame_idx += 1

        if not frames_b64:
            raise VideoDecodeError("El video no tenía ningún frame legible.")
        return frames_b64
    finally:
        cap.release()


def _resize_frame(frame, max_dimension: int):
    height, width = frame.shape[:2]
    longest = max(height, width)
    if longest <= max_dimension:
        return frame
    scale = max_dimension / longest
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
