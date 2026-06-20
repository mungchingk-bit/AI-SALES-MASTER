import json
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from models.chat_message import ChatMessage
from models.conversation_report import ConversationReport
from models.evaluation_report import EvaluationReport
from models.training_session import TrainingSession
from models.weekly_review import WeeklyReview


class _ListStore:
    def __init__(self, items=None):
        self.items = list(items or [])

    def list_all(self):
        return list(self.items)


class _ReviewStore:
    def __init__(self):
        self.items = []

    def list_by_user(self, user):
        return [item for item in self.items if item.user == user]

    def save(self, review):
        self.items = [item for item in self.items if item.id != review.id]
        self.items.append(review)


class _Client:
    def __init__(self):
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps({
            "summary": "本周综合复盘",
            "strengths": ["能主动提问"],
            "suggestions": ["加强预算异议处理"],
            "focus_areas": ["异议处理"],
        }, ensure_ascii=False)


def _session(user="小王", started_at="2026-06-16T10:00:00"):
    session = TrainingSession(mode="customer", user=user, started_at=started_at)
    session.status = "completed"
    session.end_reason = "成功"
    session.conversation = [ChatMessage(role="user", content="先了解您的预算")]
    return session


class WeeklyReviewerTests(unittest.TestCase):
    def _reviewer(self, sessions=None, evaluations=None, face_reports=None):
        from core.weekly_review import WeeklyReviewer

        reviewer = WeeklyReviewer.__new__(WeeklyReviewer)
        reviewer.client = _Client()
        reviewer.session_store = _ListStore(sessions)
        reviewer.evaluation_store = _ListStore(evaluations)
        reviewer.report_store = _ListStore(face_reports)
        reviewer.review_store = _ReviewStore()
        return reviewer

    def test_week_data_is_monday_to_now_and_user_isolated(self):
        included = _session()
        before_week = _session(started_at="2026-06-14T23:59:59")
        other_user = _session(user="小李")
        future = _session(started_at="2026-06-21T10:00:00")
        included_eval = EvaluationReport(session_id=included.id, overall_score=8)
        other_eval = EvaluationReport(session_id=other_user.id, overall_score=9)
        included_face = ConversationReport(
            sales_name="小王", source_file="a.txt", source_title="面聊A",
            created_at="2026-06-18T10:00:00",
        )
        other_face = ConversationReport(
            sales_name="小李", source_file="b.txt", source_title="面聊B",
            created_at="2026-06-18T10:00:00",
        )
        reviewer = self._reviewer(
            [included, before_week, other_user, future],
            [included_eval, other_eval],
            [included_face, other_face],
        )

        sessions, evaluations, faces = reviewer._get_week_data(
            "小王", datetime(2026, 6, 15), datetime(2026, 6, 20, 12),
        )

        self.assertEqual([item.id for item in sessions], [included.id])
        self.assertEqual([item.id for item in evaluations], [included_eval.id])
        self.assertEqual([item.id for item in faces], [included_face.id])

    def test_empty_week_does_not_call_model(self):
        reviewer = self._reviewer()

        review, status = reviewer.generate_with_status(
            "小王", now=datetime(2026, 6, 20, 12),
        )

        self.assertIsNone(review)
        self.assertEqual(status, "empty")
        self.assertEqual(reviewer.client.calls, [])

    def test_same_week_skips_unchanged_and_updates_when_source_changes(self):
        session = _session()
        evaluation = EvaluationReport(
            session_id=session.id,
            overall_score=8,
            dimension_scores={"异议处理": {"score": 7}},
            strengths=["提问清楚"],
            improvements=["异议处理不够深入"],
        )
        reviewer = self._reviewer([session], [evaluation])
        now = datetime(2026, 6, 20, 12)

        first, first_status = reviewer.generate_with_status("小王", now=now)
        second, second_status = reviewer.generate_with_status("小王", now=now)
        session.conversation.append(ChatMessage(role="assistant", content="预算大约五万"))
        third, third_status = reviewer.generate_with_status("小王", now=now)

        self.assertEqual(first_status, "created")
        self.assertEqual(second_status, "unchanged")
        self.assertEqual(third_status, "updated")
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.id, third.id)
        self.assertEqual(len(reviewer.client.calls), 2)
        self.assertEqual(third.session_count, 1)
        self.assertEqual(third.strengths, ["能主动提问"])

    def test_face_report_alone_can_generate_review(self):
        face = ConversationReport(
            sales_name="小王",
            uploader_name="小王",
            source_file="meeting.txt",
            source_title="客户面聊",
            summary="客户在意预算透明",
            improvements=["报价解释不够清晰"],
            created_at="2026-06-19T10:00:00",
        )
        reviewer = self._reviewer(face_reports=[face])

        review, status = reviewer.generate_with_status(
            "小王", now=datetime(2026, 6, 20, 12),
        )

        self.assertEqual(status, "created")
        self.assertEqual(review.session_count, 0)
        self.assertEqual(review.face_to_face_count, 1)
        self.assertIn("客户在意预算透明", reviewer.client.calls[0]["system_prompt"])


class WeeklyGrowthContextTests(unittest.TestCase):
    def test_legacy_review_defaults_and_growth_context(self):
        legacy = WeeklyReview.from_dict({
            "user": "小王",
            "week_start": "2026-06-15",
            "week_end": "2026-06-20",
            "created_at": "2026-06-20T12:00:00",
            "suggestions": ["加强异议处理"],
            "focus_areas": ["预算沟通"],
        })
        self.assertEqual(legacy.face_to_face_count, 0)
        self.assertEqual(legacy.updated_at, legacy.created_at)

        from storage.weekly_review_store import WeeklyReviewStore

        store = WeeklyReviewStore.__new__(WeeklyReviewStore)
        store.list_by_user = lambda user: [legacy]
        context = store.build_growth_context("小王")
        self.assertIn("加强异议处理", context)
        self.assertIn("预算沟通", context)
        self.assertEqual(store.build_growth_context(""), "")

    def test_growth_context_is_added_to_simulation_and_evaluation_prompts(self):
        from core.role_engine import RoleEngine
        from prompts.evaluation import build_evaluation_prompt

        instruction = RoleEngine._build_growth_instruction("重点：异议处理", "customer")
        self.assertIn("重点：异议处理", instruction)
        self.assertIn("不要直接说出训练目标", instruction)

        prompt = build_evaluation_prompt(
            session_data={"mode": "customer", "conversation": [], "scenario": {}},
            growth_context="近期训练重点：预算沟通",
        )
        self.assertIn("最近成长复盘", prompt)
        self.assertIn("预算沟通", prompt)


if __name__ == "__main__":
    unittest.main()
