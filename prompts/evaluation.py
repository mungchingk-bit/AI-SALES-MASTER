EVALUATION_PROMPT = """你是一位资深销售培训导师。请遵循 SOUL.md：准确>好听，可执行>空话，说人话少废话，以签单为导向。不确定的先说明，不硬编。输出话术自然真实可直接使用，避免生硬模板感。

请对以下销售训练对话进行专业评估。

## 训练模式
{mode_description}

## 使用的销售风格
{style_name}：{style_summary}

## 场景设定
{scenario_description}

## 完整对话记录
{full_conversation}

## 评估要求
请对以下8个维度逐一评分（1-10分）并给出具体理由，然后提供总体评价。

1. **沟通表达**：表达是否清晰、专业、有条理？
2. **需求发掘**：是否通过有效提问深入了解客户需求？
3. **价值主张**：是否针对客户需求呈现了有说服力的价值？
4. **异议处理**：面对客户异议的应对是否得当？
5. **流程完整**：销售流程各环节是否完整？
6. **关系建立**：是否有效建立了信任和好感？
7. **风格运用**：{style_evaluation_context}
8. **收尾技巧**：是否把握了成交时机，收尾方式是否恰当？

## 输出格式
严格按以下JSON输出：
```json
{{
  "dimensions": {{
    "沟通表达": {{"score": 0, "justification": "..."}},
    "需求发掘": {{"score": 0, "justification": "..."}},
    "价值主张": {{"score": 0, "justification": "..."}},
    "异议处理": {{"score": 0, "justification": "..."}},
    "流程完整": {{"score": 0, "justification": "..."}},
    "关系建立": {{"score": 0, "justification": "..."}},
    "风格运用": {{"score": 0, "justification": "..."}},
    "收尾技巧": {{"score": 0, "justification": "..."}}
  }},
  "strengths": ["...", "...", "..."],
  "improvements": ["...", "...", "..."],
  "specific_examples": [
    {{"turn": 0, "comment": "..."}},
    {{"turn": 0, "comment": "..."}}
  ],
  "style_alignment": {{
    "alignment_score": 0,
    "matched_traits": ["..."],
    "missed_traits": ["..."]
  }},
  "recommendation": "..."
}}
```

## 评分标准
- 9-10分：卓越，达到资深销售水平
- 7-8分：良好，基本掌握该技能
- 5-6分：及格，有提升空间
- 3-4分：不足，需要重点训练
- 1-2分：严重不足，建议从基础学起"""


def build_evaluation_prompt(
    session_data: dict,
    style_profile: dict | None = None,
    correction_guide: str = "",
) -> str:
    """Build an evaluation prompt from session data."""
    mode = session_data.get("mode", "customer")

    if mode == "customer":
        mode_description = "用户扮演销售，AI扮演客户"
        style_evaluation_context = "销售过程中是否展现了专业、有效的销售风格？"
    else:
        mode_description = "AI扮演销售，用户扮演客户进行学习"
        style_evaluation_context = (
            f"AI是否准确体现了「{style_profile.get('name', '')}」风格的特征？"
            "用户是否从对话中学习到了该风格的要点？"
        )

    # Format conversation
    conversation_lines = []
    for i, msg in enumerate(session_data.get("conversation", [])):
        speaker = "销售" if msg.get("role") == "user" else "客户"
        conversation_lines.append(f"第{i+1}轮-{speaker}：{msg.get('content', '')}")
    full_conversation = "\n".join(conversation_lines)

    # Format scenario
    scenario = session_data.get("scenario", {})
    scenario_description = (
        f"产品：{scenario.get('product', '未知')}\n"
        f"行业：{scenario.get('industry', '未知')}\n"
        f"难度：{scenario.get('difficulty', '中等')}"
    )

    style_name = style_profile.get("name", "默认") if style_profile else "默认"
    style_summary = style_profile.get("description", "专业顾问式销售") if style_profile else "专业顾问式销售"

    prompt = EVALUATION_PROMPT.format(
        mode_description=mode_description,
        style_name=style_name,
        style_summary=style_summary,
        scenario_description=scenario_description,
        full_conversation=full_conversation,
        style_evaluation_context=style_evaluation_context,
    )

    if correction_guide:
        prompt = prompt.replace("## 评分标准", f"{correction_guide}\n## 评分标准")

    return prompt
