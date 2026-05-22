import re

from core.llm_client import get_client
from models.chat_message import ChatMessage
from models.style_profile import StyleProfile
from prompts.customer_simulation import build_customer_prompt
from prompts.sales_simulation import build_sales_prompt

import config


class RoleEngine:
    def __init__(self):
        self.client = get_client()

    def generate_customer_response(
        self,
        conversation: list[ChatMessage],
        scenario: dict,
    ) -> tuple[str, int]:
        """Generate a customer response. Returns (response_text, receptivity_score)."""
        system_prompt = build_customer_prompt(scenario)
        messages = [msg.to_api_message() for msg in conversation]

        temperature = config.CUSTOMER_TEMP
        response = self.client.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=config.MAX_TOKENS_RESPONSE,
        )

        # Parse receptivity score from hidden tag
        receptivity = self._parse_receptivity(response)
        clean_response = self._strip_tags(response)

        return clean_response, receptivity

    def generate_customer_response_stream(
        self,
        conversation: list[ChatMessage],
        scenario: dict,
    ):
        """Stream a customer response. Yields (partial_text, is_done, receptivity)."""
        system_prompt = build_customer_prompt(scenario)
        messages = [msg.to_api_message() for msg in conversation]

        full_response = ""
        for chunk in self.client.chat_stream(
            messages=messages,
            system_prompt=system_prompt,
            temperature=config.CUSTOMER_TEMP,
            max_tokens=config.MAX_TOKENS_RESPONSE,
        ):
            full_response += chunk
            # Stream the raw text (tags still present for now, will clean at end)
            yield chunk, False, 0

        # Stream complete - parse tags
        receptivity = self._parse_receptivity(full_response)
        yield "", True, receptivity

    def generate_sales_response(
        self,
        conversation: list[ChatMessage],
        style_profile: StyleProfile,
        scenario: dict,
        current_phase: str = "开场",
        turn_number: int = 1,
    ) -> tuple[str, str]:
        """Generate a salesperson response. Returns (response_text, style_note)."""
        system_prompt = build_sales_prompt(
            style_profile=style_profile.to_dict(),
            scenario=scenario,
            current_phase=current_phase,
            turn_number=turn_number,
        )
        messages = [msg.to_api_message() for msg in conversation]

        response = self.client.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=config.SALES_TEMP,
            max_tokens=config.MAX_TOKENS_RESPONSE,
        )

        style_note = self._parse_style_note(response)
        clean_response = self._strip_tags(response)

        return clean_response, style_note

    def generate_sales_response_stream(
        self,
        conversation: list[ChatMessage],
        style_profile: StyleProfile,
        scenario: dict,
        current_phase: str = "开场",
        turn_number: int = 1,
    ):
        """Stream a salesperson response. Yields (partial_text, is_done, style_note)."""
        system_prompt = build_sales_prompt(
            style_profile=style_profile.to_dict(),
            scenario=scenario,
            current_phase=current_phase,
            turn_number=turn_number,
        )
        messages = [msg.to_api_message() for msg in conversation]

        full_response = ""
        for chunk in self.client.chat_stream(
            messages=messages,
            system_prompt=system_prompt,
            temperature=config.SALES_TEMP,
            max_tokens=config.MAX_TOKENS_RESPONSE,
        ):
            full_response += chunk
            yield chunk, False, ""

        style_note = self._parse_style_note(full_response)
        yield "", True, style_note

    def _parse_receptivity(self, text: str) -> int:
        """Parse receptivity score from <receptivity>N</receptivity> tag."""
        match = re.search(r"<receptivity>(\d+)</receptivity>", text)
        if match:
            return int(match.group(1))
        return 5  # default

    def _parse_style_note(self, text: str) -> str:
        """Parse style note from <style_note>...</style_note> tag."""
        match = re.search(r"<style_note>(.*?)</style_note>", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _strip_tags(self, text: str) -> str:
        """Remove hidden tags from displayed text."""
        text = re.sub(r"<receptivity>\d+</receptivity>", "", text)
        text = re.sub(r"<style_note>.*?</style_note>", "", text, flags=re.DOTALL)
        return text.strip()
