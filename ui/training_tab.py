import gradio as gr

from core.training_manager import TrainingManager
from core.evaluator import Evaluator
from core.role_engine import RoleEngine
from storage.style_store import StyleStore
from storage.evaluation_store import EvaluationStore

import config


def create_training_tab() -> gr.Blocks:
    training_mgr = TrainingManager()
    style_store = StyleStore()
    evaluator = Evaluator()
    eval_store = EvaluationStore()

    # State
    current_session_id = gr.State(None)

    def get_style_choices():
        profiles = style_store.list_all()
        choices = ["不指定（默认顾问式）"]
        for p in profiles:
            choices.append(p.name)
        return choices

    def start_session(mode, style_name, wedding_type, difficulty, custom_notes):
        """Start a new training session."""
        # Find style profile ID
        style_profile_id = None
        if style_name and style_name != "不指定（默认顾问式）":
            profiles = style_store.list_all()
            for p in profiles:
                if p.name == style_name:
                    style_profile_id = p.id
                    break

        # Build scenario (婚礼行业)
        scenario = {
            "product": "婚礼策划服务",
            "industry": "婚礼策划",
            "wedding_type": wedding_type or "酒店婚宴",
            "difficulty": difficulty or "medium",
            "custom_notes": custom_notes or "",
        }

        # Add customer description for sales mode
        if mode == "AI做销售，我学习":
            scenario["customer_description"] = (
                f"正在筹备{wedding_type or '婚礼'}的备婚新人"
            )

        session = training_mgr.create_session(
            mode="salesperson" if "销售" in mode and "学习" in mode else "customer",
            scenario=scenario,
            style_profile_id=style_profile_id,
        )

        # Generate opening message
        if session.mode == "customer":
            # AI as customer sends the first message
            role_engine = RoleEngine()
            ai_response, receptivity = role_engine.generate_customer_response(
                conversation=session.conversation,
                scenario=session.scenario,
            )
            session.add_message(role="assistant", content=ai_response)
            session.receptivity_history.append(receptivity)
            training_mgr.session_store.save(session)

            chat_history = [{"role": "assistant", "content": ai_response}]
            phase = "开场"
            receptivity_text = _format_receptivity(receptivity)
            return (
                session.id, chat_history, phase, receptivity_text,
                gr.update(interactive=True), gr.update(interactive=True),
                gr.update(interactive=False), "训练已开始！AI正在扮演客户，请开始你的销售对话。",
                gr.update(visible=False, value=""),
            )
        else:
            # AI as salesperson - user plays customer, AI starts
            intro = "训练已开始！请先说一句话作为客户开场，AI销售将回应你。"
            return (
                session.id, [], "开场", "-",
                gr.update(interactive=True), gr.update(interactive=True),
                gr.update(interactive=False), intro,
                gr.update(visible=False, value=""),
            )

    def send_message(session_id, message, chat_history):
        """Send a message in the training session."""
        if not session_id or not message.strip():
            return chat_history, "", "开场", "-", gr.update(visible=False, value="")

        ai_response, style_note, receptivity, phase = training_mgr.process_user_message(
            session_id, message.strip()
        )

        # Update chat history
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": ai_response})

        # Format receptivity
        receptivity_text = _format_receptivity(receptivity)

        # Build style note display
        if style_note:
            note_update = gr.update(value=f"**风格注解**：{style_note}", visible=True)
        else:
            note_update = gr.update(visible=False, value="")

        return chat_history, "", phase, receptivity_text, note_update

    def end_training(session_id):
        """End the current training session and generate immediate summary."""
        if not session_id:
            return "没有进行中的训练", gr.update(interactive=True), gr.update(visible=False, value="")

        session = training_mgr.end_session(session_id)
        if not session:
            return "结束训练失败", gr.update(interactive=True), gr.update(visible=False, value="")

        turn_count = len(session.conversation) // 2

        # Generate immediate conversation summary
        summary = evaluator.generate_summary_only(session_id)

        # Also trigger full evaluation in background
        try:
            full_report = evaluator.evaluate(session_id)
        except Exception:
            full_report = None

        # Build the summary display
        summary_md = _format_session_summary(session, summary, full_report)

        return (
            f"训练已结束！共{turn_count}轮对话。实战总结已生成，请查看下方。",
            gr.update(interactive=True),
            gr.update(visible=True, value=summary_md),
        )

    def _format_receptivity(score) -> str:
        if isinstance(score, int) and score > 0:
            bar = "█" * score + "░" * (10 - score)
            return f"{bar} {score}/10"
        return "-"

    def _format_session_summary(session, summary: str, report) -> str:
        """Format the post-session summary for display."""
        lines = ["---\n# 本次对话实战总结\n"]

        # Quick stats
        turn_count = len(session.conversation) // 2
        receptivity = session.receptivity_history
        lines.append(f"**对话轮次**：{turn_count}轮")
        if receptivity:
            lines.append(f"**客户接受度变化**：{receptivity[0] if receptivity else '-'} → {receptivity[-1] if receptivity else '-'}")
            change = receptivity[-1] - receptivity[0] if receptivity else 0
            if change > 0:
                lines.append(f"**趋势**：上升 (+{change})")
            elif change < 0:
                lines.append(f"**趋势**：下降 ({change})")
            else:
                lines.append("**趋势**：持平")
        lines.append("")

        # Conversation summary
        lines.append(summary)

        # Deal progression if available
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

    with gr.Blocks() as tab:
        gr.Markdown("## 训练场")
        gr.Markdown("选择模式开始销售实战训练，AI将模拟真实客户或销售与你对练。\n结束训练后将自动生成实战总结，帮你诊断问题、校正方向、规划签单路径。")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 训练配置")
                mode_radio = gr.Radio(
                    choices=["AI做客户，我练销售", "AI做销售，我学习"],
                    value="AI做客户，我练销售",
                    label="训练模式",
                )
                style_dropdown = gr.Dropdown(
                    choices=get_style_choices(),
                    value="不指定（默认顾问式）",
                    label="销售风格",
                )
                wedding_type_dropdown = gr.Dropdown(
                    choices=["酒店婚宴", "户外草坪婚礼", "小型精品婚礼", "目的地婚礼"],
                    value="酒店婚宴",
                    label="婚礼类型",
                )
                difficulty_radio = gr.Radio(
                    choices=[("简单", "easy"), ("中等", "medium"), ("困难", "hard")],
                    value="medium",
                    label="难度",
                )
                custom_notes = gr.Textbox(
                    label="场景备注（可选）", placeholder="如：客户预算有限、时间紧迫等", lines=2
                )
                start_btn = gr.Button("开始训练", variant="primary")
                status_text = gr.Textbox(label="状态", interactive=False, lines=2)

            with gr.Column(scale=2):
                gr.Markdown("### 对话区域")
                with gr.Row():
                    phase_display = gr.Textbox(label="当前阶段", value="未开始", interactive=False, scale=1)
                    receptivity_display = gr.Textbox(label="客户接受度", value="-", interactive=False, scale=1)
                chatbot = gr.Chatbot(height=400)
                style_note_display = gr.Markdown(visible=False)

                with gr.Row():
                    msg_input = gr.Textbox(
                        label="输入消息",
                        placeholder="输入你的回复...",
                        scale=4,
                        interactive=False,
                    )
                    send_btn = gr.Button("发送", variant="primary", scale=1, interactive=False)
                    end_btn = gr.Button("结束训练", scale=1, interactive=False)

        # 实战总结区域 - 结束训练后展开
        summary_display = gr.Markdown(visible=False, value="")

        # Event handlers
        start_btn.click(
            fn=start_session,
            inputs=[mode_radio, style_dropdown, wedding_type_dropdown, difficulty_radio, custom_notes],
            outputs=[current_session_id, chatbot, phase_display, receptivity_display,
                     msg_input, send_btn, start_btn, status_text, summary_display],
        )

        send_btn.click(
            fn=send_message,
            inputs=[current_session_id, msg_input, chatbot],
            outputs=[chatbot, msg_input, phase_display, receptivity_display, style_note_display],
        )

        msg_input.submit(
            fn=send_message,
            inputs=[current_session_id, msg_input, chatbot],
            outputs=[chatbot, msg_input, phase_display, receptivity_display, style_note_display],
        )

        end_btn.click(
            fn=end_training,
            inputs=[current_session_id],
            outputs=[status_text, start_btn, summary_display],
        )

        # Refresh style choices on load
        tab.load(fn=lambda: gr.update(choices=get_style_choices()), outputs=[style_dropdown])

    return tab
