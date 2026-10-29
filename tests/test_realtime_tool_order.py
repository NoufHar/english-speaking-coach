import asyncio
import json

import pytest

from agent.harness import AgentHarness, SessionState
from app.realtime import RealtimeCoach


class FakeBrowser:
    def __init__(self):
        self.messages = []

    async def send_json(self, payload):
        self.messages.append(payload)


class FakeUpstream:
    def __init__(self, events):
        self.events = events
        self.sent = []

    def __aiter__(self):
        self.iterator = iter(self.events)
        return self

    async def __anext__(self):
        try:
            return json.dumps(next(self.iterator))
        except StopIteration:
            raise StopAsyncIteration

    async def send(self, payload):
        self.sent.append(json.loads(payload))


def make_coach(tools, max_usd=1.5):
    coach = object.__new__(RealtimeCoach)

    coach.state = SessionState("demo")

    coach.harness = AgentHarness(
        tools,
        max_usd=max_usd,
    )

    coach.input_rate = 32
    coach.output_rate = 64
    coach.cost_exhausted = False
    coach.started = coach.state.started_at
    coach.seen_calls = set()
    coach.pending_calls = {}
    coach.outgoing_lock = asyncio.Lock()

    return coach


def tool_event(call_id="call_1"):
    return {
        "type": "function_call",
        "name": "get_learner_profile",
        "call_id": call_id,
        "arguments": "{}",
    }


def done_event(
    calls,
    input_tokens=100,
    output_tokens=100,
):
    return {
        "type": "response.done",
        "response": {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "output": calls,
        },
    }


@pytest.mark.asyncio
async def test_tool_runs_only_after_cost_is_recorded():
    execution_costs = []

    async def read_profile(**kwargs):
        execution_costs.append(
            coach.state.estimated_usd
        )
        return {"status": "success"}

    coach = make_coach(
        {"get_learner_profile": read_profile}
    )

    upstream = FakeUpstream([
        {
            "type": "response.function_call_arguments.done",
            "name": "get_learner_profile",
            "call_id": "call_1",
            "arguments": "{}",
        },
        done_event([tool_event()]),
    ])

    browser = FakeBrowser()

    await coach.handle_openai_messages(
        upstream,
        browser,
    )

    assert len(execution_costs) == 1
    assert execution_costs[0] > 0
    assert coach.state.estimated_usd > 0

    outputs = [
        msg
        for msg in upstream.sent
        if msg.get("type") == "conversation.item.create"
    ]

    responses = [
        msg
        for msg in upstream.sent
        if msg.get("type") == "response.create"
    ]

    assert len(outputs) == 1
    assert len(responses) == 1


@pytest.mark.asyncio
async def test_budget_blocks_tool_before_execution():
    executions = []

    async def read_profile(**kwargs):
        executions.append(kwargs)
        return {"status": "success"}

    coach = make_coach(
        {"get_learner_profile": read_profile},
        max_usd=0.001,
    )

    upstream = FakeUpstream([
        {
            "type": "response.function_call_arguments.done",
            "name": "get_learner_profile",
            "call_id": "call_1",
            "arguments": "{}",
        },
        done_event([tool_event()]),
    ])

    browser = FakeBrowser()

    await coach.handle_openai_messages(
        upstream,
        browser,
    )

    assert coach.cost_exhausted is True
    assert executions == []
    assert upstream.sent == []


@pytest.mark.asyncio
async def test_multiple_tools_create_one_followup_response():
    executions = []

    async def read_profile(**kwargs):
        executions.append("profile")
        return {"status": "success"}

    async def recent_sessions(**kwargs):
        executions.append("sessions")
        return {"status": "success"}

    coach = make_coach({
        "get_learner_profile": read_profile,
        "get_recent_sessions": recent_sessions,
    })

    calls = [
        tool_event("call_1"),
        {
            "type": "function_call",
            "name": "get_recent_sessions",
            "call_id": "call_2",
            "arguments": "{}",
        },
    ]

    upstream = FakeUpstream([
        done_event(calls),
    ])

    browser = FakeBrowser()

    await coach.handle_openai_messages(
        upstream,
        browser,
    )

    assert executions == [
        "profile",
        "sessions",
    ]

    outputs = [
        msg
        for msg in upstream.sent
        if msg.get("type") == "conversation.item.create"
    ]

    responses = [
        msg
        for msg in upstream.sent
        if msg.get("type") == "response.create"
    ]

    assert len(outputs) == 2
    assert len(responses) == 1