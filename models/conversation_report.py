from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class ConversationReport:
    sales_name: str
    source_file: str
    source_title: str
    highlights: list = field(default_factory=list)
    improvements: list = field(default_factory=list)
    corrected_scripts: list = field(default_factory=list)
    next_steps: list = field(default_factory=list)
    summary: str = ""
    uploader_name: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    chat_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sales_name": self.sales_name,
            "source_file": self.source_file,
            "source_title": self.source_title,
            "highlights": self.highlights,
            "improvements": self.improvements,
            "corrected_scripts": self.corrected_scripts,
            "next_steps": self.next_steps,
            "summary": self.summary,
            "uploader_name": self.uploader_name,
            "created_at": self.created_at,
            "chat_history": self.chat_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationReport":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sales_name=data.get("sales_name", ""),
            source_file=data.get("source_file", ""),
            source_title=data.get("source_title", ""),
            highlights=data.get("highlights", []),
            improvements=data.get("improvements", []),
            corrected_scripts=data.get("corrected_scripts", []),
            next_steps=data.get("next_steps", []),
            summary=data.get("summary", ""),
            uploader_name=data.get("uploader_name", data.get("sales_name", "")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            chat_history=data.get("chat_history", []),
        )
