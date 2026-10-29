import pytest
from agent.harness import AgentHarness, SessionState
from agent.tools import CoachTools
from memory.database import LearnerDatabase


@pytest.fixture
def harness(tmp_path):
    db = LearnerDatabase(str(tmp_path / "test.db"))
    db.create_learner("a", "Demo", "Speaking")
    return AgentHarness(CoachTools(db).registry(), max_calls=3)


@pytest.mark.asyncio
async def test_unknown_tool(harness):
    with pytest.raises(PermissionError):
        await harness.execute(SessionState("a"), "delete_all", {})


@pytest.mark.asyncio
async def test_consent(harness):
    with pytest.raises(PermissionError):
        await harness.execute(SessionState("a"), "save_session_feedback", {"mode": "practice", "feedback": "Good", "scores": {}})


@pytest.mark.asyncio
async def test_approval(harness):
    state = SessionState("a")
    result = await harness.execute(state, "update_learning_plan", {"plan": "Daily interviews"})
    assert result["status"] == "approval_required"
    assert harness.tools["get_learner_profile"] is not None
    assert (await harness.approve(state, result["approval_id"], True))["result"]["updated"]
    with pytest.raises(PermissionError):
        await harness.approve(state, result["approval_id"], True)


@pytest.mark.asyncio
async def test_tool_budget(harness):
    state = SessionState("a")
    for _ in range(3):
        await harness.execute(state, "get_learner_profile", {})
    with pytest.raises(RuntimeError):
        await harness.execute(state, "get_learner_profile", {})


@pytest.mark.asyncio
async def test_cross_learner_access(harness):
    with pytest.raises(ValueError):
        await harness.execute(SessionState("a"), "get_learner_profile", {"learner_id": "other"})
