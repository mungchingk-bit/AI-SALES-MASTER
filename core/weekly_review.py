import hashlib
import json
import re
from datetime import datetime, timedelta

from core.llm_client import get_client
from models.weekly_review import WeeklyReview
from prompts.weekly_review import WEEKLY_REVIEW_PROMPT
from storage.evaluation_store import EvaluationStore
from storage.report_store import ReportStore
from storage.session_store import SessionStore
from storage.weekly_review_store import WeeklyReviewStore

import config


_MAX_SOURCE_CONTEXT_CHARS = 18000


class WeeklyReviewer:
    def __init__(self):
        self.client = get_client()
        self.session_store = SessionStore()
        self.evaluation_store = EvaluationStore()
        self.report_store = ReportStore()
        self.review_store = WeeklyReviewStore()

    def generate(self, user: str) -> WeeklyReview | None:
        review, _ = self.generate_with_status(user)
        return review

    def generate_with_status(
        self,
        user: str,
        now: datetime | None = None,
    ) -> tuple[WeeklyReview | None, str]:
        """Create/update this week's review. Status: created/updated/unchanged/empty."""
        now = now or datetime.now()
        week_start_dt = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        week_start = week_start_dt.strftime("%Y-%m-%d")
        week_end = now.strftime("%Y-%m-%d")

        sessions, evaluations, face_reports = self._get_week_data(
            user, week_start_dt, now,
        )
        if not sessions and not face_reports:
            return None, "empty"

        signature = self._data_signature(sessions, evaluations, face_reports)
        existing = next(
            (r for r in self.review_store.list_by_user(user) if r.week_start == week_start),
            None,
        )
        if existing and existing.data_signature == signature:
            return existing, "unchanged"

        stats = self._aggregate(sessions, evaluations, face_reports)
        source_context = self._build_source_context(sessions, evaluations, face_reports)
        prompt = WEEKLY_REVIEW_PROMPT.format(
            period=f"{week_start} 至 {week_end}",
            session_count=stats["session_count"],
            face_to_face_count=stats["face_to_face_count"],
            success_count=stats["success_count"],
            avg_score=stats["avg_score"],
            score_trend=stats["score_trend"],
            dimension_scores=stats["dimension_scores_text"],
            source_context=source_context,
        )

        try:
            response = self.client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
                model=config.FAST_MODEL or None,
            )
            result = self._parse_json(response)
        except Exception as exc:
            raise RuntimeError(f"调用AI生成复盘失败：{exc}") from exc
        if not result:
            raise RuntimeError("AI复盘返回格式无法解析，请稍后重试")

        timestamp = now.isoformat()
        review = existing or WeeklyReview(user=user, week_start=week_start, week_end=week_end)
        review.week_end = week_end
        review.session_count = stats["session_count"]
        review.face_to_face_count = stats["face_to_face_count"]
        review.success_count = stats["success_count"]
        review.avg_overall_score = stats["avg_score"]
        review.avg_dimension_scores = stats["dimension_scores"]
        review.score_trend = stats["score_trend"]
        review.strengths = result.get("strengths", [])
        review.suggestions = result.get("suggestions", [])
        review.focus_areas = result.get("focus_areas", [])
        review.summary = result.get("summary", "")
        review.data_signature = signature
        review.updated_at = timestamp
        self.review_store.save(review)
        return review, "updated" if existing else "created"

    def _get_week_data(
        self,
        user: str,
        week_start: datetime,
        now: datetime,
    ) -> tuple[list, list, list]:
        """Get Monday-to-current sources belonging to one user."""
        sessions = [
            session for session in self.session_store.list_all()
            if session.user == user and self._in_period(session.started_at, week_start, now)
        ]
        session_ids = {session.id for session in sessions}
        evaluations = [
            report for report in self.evaluation_store.list_all()
            if report.session_id in session_ids
        ]
        face_reports = [
            report for report in self.report_store.list_all()
            if (report.sales_name == user or report.uploader_name == user)
            and self._in_period(report.created_at, week_start, now)
        ]
        return sessions, evaluations, face_reports

    @staticmethod
    def _in_period(value: str, start: datetime, end: datetime) -> bool:
        if not value:
            return False
        try:
            point = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return False
        return start <= point <= end

    @staticmethod
    def _data_signature(sessions, evaluations, face_reports) -> str:
        payload = {
            "sessions": sorted((s.to_dict() for s in sessions), key=lambda item: item["id"]),
            "evaluations": sorted((r.to_dict() for r in evaluations), key=lambda item: item["id"]),
            "face_reports": sorted((r.to_dict() for r in face_reports), key=lambda item: item["id"]),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _build_source_context(self, sessions, evaluations, face_reports) -> str:
        evaluation_by_session = {report.session_id: report for report in evaluations}
        sections = []
        for session in sorted(sessions, key=lambda item: item.started_at):
            report = evaluation_by_session.get(session.id)
            lines = [
                f"### 训练 {session.started_at[:10]}｜模式：{session.mode}｜状态：{session.status}｜结果：{session.end_reason or '未标记'}"
            ]
            if report:
                lines.append(f"总分：{report.overall_score}/10")
                lines.append("优势：" + "；".join(report.strengths[:4]))
                lines.append("改进：" + "；".join(report.improvements[:4]))
                if report.recommendation:
                    lines.append("建议：" + report.recommendation[:600])
                if report.conversation_summary:
                    lines.append("对话总结：" + report.conversation_summary[:1000])
                if report.specific_examples:
                    lines.append(
                        "关键案例：" + "；".join(
                            str(item)[:400] for item in report.specific_examples[:4]
                        )
                    )
                if report.deal_progression:
                    lines.append(
                        "成交推进：" + json.dumps(
                            report.deal_progression, ensure_ascii=False,
                        )[:1000]
                    )
            else:
                excerpts = [
                    f"{'用户' if msg.role == 'user' else 'AI'}：{msg.content[:240]}"
                    for msg in session.conversation[-6:]
                ]
                if excerpts:
                    lines.append("最近对话：\n" + "\n".join(excerpts))
            sections.append("\n".join(lines))

        for report in sorted(face_reports, key=lambda item: item.created_at):
            lines = [
                f"### 面聊汇报 {report.created_at[:10]}｜{report.source_title or report.source_file}",
                "总结：" + report.summary[:1000],
                "亮点：" + "；".join(report.highlights[:5]),
                "待改进：" + "；".join(report.improvements[:5]),
                "纠正话术：" + "；".join(
                    str(item)[:500] for item in report.corrected_scripts[:5]
                ),
                "下一步：" + "；".join(str(item)[:500] for item in report.next_steps[:5]),
            ]
            sections.append("\n".join(lines))

        return "\n\n".join(sections)[:_MAX_SOURCE_CONTEXT_CHARS]

    def _aggregate(self, sessions, reports, face_reports) -> dict:
        session_count = len(sessions)
        success_count = sum(1 for session in sessions if session.end_reason == "成功")

        if reports:
            avg_score = round(sum(r.overall_score for r in reports) / len(reports), 1)
            dim_sums = {}
            dim_counts = {}
            for report in reports:
                for dim, data in report.dimension_scores.items():
                    score = data.get("score", 0) if isinstance(data, dict) else data
                    dim_sums[dim] = dim_sums.get(dim, 0) + score
                    dim_counts[dim] = dim_counts.get(dim, 0) + 1
            dim_avgs = {key: round(value / dim_counts[key], 1) for key, value in dim_sums.items()}
            dim_text = "、".join(f"{key}{value}分" for key, value in dim_avgs.items())
            if len(reports) >= 2:
                sorted_reports = sorted(reports, key=lambda report: report.created_at)
                change = sorted_reports[-1].overall_score - sorted_reports[0].overall_score
                trend = "上升" if change > 0.5 else "下降" if change < -0.5 else "平稳"
            else:
                trend = "数据不足"
        else:
            avg_score = 0
            dim_avgs = {}
            dim_text = "无评估数据"
            trend = "无评估数据"

        return {
            "session_count": session_count,
            "face_to_face_count": len(face_reports),
            "success_count": success_count,
            "avg_score": avg_score,
            "dimension_scores": dim_avgs,
            "dimension_scores_text": dim_text,
            "score_trend": trend,
        }

    @staticmethod
    def _parse_json(response: str) -> dict | None:
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        json_str = json_match.group(1).strip() if json_match else response.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
