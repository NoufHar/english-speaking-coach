import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

def now():
    return datetime.now(timezone.utc).isoformat()


class LearnerDatabase:
    def __init__(self, path="coach.db"):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS learners (
                    learner_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL DEFAULT 'unknown',
                    goal TEXT NOT NULL,
                    learning_plan TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    feedback TEXT NOT NULL,
                    scores TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(learner_id) REFERENCES learners(learner_id)
                );
            """)


    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def create_learner(self, learner_id, name, goal):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO learners (learner_id,name,goal,created_at) VALUES (?,?,?,?)", (learner_id, name, goal, now()))
        return self.get_learner(learner_id)

    def get_learner(self, learner_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM learners WHERE learner_id=?", (learner_id,)).fetchone()
        return dict(row) if row else None

    def recent_sessions(self, learner_id, limit=3):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sessions WHERE learner_id=? ORDER BY id DESC LIMIT ?", (learner_id, min(max(int(limit), 1), 5))).fetchall()
        return [{**dict(row), "scores": json.loads(row["scores"])} for row in rows]

    def save_feedback(self, learner_id, mode, feedback, scores):
        with self.connect() as db:
            cursor = db.execute("INSERT INTO sessions (learner_id,mode,feedback,scores,created_at) VALUES (?,?,?,?,?)", (learner_id, mode, feedback, json.dumps(scores), now()))
            return cursor.lastrowid

    def update_plan(self, learner_id, plan):
        with self.connect() as db:
            return db.execute("UPDATE learners SET learning_plan=? WHERE learner_id=?", (plan, learner_id)).rowcount == 1
