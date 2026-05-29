import gradio as gr
from datetime import datetime

import config

# Lazy-initialized singletons
_training_mgr = None
_style_store = None
_evaluator = None
_eval_store = None
_session_store = None


def _get_training_mgr():
    global _training_mgr
    if _training_mgr is None:
        from core.training_manager import TrainingManager
        _training_mgr = TrainingManager()
    return _training_mgr


def _get_style_store():
    global _style_store
    if _style_store is None:
        from storage.style_store import StyleStore
        _style_store = StyleStore()
    return _style_store


def _get_evaluator():
    global _evaluator
    if _evaluator is None:
        from core.evaluator import Evaluator
        _evaluator = Evaluator()
    return _evaluator


def _get_eval_store():
    global _eval_store
    if _eval_store is None:
        from storage.evaluation_store import EvaluationStore
        _eval_store = EvaluationStore()
    return _eval_store


def _get_session_store():
    global _session_store
    if _session_store is None:
        from storage.session_store import SessionStore
        _session_store = SessionStore()
    return _session_store


def _get_unfinished_choices(current_user=""):
    sessions = _get_session_store().list_all()
    choices = []
    for s in sessions:
        if s.status != "active":
            continue
        if current_user and s.user and s.user != current_user:
            continue
        mode_label = "销售练习" if s.mode == "customer" else "风格学习"
        turn_count = len(s.conversation) // 2
        choices.append(f"{s.started_at[:10]} | {mode_label} | 第{turn_count}轮 | {s.id[:8]}")
    return choices


def _get_history_data(current_user=""):
    sessions = _get_session_store().list_all()
    rows = []
    for s in sessions:
        if current_user and s.user and s.user != current_user:
            continue
        mode_label = "销售练习" if s.mode == "customer" else "风格学习"
        turn_count = len(s.conversation) // 2
        status_labels = {"active": "进行中", "completed": "已完成", "abandoned": "已放弃"}
        status_label = status_labels.get(s.status, s.status)
        recep = s.receptivity_history
        if recep and len(recep) >= 2:
            recep_text = f"{recep[0]}→{recep[-1]}"
        elif recep:
            recep_text = str(recep[0])
        else:
            recep_text = "-"
        end_labels = {"成功": "客户有意向", "离开": "客户离开", "考虑": "需再考虑", "红线": "触犯红线"}
        end_text = end_labels.get(s.end_reason, s.end_reason) if s.end_reason else "-"
        rows.append([s.started_at[:10], mode_label, status_label, turn_count, recep_text, end_text, s.id[:8]])
    return rows


def _get_history_choices(current_user=""):
    sessions = _get_session_store().list_all()
    choices = []
    for s in sessions:
        if s.status == "active":
            continue
        if current_user and s.user and s.user != current_user:
            continue
        mode_label = "销售练习" if s.mode == "customer" else "风格学习"
        status_labels = {"completed": "已完成", "abandoned": "已放弃"}
        status_label = status_labels.get(s.status, s.status)
        turn_count = len(s.conversation) // 2
        choices.append(f"{s.started_at[:10]} | {mode_label} | {status_label} | {turn_count}轮 | {s.id[:8]}")
    return choices


def _build_history_detail(session_id_short: str, current_user="") -> str:
    """Build a detailed view of a historical training session."""
    session = None
    sessions = _get_session_store().list_all()
    for s in sessions:
        if s.id.startswith(session_id_short):
            session = s
            break
    if not session:
        return "未找到该训练记录"

    lines = ["# 训练记录详情\n"]

    # Basic info
    mode_label = "销售练习（AI做客户）" if session.mode == "customer" else "风格学习（AI做销售）"
    lines.append(f"**模式**：{mode_label}")
    lines.append(f"**对话轮次**：{len(session.conversation) // 2}轮")
    status_labels = {"completed": "已完成", "abandoned": "已放弃", "active": "进行中"}
    lines.append(f"**状态**：{status_labels.get(session.status, session.status)}")

    if session.end_reason:
        end_labels = {"成功": "客户有意向", "离开": "客户离开", "考虑": "需再考虑", "红线": "触犯红线"}
        lines.append(f"**结束原因**：{end_labels.get(session.end_reason, session.end_reason)}")

    receptivity = session.receptivity_history
    if receptivity:
        lines.append(f"**客户接受度变化**：{receptivity[0]} → {receptivity[-1]}")

    if session.scenario:
        lines.append(f"\n**婚礼类型**：{session.scenario.get('wedding_type', '-')}")
        lines.append(f"**难度**：{session.scenario.get('difficulty', '-')}")

    lines.append(f"\n**开始时间**：{session.started_at}")
    if session.ended_at:
        lines.append(f"**结束时间**：{session.ended_at}")

    # Conversation replay
    if session.conversation:
        lines.append("\n---\n## 对话回放\n")
        for i, msg in enumerate(session.conversation):
            if msg.role == "user":
                lines.append(f"**销售**：{msg.content}")
            elif msg.role == "assistant":
                lines.append(f"**客户**：{msg.content}")
            lines.append("")

    # Check for evaluation report
    if session.evaluation_id:
        lines.append("\n---\n*该训练已有详细评估报告，请前往「评估报告」Tab查看雷达图和维度评分*")

    return "\n".join(lines)


