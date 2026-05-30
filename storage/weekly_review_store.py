import json
import os
from datetime import datetime

from models.weekly_review import WeeklyReview


class WeeklyReviewStore:
    def __init__(self):
        self.dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weekly_reviews")
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
            with open(path, encoding="utf-8") as f:
                reviews.append(WeeklyReview.from_dict(json.load(f)))
        reviews.sort(key=lambda r: r.created_at, reverse=True)
        return reviews

    def list_by_user(self, user: str) -> list[WeeklyReview]:
        return [r for r in self.list_all() if r.user == user]
