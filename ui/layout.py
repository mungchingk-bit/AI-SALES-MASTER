import gradio as gr

from ui.components import create_header, create_footer
from ui.training_tab import create_training_tab
from ui.style_tab import create_style_tab
from ui.evaluation_tab import create_evaluation_tab


def create_app() -> gr.Blocks:
    with gr.Blocks(
        title="AI SALES MASTER - 销售实战训练大师",
    ) as app:
        create_header()

        with gr.Tabs():
            with gr.Tab("训练场"):
                create_training_tab()
            with gr.Tab("风格管理"):
                create_style_tab()
            with gr.Tab("评估报告"):
                create_evaluation_tab()

        create_footer()

    return app
