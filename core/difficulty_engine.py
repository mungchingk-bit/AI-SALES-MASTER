from storage.evaluation_store import EvaluationStore
from storage.session_store import SessionStore

import config


class DifficultyEngine:
    def __init__(self):
        self.evaluation_store = EvaluationStore()
        self.session_store = SessionStore()

    def recommend(self, user: str) -> str:
        """根据用户历史评估分数推荐下次训练难度。"""
        threshold_easy = getattr(config, "DIFFICULTY_THRESHOLD_EASY", 5.0)
        threshold_hard = getattr(config, "DIFFICULTY_THRESHOLD_HARD", 7.0)
        lookback = getattr(config, "DIFFICULTY_LOOKBACK", 5)

        avg_score = self._get_user_avg_score(user, lookback)
        if avg_score is None:
            return "medium"

        if avg_score < threshold_easy:
            return "easy"
        elif avg_score >= threshold_hard:
            return "hard"
        else:
            return "medium"

    def _get_user_avg_score(self, user: str, lookback: int) -> float | None:
        """获取用户最近N次评估的平均分数。"""
        user_session_ids = set()
        for s in self.session_store.list_all():
            if s.user == user:
                user_session_ids.add(s.id)

        user_reports = []
        for r in self.evaluation_store.list_all():
            if r.session_id in user_session_ids:
                user_reports.append(r)

        if not user_reports:
            return None

        user_reports.sort(key=lambda r: r.created_at, reverse=True)
        recent = user_reports[:lookback]
        return sum(r.overall_score for r in recent) / len(recent)
