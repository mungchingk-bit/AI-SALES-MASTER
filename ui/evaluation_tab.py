import base64
from io import BytesIO

import gradio as gr
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

import config

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
            if s.status not in ("completed", "abandoned"):
                continue
            if current_user and s.user and s.user != current_user:
                continue
            mode_label = "销售练习" if s.mode == "customer" else "风格学习"
            status_label = "已放弃" if s.status == "abandoned" else ""
            user_tag = f"[{s.user}] " if s.user else ""
            label = f"{user_tag}{s.started_at[:10]} | {mode_label}"
            if status_label:
                label += f" | {status_label}"
            label += f" | {s.id[:8]}"
            choices.append(label)
        return choices

    def generate_evaluation(session_choice, current_user=""):
        if not session_choice:
            return "", "请选择训练记录", "", ""
        session_id = session_choice.split("|")[-1].strip()
        sessions = session_store.list_all()
        full_id = None
        for s in sessions:
            if s.id.startswith(session_id):
                if current_user and s.user and s.user != current_user:
                    return "", "无权查看该训练记录", "", ""
                full_id = s.id
                break
        if not full_id:
            return "", "未找到训练记录", "", ""
        existing = _get_eval_store().load_by_session(full_id)
        if existing:
            report = existing
        else:
            report = _get_evaluator().evaluate(full_id)
        if not report:
            return "", "评估生成失败", "", ""
        chart = _generate_radar_chart(report)
        report_text = _format_dimension_report(report)
        summary_text = _format_summary(report)
        progression_text = _format_deal_progression(report)
        return chart, report_text, summary_text, progression_text

    def _generate_radar_chart(report):
        dimensions = list(report.dimension_scores.keys())
        scores = [report.dimension_scores[d].get("score", 0) for d in dimensions]
        if not dimensions or not scores:
            return ""
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
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        return f'<div style="text-align:center"><img src="data:image/png;base64,{img_b64}" style="max-width:100%;border-radius:8px"></div>'

    def _format_dimension_report(report):
        lines = [f"## 综合评分：{report.overall_score}/10\n"]
        if report.is_corrected:
            lines.append("*(已手动修正)*\n")
        lines.append("### 各维度评分\n")
        for dim, data in report.dimension_scores.items():
            score = data.get("score", 0)
            justification = data.get("justification", "")
            bar = "●" * score + "○" * (10 - score)
            corrected_mark = ""
            if report.is_corrected and dim in report.corrections:
                orig = report.corrections[dim].get("original_score", "")
                corrected_mark = f" (原{orig}分→修正{score}分)"
            lines.append(f"**{dim}**：{bar} {score}/10{corrected_mark}")
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

    def generate_and_store_evaluation(session_choice, current_user=""):
        chart, report_text, summary_text, progression_text = generate_evaluation(session_choice, current_user)
        # Build share checkboxes + populate correction modal
        section_choices = []
        section_defaults = []
        correction_defaults = []
        if session_choice:
            session_id = session_choice.split("|")[-1].strip()
            sessions = session_store.list_all()
            full_id = None
            for s in sessions:
                if s.id.startswith(session_id):
                    full_id = s.id
                    break
            if full_id:
                session = _get_session_store().load(full_id)
                if current_user and session and session.user and session.user != current_user:
                    for dim in config.EVAL_DIMENSIONS:
                        correction_defaults.append(5)
                        correction_defaults.append("")
                    return chart, report_text, summary_text, progression_text, None, gr.update(choices=[], value=[]), *correction_defaults
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
                    # Populate correction sliders/textboxes from report
                    for dim in config.EVAL_DIMENSIONS:
                        data = report.dimension_scores.get(dim, {})
                        correction_defaults.append(data.get("score", 5))
                        correction_defaults.append(data.get("justification", ""))
                    return chart, report_text, summary_text, progression_text, report, gr.update(choices=section_choices, value=section_defaults), *correction_defaults
        # Empty correction defaults when no report
        for dim in config.EVAL_DIMENSIONS:
            correction_defaults.append(5)
            correction_defaults.append("")
        return chart, report_text, summary_text, progression_text, None, gr.update(choices=[], value=[]), *correction_defaults

    def _build_eval_selected_md(report, selected_items):
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

    def save_correction(report, *correction_values, current_user=""):
        if not report:
            return "", "请先生成评估报告", "", "", "", None, gr.update()
        corrections = {}
        for i, dim in enumerate(config.EVAL_DIMENSIONS):
            score = correction_values[i * 2]
            justification = correction_values[i * 2 + 1]
            corrections[dim] = {"score": int(score), "justification": justification}
        corrected = _get_evaluator().correct_report(report.id, corrections, corrected_by=current_user)
        if not corrected:
            return "", "修正保存失败", "", "", "", None, gr.update()
        chart = _generate_radar_chart(corrected)
        report_text = _format_dimension_report(corrected)
        summary_text = _format_summary(corrected)
        progression_text = _format_deal_progression(corrected)
        # Update share checkboxes
        section_choices = []
        section_defaults = []
        if corrected.dimension_scores:
            section_choices.append("各维度评分")
            section_defaults.append("各维度评分")
        if corrected.strengths:
            section_choices.append("优势总结")
            section_defaults.append("优势总结")
        if corrected.improvements:
            section_choices.append("改进建议")
            section_defaults.append("改进建议")
        if corrected.style_alignment:
            section_choices.append("风格契合度")
        if corrected.conversation_summary:
            section_choices.append("实战总结")
            section_defaults.append("实战总结")
        if corrected.deal_progression:
            section_choices.append("签单路径分析")
            section_defaults.append("签单路径分析")
        return chart, "✅ 修正已保存，未来评估将参考此标准", report_text, summary_text, progression_text, corrected, gr.update(choices=section_choices, value=section_defaults)

    # --- UI Layout ---
    gr.Markdown("## 评估报告")
    gr.Markdown("选择已完成的训练记录，查看实战总结、评分和签单路径分析。")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 选择训练记录")
            session_dropdown = gr.Dropdown(choices=get_session_choices(), label="训练记录")
            refresh_sessions_btn = gr.Button("刷新记录", scale=1)
            eval_btn = gr.Button("查看评估", variant="primary")
        with gr.Column(scale=2):
            gr.Markdown("### 评分雷达图")
            radar_chart = gr.HTML()

    with gr.Accordion("实战总结", open=True):
        summary_display = gr.Markdown()
    with gr.Accordion("维度评分", open=True):
        report_display = gr.Markdown()
    with gr.Accordion("签单路径", open=True):
        progression_display = gr.Markdown()
    with gr.Accordion("修正评分", open=False):
        gr.Markdown("修改分数和评语后点击保存。修正数据将用于提升未来评估准确性。")
        correction_components = []
        for dim in config.EVAL_DIMENSIONS:
            with gr.Row():
                slider = gr.Slider(1, 10, step=1, value=5, label=f"{dim} 分数", scale=1)
                textbox = gr.Textbox(label=f"{dim} 评语", lines=1, scale=3)
                correction_components.append(slider)
                correction_components.append(textbox)
        save_correction_btn = gr.Button("保存修正", variant="primary")
        correction_status = gr.Markdown("")

    gr.Markdown("### 分享报告")
    eval_share_select = gr.CheckboxGroup(label="选择要分享的内容", choices=[], value=[])
    with gr.Row():
        eval_share_copy_btn = gr.Button("复制文本", scale=1)
        eval_share_docx_btn = gr.Button("导出Word", scale=1)
        eval_share_image_btn = gr.Button("生成图片", scale=1)
    eval_share_text_output = gr.Textbox(label="复制内容", interactive=False, lines=3)
    eval_share_file_output = gr.File(label="下载文件")

    def refresh_sessions(current_user=""):
        choices = get_session_choices(current_user)
        return gr.update(choices=choices, value=choices[0] if choices else None)

    eval_btn.click(
        fn=generate_and_store_evaluation,
        inputs=[session_dropdown, user_dropdown or gr.State("")],
        outputs=[radar_chart, report_display, summary_display, progression_display, current_eval_report, eval_share_select] + correction_components,
    )
    save_correction_btn.click(
        fn=save_correction,
        inputs=[current_eval_report] + correction_components + [user_dropdown or gr.State("")],
        outputs=[radar_chart, correction_status, report_display, summary_display, progression_display, current_eval_report, eval_share_select],
    )
    refresh_sessions_btn.click(fn=refresh_sessions, inputs=[user_dropdown or gr.State("")], outputs=[session_dropdown])
    if user_dropdown is not None:
        user_dropdown.change(fn=refresh_sessions, inputs=[user_dropdown], outputs=[session_dropdown])
    eval_share_copy_btn.click(fn=eval_share_copy, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_text_output])
    eval_share_docx_btn.click(fn=eval_share_docx, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_file_output])
    eval_share_image_btn.click(fn=eval_share_image, inputs=[current_eval_report, eval_share_select], outputs=[eval_share_file_output])
