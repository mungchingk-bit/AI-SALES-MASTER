import gradio as gr

from storage.weekly_review_store import WeeklyReviewStore
from storage.user_store import UserStore

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
        _review_store = WeeklyReviewStore()
    return _review_store


def _account_context(login_username: str | None) -> tuple[str, str]:
    """Return authenticated role and display name."""
    if not login_username:
        return "", ""
    user = UserStore().get_user(login_username)
    if not user:
        return "", ""
    return user.get("role", ""), user.get("display_name", "")


def _personal_target(login_username: str | None, selected_sales: str | None) -> tuple[str, str]:
    role, display_name = _account_context(login_username)
    if role == "sales":
        return display_name, role
    if role == "admin":
        return (selected_sales or ""), role
    return "", role


def _format_review(review) -> str:
    is_team = getattr(review, "scope", "personal") == "team"
    title = "团队每周复盘报告" if is_team else "个人每周复盘报告"
    lines = [f"# {title}\n"]
    lines.append(f"**周期**：{review.week_start} ~ {review.week_end}")
    if is_team:
        lines.append(f"**覆盖销售**：{getattr(review, 'sales_count', 0)}人")
    lines.append(f"**训练次数**：{review.session_count}次")
    lines.append(f"**面聊汇报**：{getattr(review, 'face_to_face_count', 0)}份")
    lines.append(f"**成功次数**：{review.success_count}次")
    lines.append(f"**平均总分**：{review.avg_overall_score}/10")
    lines.append(f"**分数趋势**：{review.score_trend}")
    lines.append(f"**数据更新**：{getattr(review, 'updated_at', review.created_at)[:19].replace('T', ' ')}")

    if review.avg_dimension_scores:
        lines.append("\n## 各维度平均分")
        for dim, score in review.avg_dimension_scores.items():
            bar = "█" * int(score) + "░" * (10 - int(score))
            lines.append(f"- {dim}：{bar} {score}/10")

    if review.summary:
        lines.append(f"\n## {'团队总结' if is_team else '本周总结'}\n{review.summary}")

    if getattr(review, "strengths", []):
        lines.append("\n## 共性优势" if is_team else "\n## 个人优势")
        lines.extend(f"- {item}" for item in review.strengths)

    if review.suggestions:
        lines.append("\n## 管理与训练建议" if is_team else "\n## 改进建议")
        lines.extend(f"{index}. {item}" for index, item in enumerate(review.suggestions, 1))

    if review.focus_areas:
        lines.append("\n## 下周团队重点" if is_team else "\n## 下周个人重点")
        lines.extend(f"{index}. {item}" for index, item in enumerate(review.focus_areas, 1))

    if is_team and getattr(review, "individual_insights", []):
        lines.append("\n## 各销售调整方向")
        for insight in review.individual_insights:
            name = insight.get("sales_name", "未命名销售")
            lines.append(f"\n### {name}")
            if insight.get("strength"):
                lines.append(f"- **优势**：{insight['strength']}")
            if insight.get("improvement"):
                lines.append(f"- **需改进**：{insight['improvement']}")
            if insight.get("next_action"):
                lines.append(f"- **下周动作**：{insight['next_action']}")

    return "\n".join(lines)


def _review_choices(owner: str):
    if not owner:
        return []
    reviews = _get_review_store().list_by_user(owner)
    choices = []
    for review in reviews:
        if getattr(review, "scope", "personal") == "team":
            label = (
                f"{review.week_start} ~ {review.week_end} | {getattr(review, 'sales_count', 0)}人 | "
                f"{review.session_count}次训练 + {getattr(review, 'face_to_face_count', 0)}份面聊"
            )
        else:
            label = (
                f"{review.week_start} ~ {review.week_end} | {review.session_count}次训练 + "
                f"{getattr(review, 'face_to_face_count', 0)}份面聊 | 均分{review.avg_overall_score}"
            )
        choices.append((label, review.id))
    return choices


def _status_label(status: str) -> str:
    return {
        "created": "复盘报告已生成",
        "updated": "检测到新数据，复盘报告已更新",
        "unchanged": "本周暂无新增或变化，沿用已有复盘",
    }.get(status, "复盘处理完成")


