"""On-device speech recognition for Ask AURA, using OpenAI's open-source Whisper model
(run with faster-whisper on the CPU).

Why on-device: a crew on the way to Mars has no link to Google or Apple's cloud speech
services, and health questions should not leave the habitat. The model runs inside AURA.

The model is downloaded once (about 140 MB for "base.en") and loaded the first time it is
needed. If faster-whisper is not installed, or AURA_SPEECH=off, the front end falls back to
the browser's own speech recognition.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time

MODEL_NAME = os.environ.get("AURA_WHISPER_MODEL", "base.en")
# Words Whisper would otherwise mishear; a prompt nudges it towards AURA's vocabulary.
VOCAB_PROMPT = ("Ask AURA: heart rate, blood pressure, SpO2, glucose, body temperature, "
                "sleep, mood, radiation dose, millisievert, paracetamol, flight surgeon, "
                "EVA, SANS, Kenji, Amara, Lena Ortiz.")

_lock = threading.Lock()
_model = None
_state = "idle"  # idle | loading | ready | error
_error: str | None = None


def installed() -> bool:
    if os.environ.get("AURA_SPEECH", "on").lower() == "off":
        return False
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def status() -> dict:
    return {"available": installed() and _state != "error", "state": _state if installed() else "unavailable",
            "model": MODEL_NAME, "error": _error}


def _load():
    global _model, _state, _error
    with _lock:
        if _model is not None:
            return _model
        _state = "loading"
        try:
            from faster_whisper import WhisperModel
            _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
            _state, _error = "ready", None
        except Exception as exc:  # download blocked, out of memory, ...
            _state, _error = "error", f"{type(exc).__name__}: {exc}"[:300]
            raise
        return _model


def warm_up() -> None:
    """Start loading the model in the background so the first question isn't slow."""
    if installed() and _state == "idle":
        threading.Thread(target=lambda: _safe_load(), daemon=True).start()


def _safe_load():
    try:
        _load()
    except Exception:
        pass


def decode(path: str):
    """Browser recordings (webm/opus, Safari's mp4, ogg, wav) to 16 kHz mono float32.
    Done here with PyAV directly, so it works across PyAV versions."""
    import av
    import numpy as np

    chunks = []
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    with av.open(path) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("No audio in the recording.")
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("The recording was empty.")
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def transcribe(audio: bytes, suffix: str = ".webm") -> dict:
    """Turn a recorded clip into text. Raises RuntimeError if speech is unavailable."""
    if not installed():
        raise RuntimeError("On-device speech is not installed on this server.")
    try:
        model = _load()
    except Exception as exc:
        raise RuntimeError(f"The speech model could not load ({_error or exc}).") from exc
    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(audio)
        f.flush()
        samples = decode(f.name)
    segments, info = model.transcribe(samples, language="en", beam_size=1, vad_filter=True,
                                      initial_prompt=VOCAB_PROMPT)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {"text": text, "seconds": round(time.perf_counter() - t0, 2),
            "audio_seconds": round(getattr(info, "duration", 0.0), 2), "model": MODEL_NAME}