def _parse_session_id(choice_text):
    if not choice_text:
        return None
    short_id = choice_text.split("|")[-1].strip()
    sessions = _get_session_store().list_all()
    for s in sessions:
        if s.id.startswith(short_id):
            return s.id
    return None


def _detect_phase_from_session(session):
    from core.training_manager import TrainingManager
    mgr = _get_training_mgr()
    return mgr._detect_phase(session)


def _format_receptivity(score) -> str:
    if isinstance(score, int) and score > 0:
        bar = "█" * score + "░" * (10 - score)
        return f"{bar} {score}/10"
    return "-"


def _format_session_summary(session, summary, report) -> str:
    lines = ["---\n# 本次对话实战总结\n"]
    turn_count = len(session.conversation) // 2
    receptivity = session.receptivity_history
    lines.append(f"**对话轮次**：{turn_count}轮")
    if receptivity:
        lines.append(f"**客户接受度变化**：{receptivity[0]} → {receptivity[-1]}")
        change = receptivity[-1] - receptivity[0]
        if change > 0:
            lines.append(f"**趋势**：上升 (+{change})")
        elif change < 0:
            lines.append(f"**趋势**：下降 ({change})")
        else:
            lines.append("**趋势**：持平")
    lines.append("")
    lines.append(summary)
    if report and report.deal_progression:
        dp = report.deal_progression
        lines.append("\n---\n## 签单路径分析\n")
        if dp.get("current_stage"):
            lines.append(f"**当前阶段**：{dp['current_stage']}")
        if dp.get("stage_progress"):
            lines.append(f"**推进进度**：{int(dp['stage_progress'] * 100)}%")
        if dp.get("blocking_issues"):
            lines.append("\n**当前阻碍**：")
            for issue in dp["blocking_issues"]:
                lines.append(f"- {issue}")
        if dp.get("next_steps"):
            lines.append("\n**下一步行动计划**：")
            for step in dp["next_steps"]:
                lines.append(f"\n{step.get('step', '?')}. **{step.get('action', '')}**")
                if step.get("script"):
                    lines.append(f"   - 建议话术：{step['script']}")
                if step.get("goal"):
                    lines.append(f"   - 目标：{step['goal']}")
        if dp.get("estimated_rounds_to_close"):
            lines.append(f"\n**预计还需沟通次数**：{dp['estimated_rounds_to_close']}次")
        if dp.get("risk_level"):
            lines.append(f"**风险等级**：{dp['risk_level']} — {dp.get('risk_reason', '')}")
        if dp.get("win_strategy"):
            lines.append(f"\n**赢单策略**：{dp['win_strategy']}")
    lines.append("\n---\n*完整评估报告（含雷达图）请前往「评估报告」Tab查看*")
    return "\n".join(lines)