def create_weekly_tab(user_dropdown=None, login_user_state=None):
    gr.Markdown("## 每周复盘")
    gr.Markdown(
        "个人复盘用于销售自我改进；团队复盘供管理员汇总全员表现并安排下周训练。"
    )

    login_user_state = login_user_state or gr.State(None)

    with gr.Tabs():
        with gr.Tab("个人复盘"):
            gr.Markdown("销售账号自动查看本人；管理员可通过顶部「当前销售」下钻查看个人。")
            with gr.Row():
                with gr.Column(scale=1):
                    personal_generate = gr.Button("生成/更新个人复盘", variant="primary")
                    personal_refresh = gr.Button("刷新个人历史")
                    personal_history = gr.Dropdown(label="个人历史周报", interactive=True)
                    personal_view = gr.Button("查看选中的个人周报")
                    personal_status = gr.Textbox(label="状态", interactive=False)
                with gr.Column(scale=2):
                    personal_display = gr.Markdown(value="暂无个人复盘报告。")

        with gr.Tab("团队复盘（管理员）"):
            gr.Markdown("汇总本周所有销售的训练场、评估与面聊汇报，并拆解到每位销售。")
            with gr.Row():
                with gr.Column(scale=1):
                    team_generate = gr.Button("生成/更新团队复盘", variant="primary")
                    team_refresh = gr.Button("刷新团队历史")
                    team_history = gr.Dropdown(label="团队历史周报", interactive=True)
                    team_view = gr.Button("查看选中的团队周报")
                    team_status = gr.Textbox(label="状态", interactive=False)
                with gr.Column(scale=2):
                    team_display = gr.Markdown(value="团队复盘仅管理员可生成和查看。")

    def generate_personal(login_username, selected_sales):
        target, role = _personal_target(login_username, selected_sales)
        if not role:
            return "登录状态已失效，请重新登录", gr.update(), gr.update()
        if not target:
            return "请先在顶部选择要查看的销售", gr.update(), gr.update()
        try:
            review, status = _get_reviewer().generate_with_status(target)
            if not review:
                return f"{target}本周暂无训练或面聊数据，不生成复盘", gr.update(), gr.update()
            choices = _review_choices(target)
            return (
                f"{_status_label(status)}：{target}（{review.week_start} ~ {review.week_end}）",
                gr.update(value=_format_review(review)),
                gr.update(choices=choices, value=review.id),
            )
        except Exception as exc:
            return f"生成失败：{str(exc)[:200]}", gr.update(), gr.update()

    def refresh_personal(login_username, selected_sales):
        target, role = _personal_target(login_username, selected_sales)
        if not role:
            return gr.update(choices=[], value=None), "登录状态已失效，请重新登录"
        if not target:
            return gr.update(choices=[], value=None), "请先在顶部选择要查看的销售"
        return gr.update(choices=_review_choices(target), value=None), f"已刷新{target}的个人周报"

    def view_personal(review_id, login_username, selected_sales):
        target, role = _personal_target(login_username, selected_sales)
        if not role:
            return gr.update(value="登录状态已失效，请重新登录")
        if not review_id:
            return gr.update(value="请选择一份个人周报")
        review = _get_review_store().load(review_id)
        if not review or review.user != target or getattr(review, "scope", "personal") != "personal":
            return gr.update(value="无权查看该个人周报")
        return gr.update(value=_format_review(review))

    def generate_team(login_username):
        role, _ = _account_context(login_username)
        if role != "admin":
            return "仅管理员可以生成团队复盘", gr.update(), gr.update()
        try:
            review, status = _get_reviewer().generate_team_with_status()
            if not review:
                return "本周全团队暂无训练或面聊数据，不生成复盘", gr.update(), gr.update()
            choices = _review_choices(WeeklyReviewStore.TEAM_OWNER)
            return (
                f"{_status_label(status)}（{review.week_start} ~ {review.week_end}）",
                gr.update(value=_format_review(review)),
                gr.update(choices=choices, value=review.id),
            )
        except Exception as exc:
            return f"生成失败：{str(exc)[:200]}", gr.update(), gr.update()

    def refresh_team(login_username):
        role, _ = _account_context(login_username)
        if role != "admin":
            return gr.update(choices=[], value=None), "仅管理员可以查看团队复盘"
        return (
            gr.update(choices=_review_choices(WeeklyReviewStore.TEAM_OWNER), value=None),
            "团队周报历史已刷新",
        )

    def view_team(review_id, login_username):
        role, _ = _account_context(login_username)
        if role != "admin":
            return gr.update(value="仅管理员可以查看团队复盘")
        if not review_id:
            return gr.update(value="请选择一份团队周报")
        review = _get_review_store().load(review_id)
        if (
            not review
            or review.user != WeeklyReviewStore.TEAM_OWNER
            or getattr(review, "scope", "personal") != "team"
        ):
            return gr.update(value="未找到团队周报")
        return gr.update(value=_format_review(review))

    personal_generate.click(
        fn=generate_personal,
        inputs=[login_user_state, user_dropdown],
        outputs=[personal_status, personal_display, personal_history],
    )
    personal_refresh.click(
        fn=refresh_personal,
        inputs=[login_user_state, user_dropdown],
        outputs=[personal_history, personal_status],
    )
    personal_view.click(
        fn=view_personal,
        inputs=[personal_history, login_user_state, user_dropdown],
        outputs=[personal_display],
    )
    if user_dropdown is not None:
        user_dropdown.change(
            fn=refresh_personal,
            inputs=[login_user_state, user_dropdown],
            outputs=[personal_history, personal_status],
        )

    team_generate.click(
        fn=generate_team,
        inputs=[login_user_state],
        outputs=[team_status, team_display, team_history],
    )
    team_refresh.click(
        fn=refresh_team,
        inputs=[login_user_state],
        outputs=[team_history, team_status],
    )
    team_view.click(
        fn=view_team,
        inputs=[team_history, login_user_state],
        outputs=[team_display],
    )
