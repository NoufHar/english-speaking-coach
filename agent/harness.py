
import asyncio
import json
import math
import secrets
import time
from dataclasses import dataclass, field


PERMISSIONS = {
    "get_learner_profile": "read",
    "get_recent_sessions": "read",
    "search_learning_resources": "read",
    "save_session_feedback": "consent_write",
    "update_learning_plan": "approval_write",
}


@dataclass
class SessionState:
    learner_id: str
    storage_consent: bool = False
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    estimated_usd: float = 0.0
    pending: dict = field(default_factory=dict)
    audit: list = field(default_factory=list)


class AgentHarness:
    def __init__(
        self,
        tools,
        max_calls=12,
        max_seconds=900,
        max_usd=1.5,
    ):
        self.tools = tools
        self.max_calls = max_calls
        self.max_seconds = max_seconds
        self.max_usd = max_usd

    def record_usage(
        self,
        state,
        usage,
        input_per_million,
        output_per_million,
    ):
        """Record estimated cost from Realtime token usage."""

        if not isinstance(usage, dict):
            raise ValueError("Realtime usage data missing")

        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")

        if (
            not isinstance(input_tokens, int)
            or isinstance(input_tokens, bool)
            or input_tokens < 0
        ):
            raise ValueError("Invalid input token usage")

        if (
            not isinstance(output_tokens, int)
            or isinstance(output_tokens, bool)
            or output_tokens < 0
        ):
            raise ValueError("Invalid output token usage")

        rates = (input_per_million, output_per_million)

        if any(
            not isinstance(rate, (int, float))
            or isinstance(rate, bool)
            or not math.isfinite(rate)
            or rate < 0
            for rate in rates
        ):
            raise ValueError("Invalid token pricing")

        amount = (
            input_tokens * input_per_million
            + output_tokens * output_per_million
        ) / 1_000_000

        state.estimated_usd += amount

        state.audit.append(
            {
                "event": "usage",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_usd_delta": round(amount, 8),
                "estimated_usd_total": round(
                    state.estimated_usd, 8
                ),
            }
        )

        return state.estimated_usd

    def check_budget(self, state):
        if (
            time.monotonic() - state.started_at
            >= self.max_seconds
        ):
            raise RuntimeError(
                "Session time budget exhausted"
            )

        if state.tool_calls >= self.max_calls:
            raise RuntimeError(
                "Tool budget exhausted"
            )

        if state.estimated_usd >= self.max_usd:
            raise RuntimeError(
                "Estimated cost budget exhausted"
            )

    def validate(self, state, name, args):
        if (
            name not in PERMISSIONS
            or name not in self.tools
        ):
            raise PermissionError(
                "Tool is not permitted"
            )

        if not isinstance(args, dict):
            raise ValueError(
                "Tool arguments must be an object"
            )

        allowed = {
            "get_learner_profile": set(),
            "get_recent_sessions": set(),
            "search_learning_resources": {"resource"},
            "save_session_feedback": {
                "mode",
                "feedback",
                "scores",
            },
            "update_learning_plan": {"plan"},
        }[name]

        if set(args) - allowed:
            raise ValueError(
                "Unexpected tool arguments"
            )

        if name == "search_learning_resources":
            if args.get("resource") not in {
                "grammar",
                "speaking",
                "vocabulary",
            }:
                raise PermissionError(
                    "Resource is not allowlisted"
                )

        if name == "save_session_feedback":
            if not state.storage_consent:
                raise PermissionError(
                    "Storage consent is required"
                )

            if not isinstance(
                args.get("scores"), dict
            ):
                raise ValueError(
                    "Scores must be an object"
                )

            if len(json.dumps(args)) > 6000:
                raise ValueError(
                    "Feedback too large"
                )

        if name == "update_learning_plan":
            if (
                not isinstance(
                    args.get("plan"), str
                )
                or len(args["plan"]) > 1500
            ):
                raise ValueError(
                    "Invalid learning plan"
                )

        if name in {
            "get_learner_profile",
            "get_recent_sessions",
            "save_session_feedback",
            "update_learning_plan",
        }:
            args = {
                **args,
                "learner_id": state.learner_id,
            }

        return args

    async def execute(self, state, name, args):
        self.check_budget(state)

        args = self.validate(
            state,
            name,
            args,
        )

        if PERMISSIONS[name] == "approval_write":
            approval_id = secrets.token_urlsafe(24)

            state.pending[approval_id] = {
                "name": name,
                "args": args,
                "created": time.monotonic(),
            }

            return {
                "status": "approval_required",
                "approval_id": approval_id,
                "tool": name,
                "proposal": args["plan"],
            }

        return await self._run(
            state,
            name,
            args,
        )

    async def approve(
        self,
        state,
        approval_id,
        accepted,
    ):
        request = state.pending.pop(
            approval_id,
            None,
        )

        if request is None:
            raise PermissionError(
                "Unknown or consumed approval"
            )

        if (
            time.monotonic() - request["created"]
            > 300
        ):
            raise PermissionError(
                "Approval expired"
            )

        if accepted is not True:
            return {
                "status": "rejected"
            }

        return await self._run(
            state,
            request["name"],
            request["args"],
        )

    async def _run(self, state, name, args):
        self.check_budget(state)

        state.tool_calls += 1
        started = time.monotonic()
        status = "error"

        try:
            result = await asyncio.wait_for(
                self.tools[name](**args),
                timeout=25,
            )

            status = "success"

            return {
                "status": status,
                "result": result,
            }

        except Exception as exc:
            return {
                "status": status,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{str(exc)[:200]}"
                ),
            }

        finally:
            state.audit.append(
                {
                    "tool": name,
                    "status": status,
                    "elapsed_seconds": round(
                        time.monotonic() - started,
                        3,
                    ),
                }
            )
