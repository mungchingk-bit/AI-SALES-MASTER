import gradio as gr
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from core.evaluator import Evaluator
from storage.evaluation_store import EvaluationStore
from storage.session_store import SessionStore

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def create_evaluation_tab() -> gr.Blocks:
    evaluator = Evaluator()
    eval_store = EvaluationStore()
    session_store = SessionStore()

    def get_session_choices():
        sessions = session_store.list_all()
        choices = []
        for s in sessions:
            if s.status == "completed":
                mode_label = "销售练习" if s.mode == "customer" else "风格学习"
                choices.append(f"{s.started_at[:10]} | {mode_label} | {s.id[:8]}")
        return choices

    def generate_evaluation(session_choice):
        """Generate evaluation for a selected session."""
        if not session_choice:
            return None, "请选择训练记录", "", ""

        session_id = session_choice.split("|")[-1].strip()
        # Find full session ID
        sessions = session_store.list_all()
        full_id = None
        for s in sessions:
            if s.id.startswith(session_id):
                full_id = s.id
                break

        if not full_id:
            return None, "未找到训练记录", "", ""

        # Check if evaluation already exists
        existing = eval_store.load_by_session(full_id)
        if existing:
            report = existing
        else:
            report = evaluator.evaluate(full_id)

        if not report:
            return None, "评估生成失败", "", ""

        # Generate radar chart
        chart = _generate_radar_chart(report)

        # Format dimension report
        report_text = _format_dimension_report(report)

        # Format conversation summary
        summary_text = _format_summary(report)

        # Format deal progression
        progression_text = _format_deal_progression(report)

        return chart, report_text, summary_text, progression_text

    def _generate_radar_chart(report):
        """Generate a radar chart from evaluation report."""
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
        """Format the dimension scoring part of the report."""
        lines = [f"## 综合评分：{report.overall_score}/10\n"]

        # Dimension scores
        lines.append("### 各维度评分\n")
        for dim, data in report.dimension_scores.items():
            score = data.get("score", 0)
            justification = data.get("justification", "")
            bar = "●" * score + "○" * (10 - score)
            lines.append(f"**{dim}**：{bar} {score}/10")
            lines.append(f"  {justification}\n")

        # Strengths
        if report.strengths:
            lines.append("### 优势总结\n")
            for i, s in enumerate(report.strengths, 1):
                lines.append(f"{i}. {s}")
            lines.append("")

        # Improvements
        if report.improvements:
            lines.append("### 改进建议\n")
            for i, s in enumerate(report.improvements, 1):
                lines.append(f"{i}. {s}")
            lines.append("")

        # Style alignment
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

        # Specific examples
        if report.specific_examples:
            lines.append("### 具体对话点评\n")
            for ex in report.specific_examples:
                turn = ex.get("turn", "?")
                comment = ex.get("comment", "")
                lines.append(f"- 第{turn}轮：{comment}")
            lines.append("")

        return "\n".join(lines)

    def _format_summary(report):
        """Format the conversation summary section."""
        if not report.conversation_summary:
            return "暂无实战总结"
        return report.conversation_summary

    def _format_deal_progression(report):
        """Format the deal progression analysis section."""
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

    with gr.Blocks() as tab:
        gr.Markdown("## 评估报告")
        gr.Markdown("选择已完成的训练记录，查看实战总结、评分和签单路径分析。")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 选择训练记录")
                session_dropdown = gr.Dropdown(
                    choices=get_session_choices(),
                    label="训练记录",
                )
                eval_btn = gr.Button("查看评估", variant="primary")

            with gr.Column(scale=2):
                radar_chart = gr.Plot(label="评分雷达图")

        # Three sections: 实战总结, 维度评分, 签单路径
        with gr.Tabs():
            with gr.Tab("实战总结"):
                summary_display = gr.Markdown()
            with gr.Tab("维度评分"):
                report_display = gr.Markdown()
            with gr.Tab("签单路径"):
                progression_display = gr.Markdown()

        # Event handlers
        eval_btn.click(
            fn=generate_evaluation,
            inputs=[session_dropdown],
            outputs=[radar_chart, report_display, summary_display, progression_display],
        )

        tab.load(fn=lambda: gr.update(choices=get_session_choices()), outputs=[session_dropdown])

    return tab
