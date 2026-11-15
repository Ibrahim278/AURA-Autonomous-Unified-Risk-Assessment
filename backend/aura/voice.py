"""Voice check-in: turn a spoken (or typed) sentence into check-in values.

Gloves on, hands busy, floating: speaking is often easier than typing. The browser turns speech
into text (Web Speech API); this module parses the text with transparent rules, so nothing is
saved until the astronaut has seen the filled-in form and pressed Log check-in.

Example: "Heart rate 62, blood pressure 118 over 76, temperature 36.8, slept six and a half
hours, mood 7, and I have a mild headache" ->
  {heart_rate: 62, systolic_bp: 118, diastolic_bp: 76, body_temp: 36.8, sleep_hours: 6.5, mood: 7}
  plus the symptom "headache" suggested for the symptom log.
"""

from __future__ import annotations

import re

from .symptoms import CATALOG

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}

NUM = r"(\d+(?:\.\d+)?)"
PATTERNS: list[tuple[str, str]] = [
    ("bp", rf"(?:blood pressure|bp|pressure)\D{{0,12}}?{NUM}\s*(?:over|/|and)\s*{NUM}"),
    ("heart_rate", rf"(?:heart ?rate|pulse|hr)\D{{0,12}}?{NUM}"),
    ("spo2", rf"(?:oxygen|spo2|sp o2|saturation|sats?)\D{{0,12}}?{NUM}"),
    ("glucose", rf"(?:glucose|blood sugar|sugar)\D{{0,12}}?{NUM}"),
    ("body_temp", rf"(?:temperature|temp)\D{{0,12}}?{NUM}"),
    ("sleep_hours", rf"(?:slept|sleep)\D{{0,12}}?{NUM}(\s+and a half)?"),
    ("mood", rf"(?:mood|feeling about|feel like a)\D{{0,12}}?{NUM}"),
    ("exercise_minutes", rf"(?:exercised?|workout|worked out|training|trained)\D{{0,12}}?{NUM}"),
    ("radiation_dose", rf"(?:dosimeter|radiation|dose)\D{{0,12}}?{NUM}"),
]

SYMPTOM_WORDS = {
    "headache": "headache", "head ache": "headache", "blurry": "blurred_vision", "blurred": "blurred_vision",
    "nause": "nausea", "vomit": "nausea", "sick to my stomach": "nausea", "stuffy": "congestion",
    "congest": "congestion", "back pain": "back_pain", "back hurts": "back_pain", "sore back": "back_pain",
    "muscle": "muscle_pain", "joint": "muscle_pain", "tired": "fatigue", "exhausted": "fatigue",
    "fatigue": "fatigue", "chills": "chills", "feverish": "chills", "shiver": "chills",
    "can't sleep": "insomnia", "cannot sleep": "insomnia", "insomnia": "insomnia", "trouble sleeping": "insomnia",
    "anxious": "low_mood", "anxiety": "low_mood", "feeling down": "low_mood", "sad": "low_mood", "low mood": "low_mood",
    "rash": "rash", "itchy": "rash", "chest pain": "chest_pain", "chest tight": "chest_pain",
    "short of breath": "breathing", "breathless": "breathing", "can't breathe": "breathing",
    "dizzy": "fainting", "faint": "fainting", "confused": "confusion",
}


def words_to_numbers(text: str) -> str:
    """'sixty two point five' -> '62.5', 'a hundred and eighteen' -> '118'. Leaves other words alone."""
    tokens = re.findall(r"[\w.'/]+|[^\w\s]", text.lower())
    out, i = [], 0

    def read_int(j):
        total, cur, used = 0, 0, False
        while j < len(tokens):
            t = tokens[j]
            if t in UNITS:
                cur += UNITS[t]
            elif t in TENS:
                cur += TENS[t]
            elif t == "hundred" and (used or cur):
                cur = max(cur, 1) * 100
            elif t == "hundred" and not used and j + 1 < len(tokens):
                cur = 100
            elif t == "and" and used and j + 1 < len(tokens) and (tokens[j + 1] in UNITS or tokens[j + 1] in TENS):
                pass
            elif t == "a" and j + 1 < len(tokens) and tokens[j + 1] == "hundred":
                pass
            else:
                break
            used = True
            j += 1
        return (total + cur if used else None), j

    while i < len(tokens):
        n, j = read_int(i)
        if n is None:
            out.append(tokens[i])
            i += 1
            continue
        if j + 1 < len(tokens) and tokens[j] == "point" and tokens[j + 1] in UNITS:
            digits = []
            j += 1
            while j < len(tokens) and tokens[j] in UNITS and UNITS[tokens[j]] < 10:
                digits.append(str(UNITS[tokens[j]]))
                j += 1
            out.append(f"{n}.{''.join(digits)}")
        else:
            out.append(str(n))
        i = j
    return " ".join(out)


def parse(text: str) -> dict:
    norm = words_to_numbers(text)
    norm = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", norm)  # "36 . 8" from tokenising
    values: dict[str, float] = {}
    spans = []
    for key, pat in PATTERNS:
        m = re.search(pat, norm)
        if not m:
            continue
        spans.append(m.span())
        if key == "bp":
            values["systolic_bp"], values["diastolic_bp"] = float(m.group(1)), float(m.group(2))
        elif key == "sleep_hours":
            values[key] = float(m.group(1)) + (0.5 if m.group(2) else 0)
        else:
            values[key] = float(m.group(1))
    if "body_temp" in values and values["body_temp"] < 30 and "body_temp" not in text:
        values.pop("body_temp")
    low = text.lower()
    found = []
    for phrase, key in SYMPTOM_WORDS.items():
        if phrase in low and key not in found:
            found.append(key)
    return {
        "text": text,
        "normalised": norm,
        "values": values,
        "symptoms": [{"key": k, "name": CATALOG[k].name, "red_flag": CATALOG[k].red_flag} for k in found],
        "understood": bool(values or found),
    }
