import gradio as gr
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

# Lazy singletons
_evaluator = None
_eval_store = None
_session_store = None


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


def create_evaluation_tab(user_dropdown=None) -> None:
    session_store = _get_session_store()

    def get_session_choices(current_user=""):
        sessions = session_store.list_all()
        choices = []
        for s in sessions:
            if s.status != "completed":
                continue
            # Filter by user if specified
            if current_user and s.user and s.user != current_user:
                continue
            mode_label = "销售练习" if s.mode == "customer" else "风格学习"
            user_tag = f"[{s.user}] " if s.user else ""
            choices.append(f"{user_tag}{s.started_at[:10]} | {mode_label} | {s.id[:8]}")
        return choices

    def generate_evaluation(session_choice):
        if not session_choice:
            return None, "请选择训练记录", "", ""
        session_id = session_choice.split("|")[-1].strip()
        sessions = session_store.list_all()
        full_id = None
        for s in sessions:
            if s.id.startswith(session_id):
                full_id = s.id
                break
        if not full_id:
            return None, "未找到训练记录", "", ""
        existing = _get_eval_store().load_by_session(full_id)
        if existing:
            report = existing
        else:
            report = _get_evaluator().evaluate(full_id)
        if not report:
            return None, "评估生成失败", "", ""
        chart = _generate_radar_chart(report)
        report_text = _format_dimension_report(report)
        summary_text = _format_summary(report)
        progression_text = _format_deal_progression(report)
        return chart, report_text, summary_text, progression_text

    def _generate_radar_chart(report):
        dimensions = list(report.dimension_scores.keys())
        scores = [report.dimension_scores[d].get("score", 0) for d in dimensions]
        if not dimensions or not scores:
            return None
        N = len(dimensions)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        scores_plot = scores + [scores[0]]
        angles += [angles[0]]
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        ax.fill(angles, scores_plot, color="#4CAF50", alpha=0.25)
        ax.plot(angles, scores_plot, color="#4CAF50", linewidth=2)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(dimensions, fontsize=11)
        ax.set_ylim(0, 10)
        ax.set_yticks([2, 4, 6, 8, 10])
        ax.set_yticklabels(["2", "4", "6", "8", "10"], fontsize=8)
        ax.set_title(f"综合评分：{report.overall_score}/10", fontsize=14, fontweight="bold", pad=20)
        plt.tight_layout()
        return fig

    def _format_dimension_report(report):
        lines = [f"## 综合评分：{report.overall_score}/10\n"]
        lines.append("### 各维度评分\n")
        for dim, data in report.dimension_scores.items():
            score = data.get("score", 0)
            justification = data.get("justification", "")
            bar = "●" * score + "○" * (10 - score)
            lines.append(f"**{dim}**：{bar} {score}/10")
            lines.append(f"  {justification}\n")
        if report.strengths:
            lines.append("### 优势总结\n")
            for i, s in enumerate(report.strengths, 1):
                lines.append(f"{i}. {s}")
            lines.append("")
        if report.improvements:
            lines.append("### 改进建议\n")
            for i, s in enumerate(report.improvements, 1):
                lines.append(f"{i}. {s}")
            lines.append("")
        if report.style_alignment:
            lines.append("### 风格契合度\n")
            sa = report.style_alignment
            if sa.get("alignment_score") is not None:
                lines.append(f"契合度评分：{sa['alignment_score']}/10")
            if sa.get("matched_traits"):
                lines.append(f"契合特征：{', '.join(sa['matched_traits'])}")
            if sa.get("missed_traits"):
                lines.append(f"缺失特征：{', '.join(sa['missed_traits'])}")
            lines.append("")
        if report.specific_examples:
            lines.append("### 具体对话点评\n")
            for ex in report.specific_examples:
                turn = ex.get("turn", "?")
                comment = ex.get("comment", "")
                lines.append(f"- 第{turn}轮：{comment}")
            lines.append("")
        return "\n".join(lines)

    def _format_summary(report):
        if not report.conversation_summary:
            return "暂无实战总结"
        return report.conversation_summary

    def _format_deal_progression(report):
        dp = report.deal_progression
        if not dp:
            return "暂无签单路径分析"
        lines = ["## 签单路径分析\n"]
        if dp.get("current_stage"):
            lines.append(f"**当前阶段**：{dp['current_stage']}")
        if dp.get("stage_progress"):
            progress_pct = int(dp['stage_progress'] * 100)
            filled = "█" * (progress_pct // 10) + "░" * (10 - progress_pct // 10)
            lines.append(f"**推进进度**：{filled} {progress_pct}%")
        if dp.get("risk_level"):
            risk_icon = {"低": "✅", "中": "⚠️", "高": "🔴"}.get(dp["risk_level"], "")
            lines.append(f"**风险等级**：{risk_icon} {dp['risk_level']}")
            if dp.get("risk_reason"):
                lines.append(f"  原因：{dp['risk_reason']}")
        if dp.get("blocking_issues"):
            lines.append("\n### 当前阻碍\n")
            for issue in dp["blocking_issues"]:
                lines.append(f"- {issue}")
        if dp.get("next_steps"):
            lines.append("\n### 下一步行动计划\n")
            for step in dp["next_steps"]:
                lines.append(f"\n**第{step.get('step', '?')}步：{step.get('action', '')}**")
                if step.get("script"):
                    lines.append(f"- 建议话术：{step['script']}")
                if step.get("goal"):
                    lines.append(f"- 目标：{step['goal']}")
        if dp.get("estimated_rounds_to_close"):
            lines.append(f"\n**预计还需沟通**：{dp['estimated_rounds_to_close']}次")
        if dp.get("win_strategy"):
            lines.append(f"\n### 赢单策略\n{dp['win_strategy']}")
        return "\n".join(lines)

    # --- Share functions ---
    current_eval_report = gr.State(None)

    def generate_and_store_evaluation(session_choice):
        chart, report_text, summary_text, progression_text = generate_evaluation(session_choice)
        # Build share checkboxes
        section_choices = []
        section_defaults = []
        if session_choice:
            session_id = session_choice.split("|")[-1].strip()
            sessions = session_store.list_all()
            full_id = None
            for s in sessions:
                if s.id.startswith(session_id):
                    full_id = s.id
                    break
            if full_id:
                report = _get_eval_store().load_by_session(full_id)
                if report:
                    if report.dimension_scores:
                        section_choices.append("各维度评分")
                        section_defaults.append("各维度评分")
                    if report.strengths:
                        section_choices.append("优势总结")
                        section_defaults.append("优势总结")
                    if report.improvements:
                        section_choices.append("改进建议")
                        section_defaults.append("改进建议")
                    if report.style_alignment:
                        section_choices.append("风格契合度")
                    if report.conversation_summary:
                        section_choices.append("实战总结")
                        section_defaults.append("实战总结")
                    if report.deal_progression:
                        section_choices.append("签单路径分析")
                        section_defaults.append("签单路径分析")
                    return chart, report_text, summary_text, progression_text, report, gr.update(choices=section_choices, value=section_defaults)
        return chart, report_text, summary_text, progression_text, None, gr.update(choices=[], value=[])

    def _build_eval_selected_md(report, selected_items):
        """根据勾选项构建评估报告 Markdown。"""
        if not report or not selected_items:
            return ""
        lines = ["# 训练评估报告\n"]
        lines.append(f"**综合评分**：{report.overall_score}/10\n")

        if "各维度评分" in selected_items and report.dimension_scores:
            lines.append("## 各维度评分\n")
            for dim, data in report.dimension_scores.items():
                score = data.get("score", 0)
                bar = "●" * score + "○" * (10 - score)
                lines.append(f"**{dim}**：{bar} {score}/10")
                lines.append(f"  {data.get('justification', '')}\n")

        if "优势总结" in selected_items and report.strengths:
            lines.append("## 优势总结")
            for i, s in enumerate(report.strengths, 1):
                lines.append(f"{i}. {s}")
            lines.append("")

        if "改进建议" in selected_items and report.improvements:
            lines.append("## 改进建议")
            for i, s in enumerate(report.improvements, 1):
                lines.append(f"{i}. {s}")
            lines.append("")

        if "风格契合度" in selected_items and report.style_alignment:
            sa = report.style_alignment
            lines.append("## 风格契合度")
            if sa.get("alignment_score") is not None:
                lines.append(f"契合度评分：{sa['alignment_score']}/10")
            if sa.get("matched_traits"):
                lines.append(f"契合特征：{', '.join(sa['matched_traits'])}")
            if sa.get("missed_traits"):
                lines.append(f"缺失特征：{', '.join(sa['missed_traits'])}")
            lines.append("")

        if "实战总结" in selected_items and report.conversation_summary:
            lines.append("## 实战总结\n")
            lines.append(report.conversation_summary)
            lines.append("")

        dp = report.deal_progression
        if "签单路径分析" in selected_items and dp:
            lines.append("## 签单路径分析\n")
            if dp.get("current_stage"):
                lines.append(f"**当前阶段**：{dp['current_stage']}")
            if dp.get("stage_progress"):
                progress_pct = int(dp["stage_progress"] * 100)
                lines.append(f"**推进进度**：{progress_pct}%")
            if dp.get("risk_level"):
                lines.append(f"**风险等级**：{dp['risk_level']}")
            if dp.get("blocking_issues"):
                lines.append("\n### 当前阻碍")
                for issue in dp["blocking_issues"]:
                    lines.append(f"- {issue}")
            if dp.get("next_steps"):
                lines.append("\n### 下一步行动计划")
                for step in dp["next_steps"]:
                    lines.append(f"\n**第{step.get('step', '?')}步：{step.get('action', '')}**")
                    if step.get("script"):
                        lines.append(f"- 建议话术：{step['script']}")
                    if step.get("goal"):
                        lines.append(f"- 目标：{step['goal']}")
            if dp.get("win_strategy"):
                lines.append(f"\n### 赢单策略\n{dp['win_strategy']}")

        return "\n".join(lines)

    def eval_share_copy(report, selected_items):
        if not report:
            return "请先生成评估报告"
        if not selected_items:
            return "请勾选要分享的内容"
        return _build_eval_selected_md(report, selected_items)

    def eval_share_docx(report, selected_items):
        if not report or not selected_items:
            return None
        md = _build_eval_selected_md(report, selected_items)
        if not md.strip():
            return None
        from utils.share import export_as_docx
        return export_as_docx(md, title="训练评估报告")

    def eval_share_image(report, selected_items):
        if not report or not selected_items:
            return None
        md = _build_eval_selected_md(report, selected_items)
        if not md.strip():
            return None
        from utils.share import generate_image
        return generate_image(md, title="训练评估报告")

    def eval_share_link(report, selected_items):
        if not report:
            return "请先生成评估报告"
        if not selected_items:
            return "请勾选要分享的内容"
        md = _build_eval_selected_md(report, selected_items)
        from utils.share import generate_share_link
        return generate_share_link(md, title="训练评估报告")

    gr.Markdown("## 评估报告")
    gr.Markdown("选择已完成的训练记录，查看实战总结、评分和签单路径分析。")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 选择训练记录")
            session_dropdown = gr.Dropdown(choices=get_session_choices(), label="训练记录")
            refresh_sessions_btn = gr.Button("刷新记录", scale=1)
            eval_btn = gr.Button("查看评估", variant="primary")
        with gr.Column(scale=2):
            radar_chart = gr.Plot(label="评分雷达图")

    with gr.Tabs():
        with gr.Tab("实战总结"):
            summary_display = gr.Markdown()
        with gr.Tab("维度评分"):
            report_display = gr.Markdown()
        with gr.Tab("签单路径"):
            progression_display = gr.Markdown()

    gr.Markdown("### 分享报告")
    eval_share_select = gr.CheckboxGroup(label="选择要分享的内容", choices=[], value=[])
    with gr.Row():
        eval_share_copy_btn = gr.Button("复制文本", scale=1)
        eval_share_docx_btn = gr.Button("导出Word", scale=1)
        eval_share_image_btn = gr.Button("生成图片", scale=1)
        eval_share_link_btn = gr.Button("生成链接", scale=1)
    eval_share_text_output = gr.Textbox(label="复制内容 / 链接", interactive=False, lines=3)
    eval_share_file_output = gr.File(label="下载文件")

    def refresh_sessions(current_user=""):
        choices = get_session_choices(current_user)
        return gr.update(choices=choices, value=choices[0] if choices else None)

    eval_btn.click(
        fn=generate_and_store_evaluation,
        inputs=[session_dropdown],
        outputs=[radar_chart, report_display, summary_display, progression_display, current_eval_report, eval_share_select],
    )
    refresh_sessions_btn.click(fn=refresh_sessions, inputs=[user_dropdown or gr.State("")], outputs=[session_dropdown])
    eval_share_copy_btn.click(fn=eval_share_copy, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_text_output])
    eval_share_docx_btn.click(fn=eval_share_docx, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_file_output])
    eval_share_image_btn.click(fn=eval_share_image, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_file_output])
    eval_share_link_btn.click(fn=eval_share_link, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_text_output])
