from mcp_client.fetch_client import FetchMCPClient


class CoachTools:
    def __init__(self, database, fetch_client=None):
        self.database = database
        self.fetch_client = fetch_client or FetchMCPClient()

    async def get_learner_profile(self, learner_id):
        return self.database.get_learner(learner_id)

    async def get_recent_sessions(self, learner_id):
        return self.database.recent_sessions(learner_id)

    async def search_learning_resources(self, resource):
        return await self.fetch_client.fetch(resource)

    async def save_session_feedback(self, learner_id, mode, feedback, scores):
        session_id = self.database.save_feedback(learner_id, mode, feedback, scores)
        return {"saved": True, "session_id": session_id}

    async def update_learning_plan(self, learner_id, plan):
        return {"updated": self.database.update_plan(learner_id, plan)}

    def registry(self):
        return {name: getattr(self, name) for name in ("get_learner_profile", "get_recent_sessions", "search_learning_resources", "save_session_feedback", "update_learning_plan")}
