import json
import re
from datetime import datetime, timedelta

from core.llm_client import get_client
from models.weekly_review import WeeklyReview
from storage.evaluation_store import EvaluationStore
from storage.session_store import SessionStore
from storage.weekly_review_store import WeeklyReviewStore
from prompts.weekly_review import WEEKLY_REVIEW_PROMPT

import config


class WeeklyReviewer:
    def __init__(self):
        self.client = get_client()
        self.session_store = SessionStore()
        self.evaluation_store = EvaluationStore()
        self.review_store = WeeklyReviewStore()

    def generate(self, user: str) -> WeeklyReview | None:
        """生成用户本周的复盘报告。"""
        now = datetime.now()
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        week_end = now.strftime("%Y-%m-%d")

        # 检查是否已生成过本周报告
        existing = self.review_store.list_by_user(user)
        for r in existing:
            if r.week_start == week_start:
                return r

        # 获取本周数据
        sessions, reports = self._get_week_data(user, week_start)
        if not sessions:
            return None

        # 聚合统计
        stats = self._aggregate(sessions, reports)

        # LLM 生成复盘
        prompt = WEEKLY_REVIEW_PROMPT.format(
            session_count=stats["session_count"],
            success_count=stats["success_count"],
            avg_score=stats["avg_score"],
            score_trend=stats["score_trend"],
            dimension_scores=stats["dimension_scores_text"],
        )

        try:
            response = self.client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
                model=config.FAST_MODEL or None,
            )
            result = self._parse_json(response)
        except Exception:
            result = None

        review = WeeklyReview(
            user=user,
            week_start=week_start,
            week_end=week_end,
            session_count=stats["session_count"],
            success_count=stats["success_count"],
            avg_overall_score=stats["avg_score"],
            avg_dimension_scores=stats["dimension_scores"],
            score_trend=stats["score_trend"],
            suggestions=result.get("suggestions", []) if result else [],
            focus_areas=result.get("focus_areas", []) if result else [],
            summary=result.get("summary", "") if result else "",
        )
        self.review_store.save(review)
        return review

    def _get_week_data(self, user: str, week_start: str) -> tuple:
        """获取用户本周的会话和评估数据。"""
        user_sessions = [s for s in self.session_store.list_all() if s.user == user]
        week_sessions = [
            s for s in user_sessions
            if s.started_at and s.started_at[:10] >= week_start
        ]

        session_ids = {s.id for s in week_sessions}
        week_reports = [
            r for r in self.evaluation_store.list_all()
            if r.session_id in session_ids
        ]
        return week_sessions, week_reports

    def _aggregate(self, sessions, reports) -> dict:
        """聚合训练统计。"""
        session_count = len(sessions)
        success_count = sum(1 for s in sessions if s.end_reason == "成功")

        if reports:
            avg_score = round(sum(r.overall_score for r in reports) / len(reports), 1)
            # 维度平均分
            dim_sums = {}
            for r in reports:
                for dim, data in r.dimension_scores.items():
                    score = data.get("score", 0) if isinstance(data, dict) else data
                    dim_sums[dim] = dim_sums.get(dim, 0) + score
            dim_avgs = {k: round(v / len(reports), 1) for k, v in dim_sums.items()}
            dim_text = "、".join(f"{k}{v}分" for k, v in dim_avgs.items())

            # 趋势
            if len(reports) >= 2:
                sorted_reports = sorted(reports, key=lambda r: r.created_at)
                first = sorted_reports[0].overall_score
                last = sorted_reports[-1].overall_score
                if last > first + 0.5:
                    trend = "上升"
                elif last < first - 0.5:
                    trend = "下降"
                else:
                    trend = "平稳"
            else:
                trend = "数据不足"
        else:
            avg_score = 0
            dim_avgs = {}
            dim_text = "无评估数据"
            trend = "无评估数据"

        return {
            "session_count": session_count,
            "success_count": success_count,
            "avg_score": avg_score,
            "dimension_scores": dim_avgs,
            "dimension_scores_text": dim_text,
            "score_trend": trend,
        }

    def _parse_json(self, response: str) -> dict | None:
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
