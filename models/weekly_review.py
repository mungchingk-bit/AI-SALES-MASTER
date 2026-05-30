from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class WeeklyReview:
    user: str
    week_start: str
    week_end: str
    session_count: int = 0
    success_count: int = 0
    avg_overall_score: float = 0.0
    avg_dimension_scores: dict = field(default_factory=dict)
    score_trend: str = ""
    suggestions: list = field(default_factory=list)
    focus_areas: list = field(default_factory=list)
    summary: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "user": self.user,
            "week_start": self.week_start,
            "week_end": self.week_end,
            "session_count": self.session_count,
            "success_count": self.success_count,
            "avg_overall_score": self.avg_overall_score,
            "avg_dimension_scores": self.avg_dimension_scores,
            "score_trend": self.score_trend,
            "suggestions": self.suggestions,
            "focus_areas": self.focus_areas,
            "summary": self.summary,
            "id": self.id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            user=data.get("user", ""),
            week_start=data.get("week_start", ""),
            week_end=data.get("week_end", ""),
            session_count=data.get("session_count", 0),
            success_count=data.get("success_count", 0),
            avg_overall_score=data.get("avg_overall_score", 0.0),
            avg_dimension_scores=data.get("avg_dimension_scores", {}),
            score_trend=data.get("score_trend", ""),
            suggestions=data.get("suggestions", []),
            focus_areas=data.get("focus_areas", []),
            summary=data.get("summary", ""),
            id=data.get("id", str(uuid.uuid4())),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