def _format_brief_summary(session) -> str:
    """Generate a brief summary for ended/abandoned sessions without calling LLM."""
    lines = ["---\n# 本次训练汇总\n"]
    turn_count = len(session.conversation) // 2
    mode_label = "销售练习（AI做客户）" if session.mode == "customer" else "风格学习（AI做销售）"
    lines.append(f"**训练模式**：{mode_label}")
    lines.append(f"**对话轮次**：{turn_count}轮")

    receptivity = session.receptivity_history
    if receptivity:
        lines.append(f"**客户接受度变化**：{receptivity[0]} → {receptivity[-1]}")
        change = receptivity[-1] - receptivity[0]
        if change > 0:
            lines.append(f"**趋势**：上升 (+{change})")
        elif change < 0:
            lines.append(f"**趋势**：下降 ({change})")
        else:
            lines.append("**趋势**：持平")

    status_labels = {"completed": "已结束", "abandoned": "已放弃", "active": "进行中"}
    lines.append(f"**训练状态**：{status_labels.get(session.status, session.status)}")

    if session.end_reason:
        end_labels = {"成功": "客户有意向，对话成功结束", "离开": "客户失去耐心离开了", "考虑": "客户表示需要再考虑", "红线": "触犯红线，客户直接离开"}
        lines.append(f"**结束原因**：{end_labels.get(session.end_reason, session.end_reason)}")

    if session.scenario:
        lines.append(f"\n**婚礼类型**：{session.scenario.get('wedding_type', '-')}")
        lines.append(f"**难度**：{session.scenario.get('difficulty', '-')}")

    if session.started_at:
        lines.append(f"\n**开始时间**：{session.started_at}")
    if session.ended_at:
        lines.append(f"**结束时间**：{session.ended_at}")

    lines.append("\n---\n*详细评估报告（含雷达图）请前往「评估报告」Tab查看*")
    return "\n".join(lines)


