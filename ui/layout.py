import gradio as gr

from ui.components import build_login_ui, build_main_header, create_admin_tab, create_footer


def create_app() -> gr.Blocks:
    with gr.Blocks(
        title="AI SALES MASTER - 销售实战训练大师",
    ) as app:
        # === 登录/注册区域 ===
        with gr.Column() as login_col:
            gr.Markdown(
                """
# AI SALES MASTER - 销售实战训练大师
"""
            )
            login = build_login_ui()

        # === 主应用区域（登录前隐藏）===
        with gr.Column(visible=False) as main_col:
            header = build_main_header()

            with gr.Tabs():
                with gr.Tab("⚙️ 管理面板"):
                    admin_content = create_admin_tab()
                with gr.Tab("训练场"):
                    from ui.training_tab import create_training_tab
                    create_training_tab(header["user_dropdown"])
                with gr.Tab("风格管理"):
                    from ui.style_tab import create_style_tab
                    create_style_tab(header["user_dropdown"])
                with gr.Tab("评估报告"):
                    from ui.evaluation_tab import create_evaluation_tab
                    create_evaluation_tab()
                with gr.Tab("每周复盘"):
                    from ui.weekly_tab import create_weekly_tab
                    create_weekly_tab(header["user_dropdown"])

            create_footer()

        # 绑定登录/注册事件
        login["login_btn"].click(
            fn=login["do_login"],
            inputs=[login["login_phone"], login["login_password"]],
            outputs=[login["logged_in_user"], login["login_msg"], main_col, login_col,
                     header["welcome_md"], header["user_dropdown"], admin_content],
        )
        login["reg_btn"].click(
            fn=login["do_register"],
            inputs=[login["reg_phone"], login["reg_display"], login["reg_password"], login["reg_password2"]],
            outputs=[login["logged_in_user"], login["reg_msg"], main_col, login_col,
                     header["welcome_md"], header["user_dropdown"], admin_content],
        )

    return app
