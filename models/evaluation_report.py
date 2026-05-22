from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class EvaluationReport:
    session_id: str
    dimension_scores: dict = field(default_factory=dict)
    overall_score: float = 0.0
    strengths: list = field(default_factory=list)
    improvements: list = field(default_factory=list)
    style_alignment: dict | None = None
    specific_examples: list = field(default_factory=list)
    recommendation: str = ""
    # 实战总结：对话复盘 + 问题诊断 + 校正建议 + 签单路径
    conversation_summary: str = ""
    deal_progression: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "dimension_scores": self.dimension_scores,
            "overall_score": self.overall_score,
            "strengths": self.strengths,
            "improvements": self.improvements,
            "style_alignment": self.style_alignment,
            "specific_examples": self.specific_examples,
            "recommendation": self.recommendation,
            "conversation_summary": self.conversation_summary,
            "deal_progression": self.deal_progression,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationReport":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            session_id=data["session_id"],
            dimension_scores=data.get("dimension_scores", {}),
            overall_score=data.get("overall_score", 0.0),
            strengths=data.get("strengths", []),
            improvements=data.get("improvements", []),
            style_alignment=data.get("style_alignment"),
            specific_examples=data.get("specific_examples", []),
            recommendation=data.get("recommendation", ""),
            conversation_summary=data.get("conversation_summary", ""),
            deal_progression=data.get("deal_progression", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