def create_training_tab(user_dropdown=None):
    style_store = _get_style_store()

    current_session_id = gr.State(None)

    def get_style_choices():
        profiles = style_store.list_all()
        choices = ["不指定（默认顾问式）"]
        for p in profiles:
            choices.append(p.name)
        return choices

    def start_session(mode, style_name, wedding_type, difficulty, custom_notes, current_user):
        import random
        from prompts.customer_simulation import CUSTOMER_NAMES, WEDDING_DATES, BUDGETS, DECISION_AUTHORITIES, _pick_objections_for_difficulty

        training_mgr = _get_training_mgr()
        style_profile_id = None
        if style_name and style_name != "不指定（默认顾问式）":
            profiles = style_store.list_all()
            for p in profiles:
                if p.name == style_name:
                    style_profile_id = p.id
                    break

        scenario = {
            "product": "婚礼策划服务",
            "industry": "婚礼策划",
            "wedding_type": wedding_type or "酒店婚宴",
            "difficulty": difficulty or "medium",
            "custom_notes": custom_notes or "",
            "customer_name": random.choice(CUSTOMER_NAMES),
            "wedding_date": random.choice(WEDDING_DATES),
            "budget_situation": random.choice(BUDGETS),
            "decision_authority": random.choice(DECISION_AUTHORITIES),
            "primary_objections": "；".join(_pick_objections_for_difficulty(difficulty or "medium")),
        }

        if mode == "AI做销售，我学习":
            scenario["customer_description"] = f"正在筹备{wedding_type or '婚礼'}的备婚新人"

        session = training_mgr.create_session(
            mode="salesperson" if "学习" in mode else "customer",
            scenario=scenario,
            style_profile_id=style_profile_id,
        )
        session.user = current_user or ""
        training_mgr.session_store.save(session)

        if session.mode == "customer":
            training_mgr.session_store.save(session)
            chat_history = [{"role": "assistant", "content": "——— ✅ 已添加好友 ———"}]
            phase = "开场"
            receptivity_text = "-"
        else:
            chat_history = []
            phase = "开场"
            receptivity_text = "-"

        intro = "对方已通过你的微信好友请求，请主动打招呼开始对话！" if session.mode == "customer" else "训练已开始！请先说一句话作为客户开场，AI销售将回应你。"
        return (
            session.id, chat_history, phase, receptivity_text,
            gr.update(interactive=True), gr.update(interactive=True),
            gr.update(interactive=True),  # end_btn enabled
            gr.update(interactive=False), intro,
            gr.update(visible=False, value=""),
            gr.update(choices=_get_unfinished_choices(current_user), value=None),
            gr.update(choices=_get_history_choices(current_user), value=None),
        )

    def send_message(session_id, message, chat_history):
        if not session_id or not message.strip():
            return (chat_history, "", "开场", "-", gr.update(visible=False, value=""),
                    gr.update(interactive=True), gr.update(interactive=True), gr.update(interactive=True),
                    gr.update(choices=[]), gr.update(choices=[], value=None), gr.update(visible=False, value=""))
        training_mgr = _get_training_mgr()
        session = training_mgr.get_session(session_id)
        ai_response, style_note, receptivity, phase = training_mgr.process_user_message(
            session_id, message.strip()
        )
        chat_history.append({"role": "user", "content": message})

        end_reason = session.end_reason if session else ""
        if end_reason:
            end_labels = {"成功": "客户有意向，对话成功结束！", "离开": "客户失去耐心离开了", "考虑": "客户表示需要再考虑", "红线": "客户被触犯红线，直接离开"}
            ai_response += f"\n\n——— 对话结束：{end_labels.get(end_reason, end_reason)} ———"

        chat_history.append({"role": "assistant", "content": ai_response})
        receptivity_text = _format_receptivity(receptivity)

        current_user = session.user if session else ""

        # Session ended naturally — generate full evaluation summary
        if end_reason:
            # Show brief summary immediately
            brief = _format_brief_summary(session)
            return (
                chat_history, "", "已结束", receptivity_text,
                gr.update(visible=True, value=brief + "\n\n⏳ 正在生成详细测评报告，请稍候..."),
                gr.update(interactive=False), gr.update(interactive=False),
                gr.update(interactive=False),  # end_btn disabled
                gr.update(choices=_get_unfinished_choices(current_user), value=None),
                gr.update(choices=_get_history_choices(current_user), value=None),
                gr.update(visible=False, value=""),
            )

        # Normal continuation
        if style_note:
            note_update = gr.update(value=f"**风格注解**：{style_note}", visible=True)
        else:
            note_update = gr.update(visible=False, value="")

        return (
            chat_history, "", phase, receptivity_text, note_update,
            gr.update(interactive=True), gr.update(interactive=True),
            gr.update(interactive=True),  # end_btn stays enabled
            gr.update(choices=_get_unfinished_choices(current_user)),
            gr.update(choices=_get_history_choices(current_user), value=None),
            gr.update(visible=False, value=""),  # history_detail
        )

    def end_training(session_id):
        if not session_id:
            return ("没有进行中的训练", gr.update(interactive=True),
                    gr.update(visible=False, value=""),
                    gr.update(interactive=False),  # end_btn
                    gr.update(choices=[]), [])
        training_mgr = _get_training_mgr()
        evaluator = _get_evaluator()
        session = training_mgr.end_session(session_id)
        if not session:
            return ("结束训练失败", gr.update(interactive=True),
                    gr.update(visible=False, value=""),
                    gr.update(interactive=False),
                    gr.update(choices=[]), [])
        turn_count = len(session.conversation) // 2
        # Try to generate full evaluation, fall back to brief summary
        try:
            summary = evaluator.generate_summary_only(session_id)
            try:
                full_report = evaluator.evaluate(session_id)
            except Exception:
                full_report = None
            summary_md = _format_session_summary(session, summary, full_report)
        except Exception:
            summary_md = _format_brief_summary(session)
        current_user = session.user or ""
        return (
            f"训练已结束！共{turn_count}轮对话。实战总结已生成，请查看下方。",
            gr.update(interactive=True),  # start_btn
            gr.update(visible=True, value=summary_md),
            gr.update(interactive=False),  # end_btn disabled
            gr.update(choices=_get_unfinished_choices(current_user), value=None),
            gr.update(choices=_get_history_choices(current_user), value=None),
        )

    def resume_session(session_choice, current_user):
        session_id = _parse_session_id(session_choice)
        if not session_id:
            return (None, [], "未开始", "-", gr.update(interactive=False), gr.update(interactive=False),
                    gr.update(interactive=False), gr.update(interactive=True), "未找到会话", gr.update(visible=False, value=""))
        session = _get_session_store().load(session_id)
        if not session or session.status != "active":
            return (None, [], "未开始", "-", gr.update(interactive=False), gr.update(interactive=False),
                    gr.update(interactive=False), gr.update(interactive=True), "会话不存在或已结束", gr.update(visible=False, value=""))

        chat_history = [{"role": msg.role, "content": msg.content} for msg in session.conversation]
        phase = _detect_phase_from_session(session)
        recep = session.receptivity_history
        receptivity_text = _format_receptivity(recep[-1]) if recep else "-"
        status_msg = f"已恢复训练：{session.started_at[:10]} 开始的会话，当前第{len(session.conversation) // 2}轮"

        training_mgr = _get_training_mgr()
        training_mgr._active_sessions[session_id] = session

        return (
            session_id, chat_history, phase, receptivity_text,
            gr.update(interactive=True), gr.update(interactive=True),
            gr.update(interactive=True),  # end_btn enabled on resume
            gr.update(interactive=False), status_msg,
            gr.update(visible=False, value=""),
        )

    def abandon_session(session_choice, current_user):
        session_id = _parse_session_id(session_choice)
        if not session_id:
            return ("未选择会话", gr.update(choices=_get_unfinished_choices(current_user), value=None),
                    gr.update(choices=_get_history_choices(current_user), value=None), gr.update(visible=False, value=""))
        session = _get_session_store().load(session_id)
        if not session:
            return ("未找到会话", gr.update(choices=_get_unfinished_choices(current_user), value=None),
                    gr.update(choices=_get_history_choices(current_user), value=None), gr.update(visible=False, value=""))
        session.status = "abandoned"
        session.ended_at = datetime.now().isoformat()
        _get_session_store().save(session)
        training_mgr = _get_training_mgr()
        training_mgr._active_sessions.pop(session_id, None)
        # Generate brief summary for abandoned session
        brief = _format_brief_summary(session)
        return (
            f"已放弃训练：{session.started_at[:10]}，共{len(session.conversation) // 2}轮对话",
            gr.update(choices=_get_unfinished_choices(current_user), value=None),
            gr.update(choices=_get_history_choices(current_user), value=None),
            gr.update(visible=True, value=brief),
        )

    def refresh_unfinished(current_user=""):
        choices = _get_unfinished_choices(current_user)
        return gr.update(choices=choices, value=None)

    def refresh_history(current_user=""):
        choices = _get_history_choices(current_user)
        return gr.update(choices=choices, value=None)

    def view_history(session_choice, current_user):
        if not session_choice:
            return gr.update(visible=False, value="")
        short_id = session_choice.split("|")[-1].strip()
        detail = _build_history_detail(short_id, current_user)
        return gr.update(visible=True, value=detail)

    def generate_full_summary(session_id):
        """Generate full evaluation summary after the conversation ends.
        Only runs when the session is no longer active — skipped as no-op otherwise."""
        if not session_id:
            return gr.update(), gr.update()
        session = _get_session_store().load(session_id)
        if not session:
            return gr.update(), gr.update()
        # Session still active — no-op (avoid LLM calls on every normal message)
        if session.status == "active":
            return gr.update(), gr.update()
        try:
            evaluator = _get_evaluator()
            summary = evaluator.generate_summary_only(session_id)
            try:
                full_report = evaluator.evaluate(session_id)
            except Exception:
                full_report = None
            summary_md = _format_session_summary(session, summary, full_report)
        except Exception:
            summary_md = _format_brief_summary(session)
        current_user = session.user or ""
        return (
            gr.update(visible=True, value=summary_md),
            gr.update(choices=_get_history_choices(current_user), value=None),
        )

    # --- UI Components ---
    gr.Markdown("## 训练场")
    gr.Markdown("选择模式开始销售实战训练，AI将模拟真实客户或销售与你对练。\n结束训练后将自动生成实战总结，帮你诊断问题、校正方向、规划签单路径。")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 训练配置")
            mode_radio = gr.Radio(
                choices=["AI做客户，我练销售", "AI做销售，我学习"],
                value="AI做客户，我练销售", label="训练模式",
            )
            style_dropdown = gr.Dropdown(
                choices=get_style_choices(), value="不指定（默认顾问式）", label="销售风格",
            )
            wedding_type_dropdown = gr.Dropdown(
                choices=["酒店婚宴", "户外草坪婚礼", "小型精品婚礼", "目的地婚礼"],
                value="酒店婚宴", label="婚礼类型",
            )
            difficulty_radio = gr.Radio(
                choices=[("简单", "easy"), ("中等", "medium"), ("困难", "hard")],
                value="medium", label="难度",
            )
            custom_notes = gr.Textbox(
                label="场景备注（可选）", placeholder="如：客户预算有限、时间紧迫等", lines=2,
            )
            start_btn = gr.Button("开始训练", variant="primary")
            status_text = gr.Textbox(label="状态", interactive=False, lines=2)

            # --- 未完成训练恢复区域 ---
            gr.Markdown("### 恢复未完成训练")
            unfinished_dropdown = gr.Dropdown(
                choices=_get_unfinished_choices(), label="未完成的训练", interactive=True,
            )
            with gr.Row():
                resume_btn = gr.Button("恢复训练", variant="secondary")
                abandon_btn = gr.Button("放弃训练", variant="stop")

        with gr.Column(scale=2):
            gr.Markdown("### 对话区域")
            with gr.Row():
                phase_display = gr.Textbox(label="当前阶段", value="未开始", interactive=False, scale=1)
                receptivity_display = gr.Textbox(label="客户接受度", value="-", interactive=False, scale=1)
            chatbot = gr.Chatbot(height=400)
            style_note_display = gr.Markdown(visible=False)
            with gr.Row():
                msg_input = gr.Textbox(label="输入消息", placeholder="输入你的回复...", scale=4, interactive=False)
                send_btn = gr.Button("发送", variant="primary", scale=1, interactive=False)
                end_btn = gr.Button("结束训练", scale=1, interactive=False)

    summary_display = gr.Markdown(visible=False, value="")

    # --- 训练历史 ---
    with gr.Accordion("训练历史", open=True):
        with gr.Row():
            history_dropdown = gr.Dropdown(
                choices=_get_history_choices(), label="选择历史训练记录", interactive=True, scale=4,
            )
            history_refresh_btn = gr.Button("刷新", scale=1)
            view_history_btn = gr.Button("查看详情", variant="primary", scale=1)
        history_detail = gr.Markdown(visible=False, value="")

    # --- Event bindings ---
    start_btn.click(
        fn=start_session,
        inputs=[mode_radio, style_dropdown, wedding_type_dropdown, difficulty_radio, custom_notes, user_dropdown],
        outputs=[current_session_id, chatbot, phase_display, receptivity_display,
                 msg_input, send_btn, end_btn, start_btn, status_text, summary_display,
                 unfinished_dropdown, history_dropdown],
    )
    send_btn.click(
        fn=send_message,
        inputs=[current_session_id, msg_input, chatbot],
        outputs=[chatbot, msg_input, phase_display, receptivity_display, summary_display, msg_input, send_btn, end_btn, unfinished_dropdown, history_dropdown, history_detail],
    ).then(
        fn=generate_full_summary,
        inputs=[current_session_id],
        outputs=[summary_display, history_dropdown],
    )
    msg_input.submit(
        fn=send_message,
        inputs=[current_session_id, msg_input, chatbot],
        outputs=[chatbot, msg_input, phase_display, receptivity_display, summary_display, msg_input, send_btn, end_btn, unfinished_dropdown, history_dropdown, history_detail],
    ).then(
        fn=generate_full_summary,
        inputs=[current_session_id],
        outputs=[summary_display, history_dropdown],
    )
    end_btn.click(
        fn=end_training,
        inputs=[current_session_id],
        outputs=[status_text, start_btn, summary_display, end_btn, unfinished_dropdown, history_dropdown],
    )
    resume_btn.click(
        fn=resume_session,
        inputs=[unfinished_dropdown, user_dropdown],
        outputs=[current_session_id, chatbot, phase_display, receptivity_display,
                 msg_input, send_btn, end_btn, start_btn, status_text, summary_display],
    )
    abandon_btn.click(
        fn=abandon_session,
        inputs=[unfinished_dropdown, user_dropdown],
        outputs=[status_text, unfinished_dropdown, history_dropdown, summary_display],
    )
    history_refresh_btn.click(
        fn=refresh_history,
        inputs=[user_dropdown],
        outputs=[history_dropdown],
    )
    view_history_btn.click(
        fn=view_history,
        inputs=[history_dropdown, user_dropdown],
        outputs=[history_detail],
    )
