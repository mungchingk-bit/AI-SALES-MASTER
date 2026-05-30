import json
import re

from core.llm_client import get_client
from models.training_session import TrainingSession
from models.evaluation_report import EvaluationReport
from prompts.phrase_extraction import PHRASE_EXTRACTION_PROMPT
from storage.knowledge_store import KnowledgeStore, KnowledgeEntry

import config


class PhraseExtractor:
    def __init__(self):
        self.client = get_client()
        self.knowledge_store = KnowledgeStore()

    def extract_and_save(
        self, session: TrainingSession, report: EvaluationReport
    ) -> int:
        """从高分训练对话中提取优秀话术并保存到知识库。返回提取条数。"""
        if not getattr(config, "PHRASE_EXTRACTION_ENABLED", True):
            return 0
        if report.overall_score < getattr(config, "PHRASE_EXTRACTION_THRESHOLD", 6.0):
            return 0

        conversation_text = self._format_conversation(session)
        if not conversation_text:
            return 0

        strengths = "\n".join(report.strengths) if report.strengths else "无特别标注"
        prompt = PHRASE_EXTRACTION_PROMPT.format(
            conversation=conversation_text, strengths=strengths
        )

        try:
            response = self.client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
                model=config.FAST_MODEL or None,
            )
            phrases = self._parse_response(response)
            if not phrases:
                return 0

            sales_name = session.user or "未知"
            saved = 0
            for p in phrases:
                phrase_text = p.get("phrase", "").strip()
                if not phrase_text or len(phrase_text) < 5:
                    continue

                content = f"【话术】{phrase_text}\n【场景】{p.get('context', '')}\n【异议类型】{p.get('objection_type', '')}"
                entry = KnowledgeEntry(
                    title=f"{sales_name}实战话术-{p.get('context', '通用')}",
                    content=content,
                    category="script_library",
                    source_file=f"auto_extracted_{session.id[:8]}",
                )
                self.knowledge_store.save(entry)
                saved += 1
            return saved
        except Exception:
            return 0

    def _format_conversation(self, session: TrainingSession) -> str:
        """格式化对话内容用于提取。"""
        lines = []
        for msg in session.conversation:
            role = "销售" if msg.role == "user" else "客户"
            lines.append(f"{role}：{msg.content}")
        text = "\n".join(lines)
        return text[:6000]

    def _parse_response(self, response: str) -> list[dict]:
        """Parse JSON from LLM response."""
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()
        try:
            result = json.loads(json_str)
            return result.get("phrases", [])
        except (json.JSONDecodeError, AttributeError):
            return []
