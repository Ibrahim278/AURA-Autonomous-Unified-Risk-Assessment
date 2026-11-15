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


def test_memory_api_and_context():
    from aura import main as m
    from fastapi.testclient import TestClient as TC
    c = TC(m.app)
    m.store.memory.clear()
    n = c.post("/api/memory", json={"text": "I prefer metric units", "crew_id": "aura-2"}).json()
    c.post("/api/memory", json={"text": "Team call every Friday"})
    assert c.post("/api/memory", json={"text": "x", "crew_id": "nobody"}).status_code == 422
    assert [x["text"] for x in c.get("/api/memory?crew_id=aura-2").json()] == ["I prefer metric units", "Team call every Friday"]
    assert [x["text"] for x in c.get("/api/memory?crew_id=aura-1").json()] == ["Team call every Friday"]
    ctx = assistant.build_assistant_context(m.store, "aura-2", None, None)
    assert "I prefer metric units" in ctx["memory"]
    assert c.delete(f"/api/memory/{n['id']}").status_code == 200
    assert c.delete(f"/api/memory/{n['id']}").status_code == 404
    m.store.memory.clear()


def test_offline_remember_and_new_action_validation():
    from aura import main as m
    r = assistant.offline_reply("Remember that I get headaches after EVA", {"person": None})
    assert r.actions[0].type == "remember" and r.actions[0].target == "I get headaches after EVA"
    ctx = assistant.build_assistant_context(m.store, "aura-2", None, None)
    reply = assistant.AssistantReply(answer="x", steps=[], escalate=False, topic="app_help", actions=[
        assistant.AssistantAction(type="go_to_day", label="Day 48", target="48"),
        assistant.AssistantAction(type="go_to_day", label="Bad", target="999"),
        assistant.AssistantAction(type="log_symptom", label="Log", target="headache"),
        assistant.AssistantAction(type="log_symptom", label="Bad", target="sneezing"),
        assistant.AssistantAction(type="draft_ground_message", label="Draft", target="Sleeping badly, advice?"),
    ])
    kept = assistant._clean(reply, ctx).actions
    assert [(a.type, a.target) for a in kept] == [("go_to_day", "48"), ("log_symptom", "headache"),
                                                  ("draft_ground_message", "Sleeping badly, advice?")]


def test_open_page_navigation_offline_and_validation():
    from aura.assistant import AssistantAction, AssistantReply, _clean, build_assistant_context, offline_reply
    from aura.main import store
    ctx = build_assistant_context(store, "aura-2", None, None)
    for q, page in [("take me to radiation", "radiation"), ("go to the team page", "team"),
                    ("open the daily plan", "plan"), ("show me real NASA data", "research"), ("go home", "home")]:
        r = offline_reply(q, ctx)
        assert [(a.type, a.target) for a in r.actions] == [("open_page", page)], q
    bad = AssistantReply(answer="x", steps=[], escalate=False, topic="app_help",
                         actions=[AssistantAction(type="open_page", label="Nope", target="settings"),
                                  AssistantAction(type="open_page", label="Plan", target="plan")])
    assert [a.target for a in _clean(bad, ctx).actions] == ["plan"]


@pytest.mark.parametrize("q,page", [
    ("Take me to Ground View", "ground"),
    ("go to the radiation budget", "radiation"),
    ("open the console", "console"),
    ("switch to team", "team"),
    ("show me the real NASA data", "research"),
])
def test_navigation_requests_run_automatically(q, page):
    r = ask(q)
    a = r["reply"]["actions"][r["auto_action"]]
    assert a["type"] == "open_page" and a["target"] == page


def test_other_questions_keep_buttons():
    r = ask("How do I import my own data?")
    assert r["reply"]["actions"] and r["auto_action"] is None
    # data-changing actions never auto-run, even with a "go" verb
    reply = assistant.AssistantReply(answer="x", steps=[], escalate=False, topic="app_help",
                                     actions=[assistant.AssistantAction(type="remember", label="Save", target="note")])
    assert assistant.auto_action("open my notes and remember this", reply) is None
