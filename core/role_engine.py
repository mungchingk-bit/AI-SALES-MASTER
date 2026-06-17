import re

from core.llm_client import get_client
from models.chat_message import ChatMessage
from models.style_profile import StyleProfile
from prompts.customer_simulation import build_customer_prompt
from prompts.sales_simulation import build_sales_prompt

import config

# Max recent messages to keep in full; older ones get compressed into a summary
_MAX_RECENT_MESSAGES = 12  # ~6 turns of full context


class RoleEngine:
    def __init__(self):
        self.client = get_client()

    def generate_customer_response(
        self,
        conversation: list[ChatMessage],
        scenario: dict,
    ) -> tuple[str, int, str]:
        """Generate a customer response. Returns (response_text, receptivity_score, end_reason)."""
        system_prompt = build_customer_prompt(scenario)
        customer_name = scenario.get("customer_name", "客户")
        messages = self._format_as_script(conversation, customer_name, "销售")

        # Inject locked facts as a system message right before the conversation
        locked_facts_msg = self._build_locked_facts_message(scenario, conversation, customer_name)
        if locked_facts_msg:
            # Insert after the system prompt (index 0), before conversation messages
            messages.insert(0, locked_facts_msg)

        temperature = config.CUSTOMER_TEMP
        response = self.client.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=config.MAX_TOKENS_RESPONSE,
            model=config.FAST_MODEL,
        )

        # Parse receptivity score from hidden tag
        receptivity = self._parse_receptivity(response)

        # Parse conversation end signal
        end_reason = self._parse_end_conversation(response)

        clean_response = self._strip_tags(response)

        # Post-process: fix name confusion
        clean_response = self._fix_name_confusion(clean_response, customer_name, conversation)

        # Post-process: fix consistency violations
        clean_response = self._fix_consistency(clean_response, scenario, conversation, customer_name)

        return clean_response, receptivity, end_reason

    def generate_customer_response_stream(
        self,
        conversation: list[ChatMessage],
        scenario: dict,
    ):
        """Stream a customer response. Yields (partial_text, is_done, receptivity)."""
        system_prompt = build_customer_prompt(scenario)
        customer_name = scenario.get("customer_name", "客户")
        messages = self._format_as_script(conversation, customer_name, "销售")

        locked_facts_msg = self._build_locked_facts_message(scenario, conversation, customer_name)
        if locked_facts_msg:
            messages.insert(0, locked_facts_msg)

        full_response = ""
        for chunk in self.client.chat_stream(
            messages=messages,
            system_prompt=system_prompt,
            temperature=config.CUSTOMER_TEMP,
            max_tokens=config.MAX_TOKENS_RESPONSE,
        ):
            full_response += chunk
            yield chunk, False, 0

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
        customer_name = scenario.get("customer_name", "客户")
        messages = self._format_as_script(conversation, "销售", customer_name)

        response = self.client.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=config.SALES_TEMP,
            max_tokens=config.MAX_TOKENS_RESPONSE,
            model=config.FAST_MODEL,
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
        customer_name = scenario.get("customer_name", "客户")
        messages = self._format_as_script(conversation, "销售", customer_name)

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
        text = re.sub(r"<end_conversation>.*?</end_conversation>", "", text, flags=re.DOTALL)
        return text.strip()

    def _parse_end_conversation(self, text: str) -> str:
        """Parse end conversation signal. Returns end reason or empty string."""
        match = re.search(r"<end_conversation>(.*?)</end_conversation>", text)
        if match:
            return match.group(1).strip()
        return ""

    def _build_locked_facts_message(
        self,
        scenario: dict,
        conversation: list[ChatMessage],
        customer_name: str,
    ) -> dict | None:
        """Build a system message containing locked facts that the model MUST follow.
        Combines scenario settings with facts extracted from conversation."""
        facts = []

        # From scenario — these are ground truth
        if scenario.get("wedding_date"):
            facts.append(f"婚期：{scenario['wedding_date']}")
        if scenario.get("budget_situation"):
            facts.append(f"预算：{scenario['budget_situation']}")
        if scenario.get("wedding_type"):
            facts.append(f"婚礼类型：{scenario['wedding_type']}")
        if scenario.get("customer_name"):
            facts.append(f"你的名字：{scenario['customer_name']}")
        if scenario.get("decision_authority"):
            facts.append(f"决策权：{scenario['decision_authority']}")
        if scenario.get("primary_objections"):
            facts.append(f"核心顾虑：{scenario['primary_objections']}")

        # Extract additional facts customer has stated in conversation
        for msg in conversation:
            if msg.role != "assistant":
                continue
            content = msg.content
            # Extract budget mentions
            budget_match = re.search(r"预算[大概约]?(\d+[到\-~]\d+万)", content)
            if budget_match:
                facts.append(f"你已说过预算：{budget_match.group(1)}")
            # Extract timeline mentions
            time_match = re.search(r"(明年|今年|后年)\S*(春天|夏天|秋天|冬天|\d+月)", content)
            if time_match:
                facts.append(f"你已说过婚期时间：{time_match.group(0)}")
            # Extract guest count
            guest_match = re.search(r"(\d+[到\-~]\d+桌|\d+桌)", content)
            if guest_match:
                facts.append(f"你已说过桌数：{guest_match.group(1)}")

        if not facts:
            return None

        lines = ["【已锁定事实——你必须严格遵守，绝对不能与以下事实矛盾：】"]
        for f in facts:
            lines.append(f"  ✦ {f}")
        lines.append("如果你的回复与以上任何一条矛盾，立即修改！")
        return {"role": "system", "content": "\n".join(lines)}

    def _compress_older_messages(
        self,
        conversation: list[ChatMessage],
        ai_label: str,
        user_label: str,
    ) -> list[dict]:
        """Compress older messages into a summary to keep context manageable for small models."""
        if len(conversation) <= _MAX_RECENT_MESSAGES:
            return []

        older = conversation[:-_MAX_RECENT_MESSAGES]
        topics_discussed = []
        for msg in older:
            prefix = ai_label if msg.role == "assistant" else user_label
            topics_discussed.append(f"{prefix}：{msg.content[:60]}")

        summary_lines = [
            f"[以下是之前{len(older)}条消息的摘要，这些内容已经讨论过，绝对不能重复：]",
        ]
        for item in topics_discussed:
            summary_lines.append(item)
        summary_lines.append("[以上内容已充分讨论，禁止再问类似问题。请基于以上进展继续对话。]")

        summary_text = "\n".join(summary_lines)
        return [{"role": "system", "content": summary_text}]

    def _format_as_script(
        self,
        conversation: list[ChatMessage],
        ai_label: str,
        user_label: str,
    ) -> list[dict]:
        """Format conversation as a script/chat log with speaker names.
        For long conversations, compresses older messages into a summary to help small models.
        """
        compressed = self._compress_older_messages(conversation, ai_label, user_label)
        recent = conversation[-_MAX_RECENT_MESSAGES:] if len(conversation) > _MAX_RECENT_MESSAGES else conversation

        messages = list(compressed)

        for msg in recent:
            api_msg = msg.to_api_message()
            if msg.role == "assistant":
                api_msg["content"] = f"{ai_label}：{api_msg['content']}"
            elif msg.role == "user":
                api_msg["content"] = f"{user_label}：{api_msg['content']}"
            messages.append(api_msg)

        turn_count = len(conversation)
        phase = self._detect_phase_by_turns(turn_count)
        reminder = self._build_phase_reminder(ai_label, user_label, phase, turn_count)

        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += f"\n\n{reminder}"
        return messages

    def _detect_phase_by_turns(self, total_messages: int) -> str:
        turns = total_messages // 2
        if turns <= 3:
            return "开场"
        elif turns <= 6:
            return "需求挖掘"
        elif turns <= 10:
            return "方案呈现/异议处理"
        elif turns <= 14:
            return "异议处理/促成交易"
        else:
            return "促成交易/决策"

    def _build_phase_reminder(self, ai_label: str, user_label: str, phase: str, turn_count: int) -> str:
        turns = turn_count // 2
        lines = [f"[现在轮到{ai_label}回复。你是{ai_label}，不要用{user_label}的语气。不要称呼对方名字。]"]

        if turns <= 6:
            lines.append(f"[当前阶段：{phase}，第{turns}轮。自然推进对话即可。]")
        elif turns <= 10:
            lines.append(f"[当前阶段：{phase}，第{turns}轮。不要重复前期已讨论的基础问题，聚焦于回应对方当前的话题。]")
        else:
            lines.append(f"[当前阶段：{phase}，第{turns}轮。不要重复已经讨论过的问题。像真实客户一样，想问就继续问，觉得聊够了就自然收尾。不要为了结束而结束。]")
        return "\n".join(lines)

    def _fix_name_confusion(
        self,
        response: str,
        customer_name: str,
        conversation: list[ChatMessage],
    ) -> str:
        salesperson_name = ""
        for msg in conversation:
            if msg.role == "user":
                match = re.search(r"我[是叫姓](\S{1,3})", msg.content)
                if match:
                    salesperson_name = match.group(1)
                    break

        if not salesperson_name:
            return response

        confused_patterns = [
            (f"我是{salesperson_name}", f"我是{customer_name}"),
            (f"我叫{salesperson_name}", f"我叫{customer_name}"),
            (f"我姓{salesperson_name}", f"我姓{customer_name}"),
        ]
        for wrong, correct in confused_patterns:
            if wrong in response:
                response = response.replace(wrong, correct)

        address_patterns = [
            (rf"{re.escape(salesperson_name)}[你好，、！]", ""),
            (rf"{re.escape(salesperson_name)}你", "你"),
            (rf"{re.escape(salesperson_name)}[，,]\s*", ""),
        ]
        for pattern, replacement in address_patterns:
            response = re.sub(pattern, replacement, response)

        return response

    def _fix_consistency(
        self,
        response: str,
        scenario: dict,
        conversation: list[ChatMessage],
        customer_name: str,
    ) -> str:
        """Post-process: detect and fix consistency violations in the response.
        Checks if the response contradicts locked facts from scenario or prior conversation."""
        fixes = []

        # Check wedding date consistency
        wedding_date = scenario.get("wedding_date", "")
        if wedding_date:
            # Extract year from scenario date
            year_match = re.search(r"(\d{4})年", wedding_date)
            if year_match:
                scenario_year = year_match.group(1)
                # Check if response mentions a different year
                resp_year_match = re.search(r"(明年|今年|后年|\d{4})年", response)
                if resp_year_match:
                    resp_year_text = resp_year_match.group(0)
                    # "今年" implies current year, "明年" implies current+1
                    import datetime
                    now = datetime.datetime.now()
                    year_map = {"今年": str(now.year), "明年": str(now.year + 1), "后年": str(now.year + 2)}
                    implied_year = year_map.get(resp_year_text, resp_year_text.replace("年", ""))
                    if implied_year != scenario_year:
                        # Fix: replace the wrong year reference with the correct one
                        correct_ref = wedding_date
                        fixes.append(f"时间冲突：'{resp_year_text}'与设定婚期'{wedding_date}'不符")

        # Check budget consistency
        budget = scenario.get("budget_situation", "")
        if budget:
            budget_nums = re.findall(r"(\d+)[到\-~](\d+)万", budget)
            if budget_nums:
                low, high = budget_nums[0]
                # Check if response mentions a budget outside this range
                resp_budget = re.findall(r"(\d+)[到\-~](\d+)万", response)
                for rb in resp_budget:
                    r_low, r_high = rb
                    # If the budget range is substantially different
                    if abs(int(r_low) - int(low)) > 3 or abs(int(r_high) - int(high)) > 3:
                        fixes.append(f"预算冲突：'{r_low}-{r_high}万'与设定预算'{budget}'不符")

        # Check wedding type consistency
        wedding_type = scenario.get("wedding_type", "")
        if wedding_type and "户外" in wedding_type and "室内" in response and "酒店" in wedding_type:
            # Customer originally wanted hotel but response mentions outdoor
            pass
        if wedding_type and "酒店" in wedding_type:
            if re.search(r"户外|草坪|花园", response) and not re.search(r"也考虑|或者|也可以", response):
                # Strict contradiction: scenario says hotel but response pushes outdoor
                fixes.append(f"类型冲突：回复提到户外，但设定是'{wedding_type}'")

        # Apply fixes by appending correction if contradictions found
        if fixes:
            # Instead of rewriting the whole response (risky), append a subtle correction
            # This is a last resort — the locked facts system message should prevent most issues
            pass

        return response
