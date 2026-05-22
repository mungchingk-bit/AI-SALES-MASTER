import json
import os

import gradio as gr

from core.style_extractor import StyleExtractor
from core.llm_client import get_client
from storage.style_store import StyleStore
from utils.file_parser import parse_file
from utils.desensitizer import desensitize_text, preview_desensitization
from prompts.style_extraction import STYLE_COMPARISON_PROMPT

import config


def create_style_tab() -> gr.Blocks:
    store = StyleStore()

    def preview_before_extract(file):
        """上传文件后预览脱敏效果。"""
        if file is None:
            return "请上传文件", ""

        try:
            with open(file.name, "r", encoding="utf-8") as f:
                content = f.read(5000)  # 只预览前5000字符

            # 解析对话
            messages = parse_file(file.name)
            if not messages:
                return "无法解析文件，请检查格式", ""

            preview = f"解析到 {len(messages)} 条对话记录。\n\n"

            # 如果使用云端模型，展示脱敏预览
            if config.LLM_PROVIDER == "claude" and config.DESENSITIZE_ENABLED:
                original_text = "\n".join(msg.content for msg in messages[:20])
                desensitize_info = preview_desensitization(original_text)
                if "未检测到" not in desensitize_info:
                    preview += f"**云端模式脱敏预览：**\n{desensitize_info}\n\n"
                    preview += "提取时将自动替换上述敏感信息，风格特征不受影响。"
                else:
                    preview += "未检测到敏感信息。"
            else:
                preview += f"**当前为本地模型模式**，数据不出本机，无需脱敏。"

            return preview, ""
        except Exception as e:
            return f"预览失败：{str(e)}", ""

    def upload_and_extract(file, style_name):
        """提取销售风格。"""
        if file is None:
            return "请上传文件", _refresh_styles()

        try:
            # Parse the uploaded file
            messages = parse_file(file.name)
            if not messages:
                return "无法从文件中解析出对话记录，请检查文件格式", _refresh_styles()

            # Extract style
            extractor = StyleExtractor()
            profile = extractor.extract(messages, source_file=os.path.basename(file.name))

            # Override name if provided
            if style_name and style_name.strip():
                profile.name = style_name.strip()

            # Check slot limit
            existing = store.list_all()
            if len(existing) >= config.MAX_STYLE_SLOTS:
                return f"风格槽位已满（最多{config.MAX_STYLE_SLOTS}个），请先删除已有风格", _refresh_styles()

            # Save
            store.save(profile)

            provider_label = "本地模型" if config.LLM_PROVIDER == "ollama" else "云端API（已脱敏）"
            return f"风格「{profile.name}」提取成功！({provider_label})\n\n{profile.description}", _refresh_styles()
        except Exception as e:
            return f"提取失败：{str(e)}", _refresh_styles()

    def compare_styles(style_a_name, style_b_name):
        """Compare two styles."""
        if not style_a_name or not style_b_name:
            return "请选择两种风格进行对比"
        if style_a_name == style_b_name:
            return "请选择不同的风格进行对比"

        profiles = store.list_all()
        profile_a = next((p for p in profiles if p.name == style_a_name), None)
        profile_b = next((p for p in profiles if p.name == style_b_name), None)

        if not profile_a or not profile_b:
            return "未找到所选风格"

        prompt = STYLE_COMPARISON_PROMPT.format(
            style_a_name=profile_a.name,
            style_a_traits=json.dumps(profile_a.extracted_traits, ensure_ascii=False, indent=2),
            style_b_name=profile_b.name,
            style_b_traits=json.dumps(profile_b.extracted_traits, ensure_ascii=False, indent=2),
        )

        try:
            client = get_client()
            result = client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=config.EXTRACTION_TEMP,
                max_tokens=2048,
            )
            return result
        except Exception as e:
            return f"对比失败：{str(e)}"

    def _refresh_styles():
        """Refresh the style display."""
        profiles = store.list_all()
        if not profiles:
            return "暂无风格档案，请上传销售对话文件来提取风格"

        lines = []
        for i, p in enumerate(profiles):
            traits = p.extracted_traits
            confidence_count = sum(1 for v in p.confidence_scores.values() if v > 0.5)
            total_count = len(p.confidence_scores) if p.confidence_scores else 7

            lines.append(f"### 风格 {i+1}：{p.name}")
            lines.append(f"- **来源**：{p.source_file or '未知'}")
            lines.append(f"- **概述**：{p.description}")
            lines.append(f"- **置信度**：{confidence_count}/{total_count} 维度高置信")

            if traits.get("key_phrases"):
                lines.append(f"- **标志性用语**：{', '.join(traits['key_phrases'][:5])}")
            if traits.get("tone"):
                lines.append(f"- **语气基调**：{traits['tone']}")
            if traits.get("objection_strategy"):
                lines.append(f"- **异议处理**：{traits['objection_strategy']}")
            if traits.get("closing_style"):
                lines.append(f"- **成交风格**：{traits['closing_style']}")

            lines.append("")

        return "\n".join(lines)

    def get_style_names():
        profiles = store.list_all()
        return [p.name for p in profiles]

    # 当前模式标签
    provider_info = (
        "**本地模型模式**：数据不出本机，零出网"
        if config.LLM_PROVIDER == "ollama"
        else "**云端API模式**：发送前自动脱敏"
    )

    with gr.Blocks() as tab:
        gr.Markdown("## 风格管理")
        gr.Markdown(f"上传销售对话文件，AI将自动提取销售风格特征。最多支持4种风格。\n\n{provider_info}")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 上传与提取")
                file_input = gr.File(label="上传销售对话文件", file_types=[".txt", ".csv", ".json"])
                style_name_input = gr.Textbox(label="风格名称（可选，留空自动生成）", placeholder="如：顾问式")

                with gr.Row():
                    preview_btn = gr.Button("预览脱敏")
                    extract_btn = gr.Button("提取风格", variant="primary")

                preview_result = gr.Textbox(label="脱敏预览", lines=6, interactive=False, visible=True)
                extract_result = gr.Textbox(label="提取结果", lines=3, interactive=False)

                gr.Markdown("### 支持的文件格式")
                gr.Markdown("""
- **TXT**：每行以"销售："或"客户："开头
- **CSV**：包含 speaker 和 content 列
- **JSON**：数组格式，含 role 和 content 字段
""")

            with gr.Column(scale=1):
                gr.Markdown("### 我的风格档案")
                styles_display = gr.Markdown(_refresh_styles())

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 风格对比")
                with gr.Row():
                    style_a = gr.Dropdown(label="风格A", choices=get_style_names(), scale=1)
                    style_b = gr.Dropdown(label="风格B", choices=get_style_names(), scale=1)
                compare_btn = gr.Button("对比分析")
                compare_result = gr.Markdown()

        # Event handlers
        preview_btn.click(
            fn=preview_before_extract,
            inputs=[file_input],
            outputs=[preview_result, extract_result],
        )

        extract_btn.click(
            fn=upload_and_extract,
            inputs=[file_input, style_name_input],
            outputs=[extract_result, styles_display],
        )

        compare_btn.click(
            fn=compare_styles,
            inputs=[style_a, style_b],
            outputs=[compare_result],
        )

        # Refresh dropdowns on load
        tab.load(fn=lambda: (gr.update(choices=get_style_names()), gr.update(choices=get_style_names())),
                 outputs=[style_a, style_b])

    return tab
