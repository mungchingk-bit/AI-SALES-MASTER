SALES_SIMULATION_PROMPT = """你是一位经验丰富的销售高手，正在向客户销售{product}。你将严格按照"{style_name}"风格进行销售。

## 风格特征
{style_traits_formatted}

## 风格关键词句
- 常用表达：{key_phrases}
- 避免使用：{avoid_patterns}
- 节奏特点：{pacing}

## 公司与业务知识（你的专业支撑）
{company_context}

## 销售话术与策略参考（你的打法建议）
{script_context}

## 场景信息
- 客户：{customer_description}
- 当前对话阶段：{current_phase}
- 你在对话中的位置：第{turn_number}轮

## 行为规则
1. 严格体现上述风格特征，你的每句话都应符合该风格。
2. 遵循完整的销售流程：建立联系→发现需求→提出方案→处理异议→促成交易。
3. 你的回应应自然流畅，不要生硬地堆砌风格关键词。
4. 回复结束后，用<style_note>标签简要说明你的回应如何体现该风格（供学习者参考）。
   格式：<style_note>这里通过___的方式体现了___的风格特征</style_note>
5. 使用自然、专业的中文商务语言。"""


def build_sales_prompt(
    style_profile: dict,
    scenario: dict,
    current_phase: str = "开场",
    turn_number: int = 1,
) -> str:
    """Build a salesperson simulation system prompt from style and scenario."""
    traits = style_profile.get("extracted_traits", {})

    style_traits_formatted = "\n".join(
        f"- **{k}**：{v}" for k, v in traits.items()
        if k not in ("style_name", "style_summary", "key_phrases", "avoid_patterns", "pacing")
        and v
    )

    key_phrases = "、".join(traits.get("key_phrases", []))
    avoid_patterns = "、".join(traits.get("avoid_patterns", []))
    pacing = traits.get("pacing", "适中")

    from prompts.customer_simulation import _get_company_context, _get_script_context
    company_context = _get_company_context()
    script_context = _get_script_context()

    return SALES_SIMULATION_PROMPT.format(
        product=scenario.get("product", "产品"),
        style_name=style_profile.get("name", "专业销售"),
        style_traits_formatted=style_traits_formatted,
        key_phrases=key_phrases,
        avoid_patterns=avoid_patterns,
        pacing=pacing,
        company_context=company_context,
        script_context=script_context,
        customer_description=scenario.get("customer_description", "潜在客户"),
        current_phase=current_phase,
        turn_number=turn_number,
    )
