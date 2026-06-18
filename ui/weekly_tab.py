import gradio as gr

_reviewer = None
_review_store = None


def _get_reviewer():
    global _reviewer
    if _reviewer is None:
        from core.weekly_review import WeeklyReviewer
        _reviewer = WeeklyReviewer()
    return _reviewer


def _get_review_store():
    global _review_store
    if _review_store is None:
        from storage.weekly_review_store import WeeklyReviewStore
        _review_store = WeeklyReviewStore()
    return _review_store


def _format_review(review) -> str:
    lines = [f"# 每周复盘报告\n"]
    lines.append(f"**周期**：{review.week_start} ~ {review.week_end}")
    lines.append(f"**训练次数**：{review.session_count}次")
    lines.append(f"**成功次数**：{review.success_count}次")
    lines.append(f"**平均总分**：{review.avg_overall_score}/10")
    lines.append(f"**分数趋势**：{review.score_trend}")

    if review.avg_dimension_scores:
        lines.append("\n## 各维度平均分")
        for dim, score in review.avg_dimension_scores.items():
            bar = "█" * int(score) + "░" * (10 - int(score))
            lines.append(f"- {dim}：{bar} {score}/10")

    if review.summary:
        lines.append(f"\n## 本周总结\n{review.summary}")

    if review.suggestions:
        lines.append("\n## 改进建议")
        for i, s in enumerate(review.suggestions, 1):
            lines.append(f"{i}. {s}")

    if review.focus_areas:
        lines.append("\n## 下周重点")
        for i, f in enumerate(review.focus_areas, 1):
            lines.append(f"{i}. {f}")

    return "\n".join(lines)


def _get_review_choices(current_user=""):
    reviews = _get_review_store().list_by_user(current_user)
    choices = []
    for r in reviews:
        label = f"{r.week_start} ~ {r.week_end} | {r.session_count}次训练 | 均分{r.avg_overall_score}"
        choices.append((label, r.id))
    return choices


def create_weekly_tab(user_dropdown=None):
    gr.Markdown("## 每周复盘")
    gr.Markdown("汇总每周训练数据，自动生成复盘报告，包括训练统计、维度分析、改进建议和下周重点。")

    with gr.Row():
        with gr.Column(scale=1):
            generate_btn = gr.Button("生成本周复盘", variant="primary")
            refresh_btn = gr.Button("刷新历史")
            review_dropdown = gr.Dropdown(
                choices=_get_review_choices(), label="历史周报", interactive=True,
            )
            view_btn = gr.Button("查看选中的周报")
            status_text = gr.Textbox(label="状态", interactive=False)

        with gr.Column(scale=2):
            review_display = gr.Markdown(value="暂无复盘报告。完成训练后点击「生成本周复盘」。")

    def generate_review(current_user):
        if not current_user:
            return "请先登录", gr.update()
        try:
            review = _get_reviewer().generate(current_user)
            if not review:
                return "本周暂无训练数据，无法生成复盘", gr.update()
            review_md = _format_review(review)
            choices = _get_review_choices(current_user)
            return f"复盘报告已生成（{review.week_start} ~ {review.week_end}）", gr.update(value=review_md, choices=choices)
        except Exception as e:
            return f"生成失败：{str(e)[:200]}", gr.update()

    def refresh_reviews(current_user):
        choices = _get_review_choices(current_user)
        return gr.update(choices=choices, value=None)

    def view_review(review_id, current_user):
        if not review_id:
            return gr.update(value="请选择一份周报")
        review = _get_review_store().load(review_id)
        if not review:
            return gr.update(value="未找到该周报")
        if current_user and review.user != current_user:
            return gr.update(value="无权查看该周报")
        return gr.update(value=_format_review(review))

    generate_btn.click(
        fn=generate_review,
        inputs=[user_dropdown],
        outputs=[status_text, review_display],
    )
    refresh_btn.click(
        fn=refresh_reviews,
        inputs=[user_dropdown],
        outputs=[review_dropdown],
    )
    if user_dropdown is not None:
        user_dropdown.change(fn=refresh_reviews, inputs=[user_dropdown], outputs=[review_dropdown])
    view_btn.click(
        fn=view_review,
        inputs=[review_dropdown, user_dropdown],
        outputs=[review_display],
    )
