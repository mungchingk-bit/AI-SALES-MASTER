"""面聊记录分析引擎 — 生成优劣汇报。"""
import json
import re

from core.llm_client import get_client
from models.conversation_report import ConversationReport
from prompts.conversation_analysis import CONVERSATION_ANALYSIS_PROMPT

import config


class ConversationAnalyzer:
    def analyze(
        self,
        content: str,
        sales_name: str,
        source_file: str = "",
        source_title: str = "",
    ) -> ConversationReport:
        """分析一次面聊记录，生成汇报。"""
        # 截取前8000字符避免本地模型超时
        truncated = content[:8000]

        prompt = CONVERSATION_ANALYSIS_PROMPT.format(
            sales_name=sales_name,
            source_title=source_title or "未知",
            content=truncated,
        )

        client = get_client()
        raw = client.chat(
            messages=[],
            system_prompt=prompt,
            temperature=config.EVALUATION_TEMP,
            max_tokens=3000,
        )

        data = self._parse_response(raw)
        return ConversationReport(
            sales_name=sales_name,
            source_file=source_file,
            source_title=source_title,
            highlights=data.get("highlights", []),
            improvements=data.get("improvements", []),
            corrected_scripts=data.get("corrected_scripts", []),
            next_steps=data.get("next_steps", []),
            summary=data.get("summary", ""),
        )

    def _parse_response(self, raw: str) -> dict:
        """从LLM回复中解析JSON。"""
        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 代码块
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试找第一个 { 到最后一个 }
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass

        # 解析失败，返回最小结构
        return {
            "highlights": [],
            "improvements": [],
            "corrected_scripts": [],
            "next_steps": [],
            "summary": raw[:200] if raw else "分析失败",
        }
