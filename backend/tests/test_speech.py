from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from aura import main, speech

client = TestClient(main.app)


class FakeModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, samples, **kw):
        self.calls.append((samples, kw))
        return iter([SimpleNamespace(text=" Why is my heart rate up?"), SimpleNamespace(text=" ")]), SimpleNamespace(duration=2.4)


@pytest.fixture
def fake(monkeypatch):
    m = FakeModel()
    monkeypatch.setattr(speech, "decode", lambda path: ("decoded", path))
    monkeypatch.setattr(speech, "_model", m)
    monkeypatch.setattr(speech, "_state", "ready")
    monkeypatch.setattr(speech, "installed", lambda: True)
    return m


def test_transcribe_uses_the_local_model(fake):
    r = client.post("/api/speech/transcribe", content=b"fake-audio", headers={"content-type": "audio/webm;codecs=opus"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Why is my heart rate up?" and body["audio_seconds"] == 2.4
    (_, path), kw = fake.calls[0]
    assert path.endswith(".webm") and kw["language"] == "en" and "SpO2" in kw["initial_prompt"]
    client.post("/api/speech/transcribe", content=b"fake-audio", headers={"content-type": "audio/mp4"})
    assert fake.calls[1][0][1].endswith(".mp4")  # Safari records mp4


def test_transcribe_rejects_empty_and_huge(fake):
    assert client.post("/api/speech/transcribe", content=b"").status_code == 422
    big = b"x" * (main.MAX_AUDIO_BYTES + 1)
    assert client.post("/api/speech/transcribe", content=big).status_code == 413


def test_unavailable_falls_back(monkeypatch):
    monkeypatch.setattr(speech, "installed", lambda: False)
    st = client.get("/api/speech/status").json()
    assert st["available"] is False and st["state"] == "unavailable"
    r = client.post("/api/speech/transcribe", content=b"fake-audio")
    assert r.status_code == 503 and "not installed" in r.json()["detail"]


def test_switch_off_with_env(monkeypatch):
    monkeypatch.setenv("AURA_SPEECH", "off")
    assert speech.installed() is False


def test_decode_real_browser_formats(tmp_path):
    """Real PyAV decoding of the formats browsers record (webm/opus and Safari's mp4/aac)."""
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available to make test clips")
    for name, codec in (("clip.webm", "libopus"), ("clip.mp4", "aac")):
        p = tmp_path / name
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                        "-ac", "2", "-ar", "48000", "-c:a", codec, str(p)], check=True)
        x = speech.decode(str(p))
        assert x.dtype.name == "float32" and 1.8 * 16000 < len(x) < 2.2 * 16000 and abs(x).max() <= 1.0


def test_garbage_audio_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(speech, "_model", FakeModel())
    monkeypatch.setattr(speech, "installed", lambda: True)
    r = client.post("/api/speech/transcribe", content=b"not audio at all", headers={"content-type": "audio/webm"})
    assert r.status_code == 422 and "Could not read" in r.json()["detail"]
