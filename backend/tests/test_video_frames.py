import base64

import cv2
import numpy as np
import pytest

from app.video_frames import VideoDecodeError, extract_frames_from_video_base64


def _make_test_video_base64(tmp_path, num_frames: int = 30, fps: float = 10.0, size: tuple = (64, 48)) -> str:
    """Genera un video sintético chiquito (frames de color sólido) y lo devuelve
    codificado en base64 — no depende de ningún archivo de fixture externo."""
    path = tmp_path / "synthetic.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, size)
    assert writer.isOpened(), "no se pudo abrir VideoWriter — revisar códecs de OpenCV en este entorno"
    try:
        for i in range(num_frames):
            # Frame de color sólido que cambia con i, para no depender de contenido real.
            frame = np.full((size[1], size[0], 3), i % 256, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()

    return base64.b64encode(path.read_bytes()).decode("ascii")


def test_extract_frames_returns_at_least_one_valid_jpeg(tmp_path):
    video_b64 = _make_test_video_base64(tmp_path, num_frames=30, fps=10.0)

    frames = extract_frames_from_video_base64(video_b64, interval_seconds=1.0, max_frames=8)

    assert 1 <= len(frames) <= 8
    for frame_b64 in frames:
        frame_bytes = base64.b64decode(frame_b64)
        decoded = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None
        assert decoded.shape[0] > 0 and decoded.shape[1] > 0


def test_extract_frames_respects_max_frames_cap(tmp_path):
    # 3 segundos a 10fps con intervalo de 0.1s pediría ~30 frames si no hubiera tope.
    video_b64 = _make_test_video_base64(tmp_path, num_frames=30, fps=10.0)

    frames = extract_frames_from_video_base64(video_b64, interval_seconds=0.1, max_frames=3)

    assert len(frames) <= 3


def test_extract_frames_downscales_to_max_dimension(tmp_path):
    video_b64 = _make_test_video_base64(tmp_path, num_frames=10, fps=10.0, size=(800, 400))

    frames = extract_frames_from_video_base64(video_b64, interval_seconds=1.0, max_frames=4, max_dimension=300)

    frame_bytes = base64.b64decode(frames[0])
    decoded = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert max(decoded.shape[0], decoded.shape[1]) <= 300


def test_extract_frames_raises_on_garbage_input():
    garbage_b64 = base64.b64encode(b"esto no es un video de verdad").decode("ascii")

    with pytest.raises(VideoDecodeError):
        extract_frames_from_video_base64(garbage_b64, interval_seconds=1.0, max_frames=8)
