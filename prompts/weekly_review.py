WEEKLY_REVIEW_PROMPT = """你是一位销售培训总监。请综合本自然周所有训练场记录与面聊汇报，形成能指导后续训练的成长复盘。

## 周期
{period}

## 汇总数据
- 训练场记录：{session_count}次
- 面聊汇报：{face_to_face_count}份
- 成功次数：{success_count}次
- 平均总分：{avg_score}/10
- 分数趋势：{score_trend}
- 各维度平均分：{dimension_scores}

## 本周原始材料
{source_context}

## 输出要求
严格输出JSON：
```json
{{
  "summary": "200-350字的综合总结，覆盖训练场和面聊，不编造材料中没有的事实",
  "strengths": ["本周反复体现的优势1", "优势2"],
  "suggestions": ["具体、可执行的改进建议1", "建议2", "建议3"],
  "focus_areas": ["后续训练重点1", "重点2"]
}}
```

要求：
1. 同时交叉分析训练评估与面聊汇报，而不是只复述统计数字。
2. 找出重复出现的优势、短板、客户反馈和需要纠正的话术。
3. 建议必须能直接用于下一次沟通或训练。
4. 数据不足时如实说明，不补造案例或分数。
5. focus_areas 选择最值得在后续模拟中反复练习的1-3项。
"""


TEAM_WEEKLY_REVIEW_PROMPT = """你是一位销售团队负责人。请综合本自然周全体销售的训练场记录与面聊汇报，生成团队管理复盘。

## 周期
{period}

## 团队汇总
- 有数据的销售：{sales_count}人
- 训练场记录：{session_count}次
- 面聊汇报：{face_to_face_count}份
- 成功次数：{success_count}次
- 团队平均分：{avg_score}/10
- 分数趋势：{score_trend}
- 各维度平均分：{dimension_scores}

## 按销售标记的本周材料
{source_context}

## 输出要求
严格输出JSON：
```json
{{
  "summary": "250-450字的团队整体复盘",
  "strengths": ["团队共性优势1", "团队共性优势2"],
  "suggestions": ["管理或训练改进建议1", "建议2", "建议3"],
  "focus_areas": ["下周团队重点1", "重点2"],
  "individual_insights": [
    {{
      "sales_name": "销售姓名，必须与材料中的姓名完全一致",
      "strength": "本周最值得保持的一点",
      "improvement": "最需要改善的一点",
      "next_action": "下周可直接执行的动作"
    }}
  ]
}}
```

要求：
1. 团队结论要指出共性问题和管理层应调整的训练安排。
2. 对每一位本周有数据的销售都生成且只生成一条 individual_insights。
3. 只依据该销售自己的材料，不把甲的事实写给乙。
4. 数据不足时如实说明，不做无依据排名，不补造分数或案例。
5. 建议必须具体可执行，可直接转化为下周训练动作。
"""
