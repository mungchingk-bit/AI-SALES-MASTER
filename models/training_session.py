from dataclasses import dataclass, field
from datetime import datetime
import uuid

from models.chat_message import ChatMessage


@dataclass
class TrainingSession:
    mode: str  # "customer" | "salesperson"
    scenario: dict = field(default_factory=dict)
    style_profile_id: str | None = None
    conversation: list = field(default_factory=list)
    phases: list = field(default_factory=list)
    receptivity_history: list = field(default_factory=list)
    status: str = "active"  # "active" | "completed" | "abandoned"
    user: str = ""  # 销售姓名，用于多用户隔离
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str | None = None
    evaluation_id: str | None = None

    def add_message(self, role: str, content: str, metadata: dict | None = None):
        msg = ChatMessage(role=role, content=content, metadata=metadata)
        self.conversation.append(msg)

    def get_api_messages(self) -> list[dict]:
        return [msg.to_api_message() for msg in self.conversation]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "scenario": self.scenario,
            "style_profile_id": self.style_profile_id,
            "conversation": [msg.to_dict() for msg in self.conversation],
            "phases": self.phases,
            "receptivity_history": self.receptivity_history,
            "status": self.status,
            "user": self.user,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "evaluation_id": self.evaluation_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingSession":
        session = cls(
            id=data.get("id", str(uuid.uuid4())),
            mode=data["mode"],
            scenario=data.get("scenario", {}),
            style_profile_id=data.get("style_profile_id"),
            phases=data.get("phases", []),
            receptivity_history=data.get("receptivity_history", []),
            status=data.get("status", "active"),
            user=data.get("user", ""),
            started_at=data.get("started_at", datetime.now().isoformat()),
            ended_at=data.get("ended_at"),
            evaluation_id=data.get("evaluation_id"),
        )
        session.conversation = [
            ChatMessage.from_dict(msg) for msg in data.get("conversation", [])
        ]
        return session
