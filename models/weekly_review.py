from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class WeeklyReview:
    user: str
    week_start: str
    week_end: str
    scope: str = "personal"  # "personal" | "team"
    session_count: int = 0
    face_to_face_count: int = 0
    sales_count: int = 0
    success_count: int = 0
    avg_overall_score: float = 0.0
    avg_dimension_scores: dict = field(default_factory=dict)
    score_trend: str = ""
    strengths: list = field(default_factory=list)
    individual_insights: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    focus_areas: list = field(default_factory=list)
    summary: str = ""
    data_signature: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "user": self.user,
            "week_start": self.week_start,
            "week_end": self.week_end,
            "scope": self.scope,
            "session_count": self.session_count,
            "face_to_face_count": self.face_to_face_count,
            "sales_count": self.sales_count,
            "success_count": self.success_count,
            "avg_overall_score": self.avg_overall_score,
            "avg_dimension_scores": self.avg_dimension_scores,
            "score_trend": self.score_trend,
            "strengths": self.strengths,
            "individual_insights": self.individual_insights,
            "suggestions": self.suggestions,
            "focus_areas": self.focus_areas,
            "summary": self.summary,
            "data_signature": self.data_signature,
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            user=data.get("user", ""),
            week_start=data.get("week_start", ""),
            week_end=data.get("week_end", ""),
            scope=data.get("scope", "personal"),
            session_count=data.get("session_count", 0),
            face_to_face_count=data.get("face_to_face_count", 0),
            sales_count=data.get("sales_count", 0),
            success_count=data.get("success_count", 0),
            avg_overall_score=data.get("avg_overall_score", 0.0),
            avg_dimension_scores=data.get("avg_dimension_scores", {}),
            score_trend=data.get("score_trend", ""),
            strengths=data.get("strengths", []),
            individual_insights=data.get("individual_insights", []),
            suggestions=data.get("suggestions", []),
            focus_areas=data.get("focus_areas", []),
            summary=data.get("summary", ""),
            data_signature=data.get("data_signature", ""),
            id=data.get("id", str(uuid.uuid4())),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", data.get("created_at", datetime.now().isoformat())),
        )
