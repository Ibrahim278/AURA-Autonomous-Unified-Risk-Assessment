import json

import pytest
from fastapi.testclient import TestClient

from aura import ai, assistant, main
from aura.simulator import generate

from .test_ai import _fake_anthropic

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    main.store.load(generate())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", "/nonexistent-aura-test")


def ask(q, **kw):
    return client.post("/api/assistant", json={"question": q, **kw}).json()


def test_offline_app_help():
    r = ask("How do I upload my own CSV?")
    assert r["mode"] == "offline" and r["reply"]["topic"] == "app_help"
    assert r["reply"]["actions"][0]["type"] == "open_import"


def test_offline_health_escalates_for_critical_crew():
    r = ask("How am I doing?", crew_id="aura-3")["reply"]
    assert r["escalate"] is True and r["topic"] == "health"
    assert r["actions"][0] == {"type": "open_indicator", "label": "Open Body temperature", "target": "body_temp"}


def test_unknown_crew_is_ignored():
    r = ask("hello", crew_id="nobody")["reply"]
    assert r["topic"] == "app_help"


def test_context_is_compact():
    ctx = assistant.build_assistant_context(main.store, "aura-2", None, "sleep_hours")
    assert ctx["viewing"]["selected_indicator"] == "sleep_hours"
    assert len(json.dumps(ctx)) < 20000


def test_ai_reply_actions_are_validated(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    captured = []
    reply = json.dumps({"answer": "Sleep is your main issue.", "steps": ["Dim lights", "a", "b", "c", "d"],
                        "actions": [{"type": "open_indicator", "label": "Sleep", "target": "sleep_hours"},
                                    {"type": "open_indicator", "label": "Bogus", "target": "made_up"},
                                    {"type": "select_crew", "label": "Amara", "target": "aura-3"},
                                    {"type": "open_checkin", "label": "Log", "target": "x"}],
                        "escalate": False, "topic": "health"})
    monkeypatch.setattr(assistant, "_client", lambda: _fake_anthropic(captured, reply))
    r = ask("What should I fix?", crew_id="aura-2")
    assert r["mode"] == "ai"
    acts = r["reply"]["actions"]
    assert [a["target"] for a in acts] == ["sleep_hours", "aura-3", None]
    assert len(r["reply"]["steps"]) == 4
    body = captured[0]
    assert "aura_context" in body["messages"][-1]["content"]
    assert body["output_config"]["effort"] == "low"
