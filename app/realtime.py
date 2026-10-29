
import asyncio
import json
import logging
import os
import time
from urllib.parse import quote

import websockets
from fastapi import WebSocketDisconnect

from agent.coach import TOOLS, build_instructions
from agent.harness import AgentHarness, SessionState
from agent.tools import CoachTools
from memory.database import LearnerDatabase


logger = logging.getLogger(__name__)


class RealtimeCoach:
    def __init__(self, learner_id):
        self.database = LearnerDatabase(
            os.getenv("DATABASE_PATH", "coach.db")
        )

        self.profile = self.database.get_learner(learner_id)

        if self.profile is None:
            raise ValueError(
                "Create learner before starting a voice session"
            )

        self.state = SessionState(learner_id)

        self.harness = AgentHarness(
            CoachTools(self.database).registry(),
            max_calls=int(os.getenv("MAX_TOOL_CALLS", "12")),
            max_seconds=int(os.getenv("MAX_SESSION_SECONDS", "900")),
            max_usd=float(os.getenv("MAX_ESTIMATED_USD", "1.5")),
        )

        self.pending_calls = {}
        self.outgoing_lock = asyncio.Lock()
        self.started = time.monotonic()
        self.seen_calls = set()

        self.input_rate = float(
            os.getenv("REALTIME_INPUT_USD_PER_1M", "32")
        )
        self.output_rate = float(
            os.getenv("REALTIME_OUTPUT_USD_PER_1M", "64")
        )

        self.cost_exhausted = False

    async def send_openai(self, upstream, payload):
        async with self.outgoing_lock:
            await upstream.send(json.dumps(payload))

    async def tool_output(
        self,
        upstream,
        call_id,
        result,
        create_response=True,
    ):
        await self.send_openai(
            upstream,
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                },
            },
        )

        if create_response and not self.cost_exhausted:
            await self.send_openai(
                upstream,
                {"type": "response.create"},
            )

    async def handle_call(
        self,
        event,
        upstream,
        browser,
        create_response=True,
    ):
        if self.cost_exhausted:
            return False

        call_id = event.get("call_id")

        if not call_id or call_id in self.seen_calls:
            return False

        self.seen_calls.add(call_id)

        try:
            args = json.loads(
                event.get("arguments") or "{}"
            )

            result = await self.harness.execute(
                self.state,
                event.get("name", ""),
                args,
            )

        except Exception as exc:
            logger.exception("Tool execution failed")

            result = {
                "status": "error",
                "error": str(exc)[:200],
            }

        if result.get("status") == "approval_required":
            approval_id = result["approval_id"]

            self.pending_calls[approval_id] = call_id

            await browser.send_json(
                {
                    "type": "approval_required",
                    "approval_id": approval_id,
                    "proposal": result["proposal"],
                }
            )

            return False

        await self.tool_output(
            upstream,
            call_id,
            result,
            create_response=create_response,
        )

        return True

    async def initialize_session(
        self,
        upstream,
        browser,
        instructions,
    ):
        await self.send_openai(
            upstream,
            {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "instructions": instructions,
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {
                                "type": "audio/pcm",
                                "rate": 24000,
                            },
                            "turn_detection": {
                                "type": "server_vad",
                                "create_response": True,
                                "interrupt_response": True,
                            },
                            "transcription": {
                                "model": "gpt-4o-mini-transcribe",
                            },
                        },
                        "output": {
                            "format": {
                                "type": "audio/pcm",
                                "rate": 24000,
                            },
                            "voice": "alloy",
                        },
                    },
                    "tools": TOOLS,
                    "tool_choice": "auto",
                },
            },
        )

        while True:
            raw = await asyncio.wait_for(
                upstream.recv(),
                timeout=15,
            )

            event = json.loads(raw)
            kind = event.get("type", "")

            if kind == "session.updated":
                logger.info(
                    "OpenAI Realtime session initialized"
                )

                await browser.send_json(
                    {"type": "ready"}
                )

                return

            if kind == "error":
                error = event.get("error", {})

                message = error.get(
                    "message",
                    "Realtime session initialization failed",
                )

                logger.error(
                    "Realtime initialization error: %s",
                    message,
                )

                raise RuntimeError(message)

    async def handle_browser_messages(
        self,
        browser,
        upstream,
    ):
        while True:
            message = await browser.receive_json()
            kind = message.get("type")

            if kind == "stop":
                logger.info(
                    "Voice session stopped by user"
                )
                return

            if self.cost_exhausted:
                continue

            if kind == "audio":
                audio = message.get("audio")

                if isinstance(audio, str) and audio:
                    await self.send_openai(
                        upstream,
                        {
                            "type": "input_audio_buffer.append",
                            "audio": audio,
                        },
                    )

            elif kind == "consent":
                self.state.storage_consent = (
                    message.get("approved") is True
                )

            elif kind == "approval":
                approval_id = message.get("approval_id")

                call_id = self.pending_calls.pop(
                    approval_id,
                    None,
                )

                if call_id:
                    try:
                        result = await self.harness.approve(
                            self.state,
                            approval_id,
                            message.get("approved") is True,
                        )

                    except Exception as exc:
                        logger.exception(
                            "Approval processing failed"
                        )

                        result = {
                            "status": "error",
                            "error": str(exc)[:200],
                        }

                    await self.tool_output(
                        upstream,
                        call_id,
                        result,
                    )

    async def handle_openai_messages(
        self,
        upstream,
        browser,
    ):
        async for raw in upstream:
            event = json.loads(raw)
            kind = event.get("type", "")

            if (
                time.monotonic() - self.started
                > self.harness.max_seconds
            ):
                await browser.send_json(
                    {
                        "type": "error",
                        "message": "Session time limit reached",
                    }
                )
                return

            if self.cost_exhausted:
                return

            if kind in (
                "response.output_audio.delta",
                "response.audio.delta",
            ):
                await browser.send_json(
                    {
                        "type": "audio",
                        "audio": event.get("delta", ""),
                    }
                )

            elif kind in (
                "response.output_audio_transcript.delta",
                "response.audio_transcript.delta",
            ):
                await browser.send_json(
                    {
                        "type": "coach_text_delta",
                        "text": event.get("delta", ""),
                    }
                )

            elif (
                kind
                == "conversation.item.input_audio_transcription.completed"
            ):
                await browser.send_json(
                    {
                        "type": "learner_text",
                        "text": event.get("transcript", ""),
                    }
                )

            elif kind == "input_audio_buffer.speech_started":
                await browser.send_json(
                    {"type": "interrupt"}
                )

            elif kind == "response.function_call_arguments.done":
                # Do not execute the tool yet.
                # First wait for response.done so that
                # usage is charged before tool execution.
                continue

            elif kind == "response.done":
                response = event.get("response", {})
                usage = response.get("usage")

                try:
                    total = self.harness.record_usage(
                        self.state,
                        usage,
                        self.input_rate,
                        self.output_rate,
                    )

                except ValueError as exc:
                    self.cost_exhausted = True

                    await browser.send_json(
                        {
                            "type": "error",
                            "message": (
                                "Cost accounting unavailable: "
                                f"{exc}. Session stopped."
                            ),
                        }
                    )
                    return

                await browser.send_json(
                    {
                        "type": "usage",
                        "usage": usage,
                        "estimated_usd": round(total, 6),
                        "max_estimated_usd": self.harness.max_usd,
                    }
                )

                if total >= self.harness.max_usd:
                    self.cost_exhausted = True

                    await browser.send_json(
                        {
                            "type": "error",
                            "message": (
                                "Estimated session cost budget reached. "
                                "Session stopped."
                            ),
                        }
                    )
                    return

                # All tool calls are handled only after
                # the response cost has been recorded.
                completed = False

                for item in response.get("output", []):
                    if item.get("type") == "function_call":
                        sent = await self.handle_call(
                            item,
                            upstream,
                            browser,
                            create_response=False,
                        )
                        completed = completed or sent

                # Request only one follow-up response,
                # even when multiple tools are called.
                if (
                    completed
                    and not self.pending_calls
                    and not self.cost_exhausted
                ):
                    await self.send_openai(
                        upstream,
                        {"type": "response.create"},
                    )

            elif kind == "error":
                error = event.get("error", {})

                message = error.get(
                    "message",
                    "Realtime API error",
                )

                logger.error(
                    "OpenAI Realtime error: %s",
                    message,
                )

                await browser.send_json(
                    {
                        "type": "error",
                        "message": message,
                    }
                )

    async def run(self, browser):
        model = os.getenv(
            "OPENAI_REALTIME_MODEL",
            "gpt-realtime",
        )

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing from .env"
            )

        url = (
            "wss://api.openai.com/v1/realtime?model="
            + quote(model)
        )

        history = self.database.recent_sessions(
            self.state.learner_id
        )

        instructions = build_instructions(
            self.profile,
            history,
            int(
                os.getenv(
                    "MAX_CONTEXT_CHARS",
                    "10000",
                )
            ),
        )

        logger.info(
            "Connecting to OpenAI Realtime model: %s",
            model,
        )

        try:
            async with websockets.connect(
                url,
                additional_headers={
                    "Authorization": f"Bearer {api_key}"
                },
                max_size=12_000_000,
                open_timeout=20,
                ping_interval=20,
                ping_timeout=20,
            ) as upstream:

                logger.info(
                    "Connected to OpenAI Realtime"
                )

                await self.initialize_session(
                    upstream,
                    browser,
                    instructions,
                )

                incoming = asyncio.create_task(
                    self.handle_browser_messages(
                        browser,
                        upstream,
                    )
                )

                outgoing = asyncio.create_task(
                    self.handle_openai_messages(
                        upstream,
                        browser,
                    )
                )

                tasks = [incoming, outgoing]

                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                await asyncio.gather(
                    *pending,
                    return_exceptions=True,
                )

                for task in done:
                    if task.cancelled():
                        continue

                    error = task.exception()

                    if error and not isinstance(
                        error,
                        WebSocketDisconnect,
                    ):
                        raise error

        except WebSocketDisconnect:
            logger.info(
                "Browser WebSocket disconnected"
            )

        except Exception as exc:
            logger.exception(
                "Realtime voice session failed"
            )

            try:
                await browser.send_json(
                    {
                        "type": "error",
                        "message": str(exc)[:500],
                    }
                )

            except Exception:
                pass

            raise
