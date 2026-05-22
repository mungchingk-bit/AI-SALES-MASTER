import json
import re

from core.llm_client import get_client
from models.evaluation_report import EvaluationReport
from models.training_session import TrainingSession
from models.style_profile import StyleProfile
from prompts.evaluation import build_evaluation_prompt
from prompts.conversation_summary import (
    build_conversation_summary_prompt,
    build_deal_progression_prompt,
)
from storage.evaluation_store import EvaluationStore
from storage.style_store import StyleStore
from storage.session_store import SessionStore

import config


class Evaluator:
    def __init__(self):
        self.client = get_client()
        self.evaluation_store = EvaluationStore()
        self.style_store = StyleStore()
        self.session_store = SessionStore()

    def evaluate(self, session_id: str) -> EvaluationReport | None:
        """Evaluate a completed training session with full report."""
        session = self.session_store.load(session_id)
        if not session:
            return None

        # Load style profile if available
        style_profile = None
        if session.style_profile_id:
            style_profile_obj = self.style_store.load(session.style_profile_id)
            if style_profile_obj:
                style_profile = style_profile_obj.to_dict()

        # Build evaluation prompt
        prompt = build_evaluation_prompt(
            session_data=session.to_dict(),
            style_profile=style_profile,
        )

        # Call LLM for dimension scoring
        response = self.client.chat(
            messages=[],
            system_prompt=prompt,
            temperature=config.EVALUATION_TEMP,
            max_tokens=config.MAX_TOKENS_EVALUATION,
        )

        # Parse response
        result = self._parse_json_response(response)
        if not result:
            return self._create_default_report(session_id)

        # Build report
        report = self._build_report(session_id, result, session)

        # Generate conversation summary (实战复盘)
        summary = self._generate_conversation_summary(session)
        report.conversation_summary = summary

        # Generate deal progression analysis (成交路径)
        progression = self._generate_deal_progression(session)
        report.deal_progression = progression

        # Save and return
        self.evaluation_store.save(report)

        # Update session with evaluation link
        session.evaluation_id = report.id
        self.session_store.save(session)

        return report

    def generate_summary_only(self, session_id: str) -> str:
        """Generate only the conversation summary (fast, for immediate display)."""
        session = self.session_store.load(session_id)
        if not session:
            return "会话不存在"
        return self._generate_conversation_summary(session)

    def _generate_conversation_summary(self, session: TrainingSession) -> str:
        """Generate the practical conversation summary."""
        prompt = build_conversation_summary_prompt(session_data=session.to_dict())
        try:
            response = self.client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=0.4,
                max_tokens=3000,
            )
            return response.strip()
        except Exception:
            return "总结生成失败，请稍后重试。"

    def _generate_deal_progression(self, session: TrainingSession) -> dict:
        """Generate the deal progression analysis."""
        prompt = build_deal_progression_prompt(session_data=session.to_dict())
        try:
            response = self.client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
            )
            result = self._parse_json_response(response)
            return result if result else {}
        except Exception:
            return {}

    def _build_report(self, session_id: str, result: dict, session: TrainingSession) -> EvaluationReport:
        """Build an EvaluationReport from parsed LLM response."""
        dimensions = result.get("dimensions", {})
        dimension_scores = {}
        for dim_name, dim_data in dimensions.items():
            if isinstance(dim_data, dict):
                dimension_scores[dim_name] = dim_data
            else:
                dimension_scores[dim_name] = {"score": 0, "justification": str(dim_data)}

        # Calculate weighted overall score
        total_weight = 0
        weighted_sum = 0
        for dim_name, dim_data in dimension_scores.items():
            score = dim_data.get("score", 0)
            weight = config.EVAL_WEIGHTS.get(dim_name, 1.0)
            weighted_sum += score * weight
            total_weight += weight

        overall_score = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0

        return EvaluationReport(
            session_id=session_id,
            dimension_scores=dimension_scores,
            overall_score=overall_score,
            strengths=result.get("strengths", []),
            improvements=result.get("improvements", []),
            style_alignment=result.get("style_alignment"),
            specific_examples=result.get("specific_examples", []),
            recommendation=result.get("recommendation", ""),
        )

    def _parse_json_response(self, response: str) -> dict | None:
        """Parse JSON from LLM response."""
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    def _create_default_report(self, session_id: str) -> EvaluationReport:
        """Create a default report when evaluation fails."""
        return EvaluationReport(
            session_id=session_id,
            dimension_scores={
                "沟通表达": {"score": 5, "justification": "评估生成失败"},
                "需求发掘": {"score": 5, "justification": "评估生成失败"},
                "价值主张": {"score": 5, "justification": "评估生成失败"},
                "异议处理": {"score": 5, "justification": "评估生成失败"},
                "流程完整": {"score": 5, "justification": "评估生成失败"},
                "关系建立": {"score": 5, "justification": "评估生成失败"},
                "风格运用": {"score": 5, "justification": "评估生成失败"},
                "收尾技巧": {"score": 5, "justification": "评估生成失败"},
            },
            overall_score=5.0,
            strengths=["评估生成失败，请重试"],
            improvements=["评估生成失败，请重试"],
            recommendation="请重新进行训练并生成评估报告",
        )
