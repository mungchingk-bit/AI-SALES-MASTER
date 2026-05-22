import json
import os

import config
from models.training_session import TrainingSession


class SessionStore:
    def __init__(self):
        self.sessions_dir = config.SESSIONS_DIR

    def save(self, session: TrainingSession) -> str:
        path = os.path.join(self.sessions_dir, f"{session.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        return session.id

    def load(self, session_id: str) -> TrainingSession | None:
        path = os.path.join(self.sessions_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TrainingSession.from_dict(data)

    def list_all(self) -> list[TrainingSession]:
        sessions = []
        if not os.path.exists(self.sessions_dir):
            return sessions
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.sessions_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(TrainingSession.from_dict(data))
        return sorted(sessions, key=lambda s: s.started_at, reverse=True)

    def delete(self, session_id: str) -> bool:
        path = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
