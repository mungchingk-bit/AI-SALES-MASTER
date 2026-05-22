from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class StyleProfile:
    name: str
    description: str
    source_file: str
    extracted_traits: dict = field(default_factory=dict)
    confidence_scores: dict = field(default_factory=dict)
    sample_dialogues: list = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source_file": self.source_file,
            "extracted_traits": self.extracted_traits,
            "confidence_scores": self.confidence_scores,
            "sample_dialogues": self.sample_dialogues,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StyleProfile":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            description=data["description"],
            source_file=data.get("source_file", ""),
            extracted_traits=data.get("extracted_traits", {}),
            confidence_scores=data.get("confidence_scores", {}),
            sample_dialogues=data.get("sample_dialogues", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )
