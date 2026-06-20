import json
import os
from datetime import datetime

import config
from models.weekly_review import WeeklyReview


class WeeklyReviewStore:
    def __init__(self):
        self.dir = config.WEEKLY_REVIEW_DIR
        os.makedirs(self.dir, exist_ok=True)

    def save(self, review: WeeklyReview):
        path = os.path.join(self.dir, f"{review.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(review.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self, review_id: str) -> WeeklyReview | None:
        path = os.path.join(self.dir, f"{review_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return WeeklyReview.from_dict(json.load(f))

    def list_all(self) -> list[WeeklyReview]:
        reviews = []
        for fname in os.listdir(self.dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    reviews.append(WeeklyReview.from_dict(json.load(f)))
            except Exception:
                continue
        reviews.sort(key=lambda r: r.created_at, reverse=True)
        return reviews

    def list_by_user(self, user: str) -> list[WeeklyReview]:
        if not user:
            return self.list_all()
        return [r for r in self.list_all() if r.user == user]

    def latest_by_user(self, user: str) -> WeeklyReview | None:
        if not user:
            return None
        reviews = self.list_by_user(user)
        return reviews[0] if reviews else None

    def build_growth_context(self, user: str, max_chars: int = 1600) -> str:
        """Return compact lessons from the latest review for future training."""
        if not user:
            return ""
        review = self.latest_by_user(user)
        if not review:
            return ""

        lines = [f"最近成长复盘（{review.week_start} 至 {review.week_end}）："]
        if review.strengths:
            lines.append("继续保持：" + "；".join(review.strengths[:3]))
        if review.suggestions:
            lines.append("重点改进：" + "；".join(review.suggestions[:4]))
        if review.focus_areas:
            lines.append("近期训练重点：" + "；".join(review.focus_areas[:3]))
        return "\n".join(lines)[:max_chars]
