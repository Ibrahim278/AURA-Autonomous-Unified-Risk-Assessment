from fastapi.testclient import TestClient

from aura import main, voice

client = TestClient(main.app)


def test_digits_sentence():
    r = voice.parse("Heart rate 62, blood pressure 118 over 76, temperature 36.8, slept six and a half hours, "
                    "mood 7, and I have a mild headache")
    assert r["values"] == {"heart_rate": 62, "systolic_bp": 118, "diastolic_bp": 76, "body_temp": 36.8,
                           "sleep_hours": 6.5, "mood": 7}
    assert [s["key"] for s in r["symptoms"]] == ["headache"]


def test_number_words():
    assert voice.words_to_numbers("sixty two") == "62"
    assert voice.words_to_numbers("one hundred eighteen over seventy six") == "118 over 76"
    assert voice.words_to_numbers("thirty six point eight") == "36.8"
    r = voice.parse("pulse sixty two, BP one hundred eighteen over seventy six, glucose ninety four")
    assert r["values"] == {"heart_rate": 62, "systolic_bp": 118, "diastolic_bp": 76, "glucose": 94}


def test_slash_and_symptoms_and_nothing():
    r = voice.parse("blood pressure 120/80, exercised 95 minutes, feeling tired and short of breath")
    assert r["values"] == {"systolic_bp": 120, "diastolic_bp": 80, "exercise_minutes": 95}
    keys = {s["key"]: s for s in r["symptoms"]}
    assert keys["breathing"]["red_flag"] and "fatigue" in keys
    assert voice.parse("hello there")["understood"] is False


def test_api():
    r = client.post("/api/checkins/parse", json={"text": "oxygen 97, mood 8"}).json()
    assert r["values"] == {"spo2": 97, "mood": 8}
    assert client.post("/api/checkins/parse", json={"text": ""}).status_code == 422
