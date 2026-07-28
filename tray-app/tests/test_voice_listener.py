"""Tests de VoiceListener sin tocar hardware real de audio -- todo lo que
tocaría el micrófono (sd.InputStream) va mockeado o inyectado a mano."""

import queue
import sys
import threading
from unittest.mock import MagicMock

import numpy as np

import voice_listener as vl_module
from voice_listener import VoiceListener


def test_require_wake_word_defaults_true():
    vl = VoiceListener()
    assert vl._require_wake_word is True


def test_require_wake_word_can_be_disabled_for_the_sidebar_button():
    vl = VoiceListener(require_wake_word=False)
    assert vl._require_wake_word is False


def test_stop_aborts_the_audio_stream_immediately_even_if_the_thread_is_stuck():
    """Regresión del bug real reportado el 26/07: el mic quedaba abierto
    mientras el hilo de escucha estuviera trabado (ej. esperando la respuesta
    del backend, hasta 600s). stop() tiene que cortar el audio YA, sin
    esperar a que ese hilo llegue a chequear la bandera de stop."""
    vl = VoiceListener(require_wake_word=False)
    fake_stream = MagicMock()
    vl._stream = fake_stream

    stuck = threading.Event()

    def _stuck_worker():
        stuck.wait(timeout=5)  # simula un hilo trabado en una llamada larga

    vl._thread = threading.Thread(target=_stuck_worker, daemon=True)
    vl._thread.start()

    vl.stop()

    fake_stream.abort.assert_called_once_with(ignore_errors=True)
    stuck.set()
    vl._thread.join(timeout=2)


def test_stop_is_a_no_op_when_never_started():
    vl = VoiceListener(require_wake_word=False)
    vl.stop()  # no debe tirar excepción


def test_stop_swallows_errors_from_abort(monkeypatch):
    vl = VoiceListener(require_wake_word=False)
    fake_stream = MagicMock()
    fake_stream.abort.side_effect = RuntimeError("stream ya cerrado")
    vl._stream = fake_stream

    vl.stop()  # no debe propagar la excepción de abort()


def test_load_models_skips_wake_word_model_when_not_required(monkeypatch):
    vl = VoiceListener(require_wake_word=False)

    fake_vad_module = MagicMock()
    fake_whisper_module = MagicMock()
    monkeypatch.setitem(sys.modules, "openwakeword.vad", fake_vad_module)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper_module)

    vl._load_models()

    assert vl._oww is None, "en modo directo no hace falta cargar el modelo de wake word"
    fake_vad_module.VAD.assert_called_once()
    fake_whisper_module.WhisperModel.assert_called_once()


def test_load_models_loads_wake_word_model_when_required(monkeypatch):
    vl = VoiceListener(require_wake_word=True)

    fake_oww_module = MagicMock()
    fake_vad_module = MagicMock()
    fake_whisper_module = MagicMock()
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_oww_module)
    monkeypatch.setitem(sys.modules, "openwakeword.vad", fake_vad_module)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper_module)

    vl._load_models()

    fake_oww_module.Model.assert_called_once()
    assert vl._oww is not None


def _fill_queue_with_silence(frame_count: int) -> queue.Queue:
    q: queue.Queue = queue.Queue()
    for _ in range(frame_count):
        q.put(np.zeros(vl_module.FRAME_SAMPLES, dtype=np.int16))
    return q


def test_record_command_silent_ok_suppresses_the_error_event():
    """Modo directo (botón de la barra lateral): el silencio mientras se
    espera que el usuario hable es normal, no un error -- no debe generar
    ningún mensaje al usuario."""
    vl = VoiceListener()
    events = []
    vl._on_event = lambda kind, text: events.append((kind, text))
    vl._vad = MagicMock()
    vl._vad.predict.return_value = 0.0  # nunca detecta habla

    max_frames = int(vl_module.MAX_COMMAND_SECONDS * vl_module.SAMPLE_RATE / vl_module.FRAME_SAMPLES)
    q = _fill_queue_with_silence(max_frames)

    result = vl._record_command(q, [], silent_ok=True)

    assert result is None
    assert events == []


def test_record_command_without_silent_ok_emits_the_error_event():
    """Modo con wake word: si detectó "hey jarvis" pero no un comando después,
    sí tiene sentido avisarle al usuario."""
    vl = VoiceListener()
    events = []
    vl._on_event = lambda kind, text: events.append((kind, text))
    vl._vad = MagicMock()
    vl._vad.predict.return_value = 0.0

    max_frames = int(vl_module.MAX_COMMAND_SECONDS * vl_module.SAMPLE_RATE / vl_module.FRAME_SAMPLES)
    q = _fill_queue_with_silence(max_frames)

    result = vl._record_command(q, [], silent_ok=False)

    assert result is None
    assert events == [("error", "Te escuché llamarme pero no escuché ningún comando.")]


def test_record_command_returns_audio_once_speech_then_silence_detected():
    vl = VoiceListener()
    vl._on_event = lambda kind, text: None
    vl._vad = MagicMock()

    silence_frames_needed = int(vl_module.SILENCE_SECONDS_TO_STOP * vl_module.SAMPLE_RATE / vl_module.FRAME_SAMPLES)
    # 3 frames de "habla" (prob alta) seguidos de suficiente silencio para cortar.
    speech_then_silence = [0.9, 0.9, 0.9] + [0.0] * (silence_frames_needed + 1)
    vl._vad.predict.side_effect = speech_then_silence

    q: queue.Queue = queue.Queue()
    for _ in speech_then_silence:
        q.put(np.ones(vl_module.FRAME_SAMPLES, dtype=np.int16) * 1000)

    result = vl._record_command(q, [], silent_ok=True)

    assert result is not None
    assert result.dtype == np.float32
