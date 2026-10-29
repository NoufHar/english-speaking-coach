
import json

import pytest

from agent.harness import AgentHarness, SessionState
from app.realtime import RealtimeCoach


def test_usage_accumulates_and_budget_blocks():
    harness = AgentHarness({}, max_usd=0.01)
    state = SessionState("demo")

    total = harness.record_usage(
        state,
        {"input_tokens": 100, "output_tokens": 100},
        32,
        64,
    )
    assert total == pytest.approx(0.0096)

    harness.check_budget(state)

    harness.record_usage(
        state,
        {"input_tokens": 10, "output_tokens": 10},
        32,
        64,
    )

    with pytest.raises(RuntimeError, match="cost budget"):
        harness.check_budget(state)


def test_missing_usage_fails_closed():
    harness = AgentHarness({})

    with pytest.raises(ValueError, match="missing"):
        harness.record_usage(
            SessionState("demo"), None, 32, 64
        )


def test_invalid_usage_fails_closed():
    harness = AgentHarness({})

    with pytest.raises(ValueError):
        harness.record_usage(
            SessionState("demo"),
            {"input_tokens": -1, "output_tokens": 1},
            32,
            64,
        )


class FakeBrowser:
    def __init__(self):
        self.messages = []

    async def send_json(self, payload):
        self.messages.append(payload)


class FakeUpstream:
    def __init__(self, messages):
        self.messages = messages

    def __aiter__(self):
        self.iterator = iter(self.messages)
        return self

    async def __anext__(self):
        try:
            return json.dumps(next(self.iterator))
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.asyncio
async def test_realtime_stops_at_cost_limit():
    coach = object.__new__(RealtimeCoach)
    coach.state = SessionState("demo")
    coach.harness = AgentHarness({}, max_usd=0.001)
    coach.input_rate = 32
    coach.output_rate = 64
    coach.cost_exhausted = False
    coach.started = coach.state.started_at

    browser = FakeBrowser()
    upstream = FakeUpstream([
        {
            "type": "response.done",
            "response": {
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 100,
                }
            },
        }
    ])

    await coach.handle_openai_messages(
        upstream, browser
    )

    assert coach.cost_exhausted
    assert any(
        "budget reached" in message.get("message", "")
        for message in browser.messages
    )
