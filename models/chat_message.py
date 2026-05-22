from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict | None = None

    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content, "timestamp": self.timestamp}
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata"),
        )

    def to_api_message(self) -> dict:
        return {"role": self.role, "content": self.content}
