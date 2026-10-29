import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.realtime import RealtimeCoach
from memory.database import LearnerDatabase

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="AI English Speaking Coach")
database = LearnerDatabase(os.getenv("DATABASE_PATH", "coach.db"))


class LearnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    goal: str = Field(default="Improve spoken English", max_length=300)


@app.get("/")
async def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/audio-worklet.js")
async def worklet():
    return FileResponse(ROOT / "static" / "audio-worklet.js", media_type="application/javascript")


@app.post("/learners")
async def create_learner(request: LearnerCreate):
    learner_id = uuid4().hex
    return database.create_learner(learner_id, request.name, request.goal)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/{learner_id}")
async def voice(websocket: WebSocket, learner_id: str):
    await websocket.accept()
    if not os.getenv("OPENAI_API_KEY"):
        await websocket.send_json({"type": "error", "message": "Set OPENAI_API_KEY in .env"})
        await websocket.close()
        return
    try:
        coach = RealtimeCoach(learner_id)
        await coach.run(websocket)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)[:300]})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
