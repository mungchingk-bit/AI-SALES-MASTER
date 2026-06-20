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
    print(f"[AI SALES MASTER] Gradio version: {gr.__version__}", flush=True)
    print(f"[AI SALES MASTER] 数据目录: {config.DATA_DIR}", flush=True)
    print(f"[AI SALES MASTER] 临时文件目录: {config.TEMP_DIR}", flush=True)
    # 显示当前模型模式
    if config.LLM_PROVIDER == "ollama":
        print(f"[AI SALES MASTER] 本地模型模式: {config.OLLAMA_MODEL}")
        print(f"[AI SALES MASTER] Ollama地址: {config.OLLAMA_BASE_URL}")
        print("[AI SALES MASTER] 数据不出本机，零出网")
    else:
        print(f"[AI SALES MASTER] 云端API模式: {config.CLAUDE_MODEL}")
        print(f"[AI SALES MASTER] 自动脱敏: {'开启' if config.DESENSITIZE_ENABLED else '关闭'}")

    # 启动时检查知识库是否有新内容可提取
    print("[AI SALES MASTER] 检查知识库...")
    try:
        from storage.knowledge_store import KnowledgeStore
        from storage.style_store import StyleStore
        import re
        kb = KnowledgeStore()
        ss = StyleStore()
        existing_names = {p.name.replace("式", "").replace("面聊", "") for p in ss.list_all()}
        kb_sales = set()
        for entry in kb.list_by_category("script_library") + kb.list_by_category("customer_doc"):
            m = re.search(r"销售(\w+)", entry.title)
            if m:
                kb_sales.add(m.group(1))
        new_sales = kb_sales - existing_names
        if new_sales:
            print(f"[AI SALES MASTER] 发现新销售资料：{', '.join(new_sales)}，请在风格管理页点击「从知识库导入」")
        else:
            print("[AI SALES MASTER] 风格档案已是最新")
    except Exception as e:
        print(f"[AI SALES MASTER] 知识库检查失败: {e}")

    print("[AI SALES MASTER] 用户系统已初始化")
    print("[AI SALES MASTER] 首次使用请注册账号 | 管理员: admin/admin123")

    app = create_app()
    app.queue()

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=False,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
