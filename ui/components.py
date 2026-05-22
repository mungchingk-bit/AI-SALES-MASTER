import gradio as gr


def create_header() -> gr.Markdown:
    return gr.Markdown(
        """
# AI SALES MASTER - 销售实战训练大师
模拟真实客户与销售对练 | 4种销售风格学习 | 专业维度评估与改进建议
"""
    )


def create_footer() -> gr.Markdown:
    return gr.Markdown(
        """
---
AI SALES MASTER | Powered by Claude API | 销售实战训练平台
"""
    )
