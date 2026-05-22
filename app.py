import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import config
import gradio as gr
from ui.layout import create_app


def main():
    # 显示当前模型模式
    if config.LLM_PROVIDER == "ollama":
        print(f"[AI SALES MASTER] 本地模型模式: {config.OLLAMA_MODEL}")
        print(f"[AI SALES MASTER] Ollama地址: {config.OLLAMA_BASE_URL}")
        print("[AI SALES MASTER] 数据不出本机，零出网")
    else:
        print(f"[AI SALES MASTER] 云端API模式: {config.CLAUDE_MODEL}")
        print(f"[AI SALES MASTER] 自动脱敏: {'开启' if config.DESENSITIZE_ENABLED else '关闭'}")

    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
