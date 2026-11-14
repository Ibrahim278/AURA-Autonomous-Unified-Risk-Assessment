import json

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from aura import ai, main
from aura.simulator import generate

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    main.store.load(generate())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


def test_status_disabled_without_key():
    assert client.get("/api/ai/status").json()["enabled"] is False


def test_offline_briefing_critical_escalates():
    r = client.post("/api/crew/aura-3/briefing").json()
    assert r["mode"] == "offline"
    b = r["briefing"]
    assert b["escalate"] is True
    assert b["priorities"][0]["indicators"] == ["body_temp"]


def test_offline_briefing_normal():
    b = client.post("/api/crew/aura-1/briefing").json()["briefing"]
    assert b["escalate"] is False and b["priorities"] == []


def test_offline_ask():
    r = client.post("/api/crew/aura-3/ask", json={"question": "Am I ok?"}).json()
    assert r["mode"] == "offline" and "flight surgeon" in r["answer"]


def test_context_is_compact_and_grounded():
    ctx = ai.build_context(main.store, "aura-2")
    assert ctx["overall_level"] == "warning"
    assert len(ctx["indicators"]) == 10
    assert all(len(i["recent"]) <= 7 for i in ctx["indicators"])
    assert len(json.dumps(ctx)) < 20000


def _fake_anthropic(captured, reply_text, stop_reason="end_turn"):
    import anthropic

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": reply_text}],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    return anthropic.Anthropic(api_key="test", base_url="https://api.test",
                               http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_ai_briefing_request_shape_and_escalation_guard(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    captured = []
    # Model claims no escalation; the rule engine says critical, so AURA must force it.
    reply = json.dumps({"headline": "Fever building.", "escalate": False,
                        "priorities": [{"title": "Fever", "detail": "39 C", "action": "Rest",
                                        "indicators": ["body_temp"]}],
                        "patterns": ["Fever with raised HR"], "encouragement": "You've got this."})
    monkeypatch.setattr(ai, "_client", lambda: _fake_anthropic(captured, reply))
    r = client.post("/api/crew/aura-3/briefing").json()
    assert r["mode"] == "ai"
    assert r["briefing"]["escalate"] is True
    body = captured[0]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "astronaut_data" in body["messages"][0]["content"]


def test_ai_ask_uses_history(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    captured = []
    monkeypatch.setattr(ai, "_client", lambda: _fake_anthropic(captured, "Sleep is the driver."))
    r = client.post("/api/crew/aura-2/ask", json={
        "question": "Why is my heart rate up?",
        "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    }).json()
    assert r == {"mode": "ai", "model": "claude-opus-5-5", "answer": "Sleep is the driver."}
    msgs = captured[0]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert captured[0]["output_config"] == {"effort": "low"}


def test_ai_refusal_handled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(ai, "_client", lambda: _fake_anthropic([], "", stop_reason="refusal"))
    r = client.post("/api/crew/aura-2/ask", json={"question": "x"}).json()
    assert "flight surgeon" in r["answer"]


def test_ai_failure_falls_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    def boom():
        raise ConnectionError("no network")

    monkeypatch.setattr(ai, "_client", boom)
    r = client.post("/api/crew/aura-3/briefing").json()
    assert r["mode"] == "offline" and r["briefing"]["escalate"] is True
