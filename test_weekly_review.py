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
        result = {
            "summary": "本周综合复盘",
            "strengths": ["能主动提问"],
            "suggestions": ["加强预算异议处理"],
            "focus_areas": ["异议处理"],
        }
        if "团队管理复盘" in kwargs["system_prompt"]:
            result["individual_insights"] = [
                {
                    "sales_name": "小王",
                    "strength": "提问清楚",
                    "improvement": "预算异议处理不够深入",
                    "next_action": "完成两轮预算异议训练",
                },
                {
                    "sales_name": "小李",
                    "strength": "表达自然",
                    "improvement": "收尾不够明确",
                    "next_action": "练习确认下一步",
                },
            ]
        return json.dumps(result, ensure_ascii=False)


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

    def test_team_review_aggregates_all_sales_and_is_incremental(self):
        wang = _session(user="小王")
        li = _session(user="小李", started_at="2026-06-17T10:00:00")
        wang_eval = EvaluationReport(session_id=wang.id, overall_score=8)
        li_face = ConversationReport(
            sales_name="小李",
            source_file="li.txt",
            source_title="小李面聊",
            created_at="2026-06-18T10:00:00",
        )
        reviewer = self._reviewer([wang, li], [wang_eval], [li_face])
        now = datetime(2026, 6, 20, 12)

        first, first_status = reviewer.generate_team_with_status(now=now)
        second, second_status = reviewer.generate_team_with_status(now=now)

        self.assertEqual(first_status, "created")
        self.assertEqual(second_status, "unchanged")
        self.assertEqual(first.scope, "team")
        self.assertEqual(first.user, "__team__")
        self.assertEqual(first.sales_count, 2)
        self.assertEqual(first.session_count, 2)
        self.assertEqual(first.face_to_face_count, 1)
        self.assertEqual(len(first.individual_insights), 2)
        self.assertEqual(
            [item["sales_name"] for item in first.individual_insights],
            ["小李", "小王"],
        )
        prompt = reviewer.client.calls[0]["system_prompt"]
        self.assertIn("销售：小王", prompt)
        self.assertIn("销售：小李", prompt)
        self.assertEqual(len(reviewer.client.calls), 1)

    def test_team_insights_filter_unknown_names_and_fill_missing_sales(self):
        from core.weekly_review import WeeklyReviewer

        normalized = WeeklyReviewer._normalize_team_insights(
            [
                {"sales_name": "小王", "strength": "提问好"},
                {"sales_name": "不存在的人", "improvement": "不应出现"},
            ],
            ["小王", "小李"],
            ["需求挖掘"],
        )

        self.assertEqual([item["sales_name"] for item in normalized], ["小王", "小李"])
        self.assertEqual(normalized[0]["strength"], "提问好")
        self.assertIn("需求挖掘", normalized[1]["next_action"])


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
        self.assertEqual(legacy.scope, "personal")
        self.assertEqual(legacy.updated_at, legacy.created_at)

        from storage.weekly_review_store import WeeklyReviewStore

        store = WeeklyReviewStore.__new__(WeeklyReviewStore)
        store.list_by_user = lambda user: [legacy]
        context = store.build_growth_context("小王")
        self.assertIn("加强异议处理", context)
        self.assertIn("预算沟通", context)
        self.assertEqual(store.build_growth_context(""), "")

    def test_team_growth_context_only_exposes_matching_salesperson(self):
        personal = WeeklyReview(
            user="小王", week_start="2026-06-15", week_end="2026-06-20",
            suggestions=["个人建议"],
        )
        team = WeeklyReview(
            user="__team__", scope="team", week_start="2026-06-15", week_end="2026-06-20",
            individual_insights=[
                {"sales_name": "小王", "improvement": "小王改进", "next_action": "小王动作"},
                {"sales_name": "小李", "improvement": "小李私有改进", "next_action": "小李动作"},
            ],
        )
        from storage.weekly_review_store import WeeklyReviewStore

        store = WeeklyReviewStore.__new__(WeeklyReviewStore)
        store.list_by_user = lambda user: [personal] if user == "小王" else [team] if user == "__team__" else []

        context = store.build_growth_context("小王")

        self.assertIn("个人建议", context)
        self.assertIn("小王改进", context)
        self.assertNotIn("小李私有改进", context)

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


class WeeklyReviewPermissionTests(unittest.TestCase):
    def test_sales_account_is_forced_to_own_display_name(self):
        from ui import weekly_tab

        fake_store = SimpleNamespace(
            get_user=lambda username: {
                "role": "sales", "display_name": "小王",
            } if username == "13800000000" else None,
        )
        with patch.object(weekly_tab, "UserStore", return_value=fake_store):
            target, role = weekly_tab._personal_target("13800000000", "小李")

        self.assertEqual(role, "sales")
        self.assertEqual(target, "小王")

    def test_admin_must_choose_personal_target(self):
        from ui import weekly_tab

        fake_store = SimpleNamespace(
            get_user=lambda username: {"role": "admin", "display_name": "管理员"},
        )
        with patch.object(weekly_tab, "UserStore", return_value=fake_store):
            empty_target, role = weekly_tab._personal_target("admin", None)
            selected_target, _ = weekly_tab._personal_target("admin", "小李")

        self.assertEqual(role, "admin")
        self.assertEqual(empty_target, "")
        self.assertEqual(selected_target, "小李")


if __name__ == "__main__":
    unittest.main()
