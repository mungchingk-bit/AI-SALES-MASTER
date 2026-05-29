CONVERSATION_SUMMARY_PROMPT = """你是一位资深销售实战教练。请遵循 SOUL.md：准确>好听，可执行>空话，说人话少废话，以签单为导向而不是只做分析。不确定的先说明，不硬编。输出话术要自然真实可直接使用，避免生硬模板感。

刚刚结束了一场销售对话，请你基于对话内容进行实战复盘总结，帮助销售人员成长。

## 对话场景
- 产品：{product}
- 客户行业：{industry}
- 对话类型：{conversation_type}
- 对话轮次：{turn_count}轮

## 完整对话记录
{full_conversation}

## 客户接受度变化轨迹
{receptivity_trajectory}

---

请你严格按照以下结构输出复盘总结，用中文，语气直接、有针对性、可执行，不要空话套话：

### 一、本次对话回顾
用3-5句话概括这次对话的整体走向：从哪里开始、经历了什么、到哪一步结束的。

### 二、做得好的地方
列出本次对话中销售表现优秀的2-3个亮点，每个包含：
- 做了什么
- 为什么这样做是对的
- 产生了什么好的效果

### 三、需要改进的地方
逐条列出本次对话中暴露出的具体问题，每条包含：
- 问题描述
- 出现在哪一轮
- 为什么这是个问题
- 正确的做法应该是什么（给出具体话术示例）

### 四、关键转折点
找出对话中2-3个关键转折点（好的或坏的），每个转折点说明：
- 发生在哪一轮
- 说了什么
- 产生了什么影响（客户态度变化）

### 五、成交路径分析
根据当前对话进展，分析：
1. **当前处于成交漏斗的哪个阶段**（初次接触→需求确认→方案沟通→商务谈判→签单成交）
2. **距离签单还差几步**，每一步具体要做什么
3. **客户当前最大的顾虑是什么**，如何化解
4. **下一次接触时应该说什么**（给出开场话术和推进策略）
5. **预计还需要几次沟通才能签单**，每次的核心目标是什么

### 六、本次核心收获
用一句话总结：这次对话最大的一个教训或进步是什么？"""

DEAL_PROGRESSION_PROMPT = """你是一位销售流程分析专家。遵循 SOUL.md：以成交为导向，所有建议必须推进转化而不停留在描述问题。输出的话术要自然真实可直接使用。不确定的先说明，不硬编。

请根据以下对话记录，分析当前交易推进状态，并给出明确的下一步行动计划。

## 对话场景
- 产品：{product}
- 行业：{industry}

## 对话记录
{full_conversation}

## 客户接受度变化
初始 → {receptivity_start}，最终 → {receptivity_end}

---

请用JSON格式输出：
```json
{{
  "current_stage": "初次接触|需求确认|方案沟通|商务谈判|签单成交",
  "stage_progress": 0.0,
  "blocking_issues": ["阻碍成交的当前问题1", "问题2"],
  "next_steps": [
    {{
      "step": 1,
      "action": "具体行动",
      "script": "建议话术",
      "goal": "这步要达成的目标"
    }}
  ],
  "estimated_rounds_to_close": 0,
  "risk_level": "低|中|高",
  "risk_reason": "风险原因",
  "win_strategy": "整体赢单策略概述"
}}
```"""


def build_conversation_summary_prompt(
    session_data: dict,
) -> str:
    """Build a conversation summary prompt."""
    scenario = session_data.get("scenario", {})
    mode = session_data.get("mode", "customer")

    # Determine conversation type
    if mode == "customer":
        conversation_type = "面聊/线上对话（销售练习）"
    else:
        conversation_type = "风格学习对话"

    # Format conversation
    conversation_lines = []
    for i, msg in enumerate(session_data.get("conversation", [])):
        speaker = "销售" if msg.get("role") == "user" else "客户"
        conversation_lines.append(f"第{i+1}轮-{speaker}：{msg.get('content', '')}")
    full_conversation = "\n".join(conversation_lines)

    # Format receptivity trajectory
    receptivity = session_data.get("receptivity_history", [])
    if receptivity:
        trajectory_parts = []
        for i, score in enumerate(receptivity):
            trajectory_parts.append(f"第{i+1}次回应后：{score}/10")
        trajectory = " → ".join([str(s) for s in receptivity])
        trajectory += "\n" + "\n".join(trajectory_parts)
    else:
        trajectory = "未追踪"

    turn_count = len(session_data.get("conversation", [])) // 2

    return CONVERSATION_SUMMARY_PROMPT.format(
        product=scenario.get("product", "产品"),
        industry=scenario.get("industry", "行业"),
        conversation_type=conversation_type,
        turn_count=turn_count,
        full_conversation=full_conversation,
        receptivity_trajectory=trajectory,
    )


def build_deal_progression_prompt(
    session_data: dict,
) -> str:
    """Build a deal progression analysis prompt."""
    scenario = session_data.get("scenario", {})

    # Format conversation
    conversation_lines = []
    for i, msg in enumerate(session_data.get("conversation", [])):
        speaker = "销售" if msg.get("role") == "user" else "客户"
        conversation_lines.append(f"第{i+1}轮-{speaker}：{msg.get('content', '')}")
    full_conversation = "\n".join(conversation_lines)

    receptivity = session_data.get("receptivity_history", [])
    receptivity_start = str(receptivity[0]) if receptivity else "未知"
    receptivity_end = str(receptivity[-1]) if receptivity else "未知"

    return DEAL_PROGRESSION_PROMPT.format(
        product=scenario.get("product", "产品"),
        industry=scenario.get("industry", "行业"),
        full_conversation=full_conversation,
        receptivity_start=receptivity_start,
        receptivity_end=receptivity_end,
    )
