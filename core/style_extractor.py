import json
import re

from core.llm_client import get_client
from models.chat_message import ChatMessage
from models.style_profile import StyleProfile
from prompts.style_extraction import STYLE_EXTRACTION_PROMPT, STYLE_CHUNK_MERGE_PROMPT
from utils.text_utils import estimate_tokens, format_conversation_for_prompt

import config


class StyleExtractor:
    def __init__(self):
        self.client = get_client()

    def extract(self, messages: list[ChatMessage], source_file: str = "") -> StyleProfile:
        """Extract a StyleProfile from a list of chat messages."""
        conversation_text = format_conversation_for_prompt(messages)
        estimated_tokens = estimate_tokens(conversation_text)

        if estimated_tokens <= config.MAX_CHUNK_TOKENS:
            # Single chunk extraction
            traits = self._extract_from_text(conversation_text)
        else:
            # Multi-chunk extraction with merging
            traits = self._extract_chunked(messages)

        # Build sample dialogues (first 5 exchanges)
        sample_dialogues = []
        for i, msg in enumerate(messages[:10]):
            speaker = "销售" if msg.role == "user" else "客户"
            sample_dialogues.append(f"{speaker}：{msg.content}")

        profile = StyleProfile(
            name=traits.get("style_name", "未命名风格"),
            description=traits.get("style_summary", ""),
            source_file=source_file,
            extracted_traits=traits,
            confidence_scores=self._compute_confidence(traits, len(messages)),
            sample_dialogues=sample_dialogues,
        )
        return profile

    def _extract_from_text(self, text: str) -> dict:
        """Extract style traits from a single text block."""
        prompt = STYLE_EXTRACTION_PROMPT.format(chat_records=text)
        response = self.client.chat(
            messages=[],
            system_prompt=prompt,
            temperature=config.EXTRACTION_TEMP,
            max_tokens=2048,
        )
        return self._parse_json_response(response)

    def _extract_chunked(self, messages: list[ChatMessage]) -> dict:
        """Extract style traits from multiple chunks and merge."""
        chunks = self._split_into_chunks(messages)
        chunk_results = []

        for chunk in chunks:
            text = format_conversation_for_prompt(chunk)
            result = self._extract_from_text(text)
            if result:
                chunk_results.append(result)

        if not chunk_results:
            return self._default_traits()

        if len(chunk_results) == 1:
            return chunk_results[0]

        # Merge results
        merge_prompt = STYLE_CHUNK_MERGE_PROMPT.format(
            chunk_results=json.dumps(chunk_results, ensure_ascii=False, indent=2)
        )
        response = self.client.chat(
            messages=[],
            system_prompt=merge_prompt,
            temperature=config.EXTRACTION_TEMP,
            max_tokens=2048,
        )
        return self._parse_json_response(response)

    def _split_into_chunks(self, messages: list[ChatMessage]) -> list[list[ChatMessage]]:
        """Split messages into chunks that fit within token limits."""
        chunks = []
        current_chunk = []
        current_tokens = 0

        for msg in messages:
            msg_tokens = estimate_tokens(msg.content) + 10  # overhead for speaker prefix
            if current_tokens + msg_tokens > config.MAX_CHUNK_TOKENS and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0
            current_chunk.append(msg)
            current_tokens += msg_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON in code blocks
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return self._default_traits()

    def _compute_confidence(self, traits: dict, message_count: int) -> dict:
        """Compute confidence scores for each trait based on data volume."""
        # Base confidence: more messages = higher confidence
        base = min(1.0, message_count / 30)
        confidence = {}
        for key in ["communication_pattern", "tone", "objection_strategy", "closing_style",
                     "key_phrases", "avoid_patterns", "pacing"]:
            value = traits.get(key)
            if isinstance(value, list) and len(value) > 0:
                confidence[key] = base
            elif isinstance(value, str) and len(value) > 0:
                confidence[key] = base
            else:
                confidence[key] = base * 0.5
        return confidence

    def _default_traits(self) -> dict:
        return {
            "communication_pattern": "",
            "tone": "",
            "objection_strategy": "",
            "closing_style": "",
            "key_phrases": [],
            "avoid_patterns": [],
            "pacing": "",
            "style_name": "未识别",
            "style_summary": "数据不足，无法准确提取风格特征",
        }
