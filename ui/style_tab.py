import json
import os
import re

import gradio as gr
import requests

from storage.style_store import StyleStore

import config


def _normalize_style_name(name):
    """Normalize style name: CC话术库式 → CC式, 免免面聊式 → 免免式."""
    return name.replace("话术库式", "式").replace("面聊式", "式").replace("面聊", "")


def _dedup_styles(store):
    """Auto-merge duplicate-named styles, keeping one merged profile per name."""
    profiles = store.list_all()
    name_groups = {}
    for p in profiles:
        key = _normalize_style_name(p.name)
        name_groups.setdefault(key, []).append(p)
    for key, group in name_groups.items():
        if len(group) <= 1:
            # Also rename if needed (e.g., "免免面聊式" → "免免式")
            if group and group[0].name != key:
                group[0].name = key
                store.save(group[0])
            continue
        # Merge all into one
        merged = group[0]
        for other in group[1:]:
            merged = store.merge(merged, other, merged_name=key)
        # Ensure final name is clean (e.g., "免免式" not "免免面聊式")
        if merged.name != key:
            merged.name = key
            store.save(merged)


def create_style_tab(user_dropdown=None, login_user_state=None) -> None:
    print("[STYLE_TAB] create_style_tab called - v2 code loaded")
    store = StyleStore()
    _dedup_styles(store)

    def get_style_names(current_user=""):
        profiles = store.list_all()
        return [f"{p.name} ({p.id[:6]})" for p in profiles]

    def _parse_style_name(label):
        """Extract style name from '免免式 (abc123)' format."""
        if " (" in label:
            return label.rsplit(" (", 1)[0]
        return label

    def _refresh_styles_table(current_user=""):
        """Generate HTML table with style names as columns, attributes as rows, sticky header."""
        profiles = store.list_all()
        if not profiles:
            return '<div style="color:#999;text-align:center;padding:20px;">暂无风格档案</div>'
        style_names = [p.name for p in profiles]
        attr_rows = [
            ("tone", "语气基调"),
            ("communication_pattern", "沟通模式"),
            ("pacing", "节奏"),
            ("objection_strategy", "异议处理"),
            ("closing_style", "成交风格"),
        ]
        html_parts = ['<div style="max-height:400px;overflow-y:auto;border:1px solid #e0e0e0;border-radius:8px;">']
        html_parts.append('<table style="width:100%;border-collapse:collapse;font-size:14px;">')
        # Sticky header row with style names
        html_parts.append('<thead><tr style="background:#f5f5f5;">')
        html_parts.append('<th style="position:sticky;top:0;z-index:2;background:#f5f5f5;padding:10px 12px;text-align:left;border-bottom:2px solid #ddd;min-width:80px;">属性</th>')
        for name in style_names:
            html_parts.append(
                f'<th style="position:sticky;top:0;z-index:2;background:#f5f5f5;padding:10px 12px;text-align:left;'
                f'border-bottom:2px solid #ddd;min-width:150px;font-weight:600;color:#2563eb;">{name}</th>'
            )
        html_parts.append('</tr></thead><tbody>')
        for i, (attr_key, attr_label) in enumerate(attr_rows):
            bg = '#fafafa' if i % 2 == 0 else '#fff'
            html_parts.append(f'<tr style="background:{bg};">')
            html_parts.append(
                f'<td style="padding:10px 12px;font-weight:600;border-bottom:1px solid #eee;'
                f'white-space:nowrap;vertical-align:top;color:#374151;">{attr_label}</td>'
            )
            for p in profiles:
                val = p.extracted_traits.get(attr_key, "-")
                html_parts.append(
                    f'<td style="padding:10px 12px;border-bottom:1px solid #eee;'
                    f'line-height:1.6;vertical-align:top;">{val}</td>'
                )
            html_parts.append('</tr>')
        html_parts.append('</tbody></table></div>')
        return ''.join(html_parts)

    def _get_user_name(user_dropdown_val):
        """Extract display name from user_dropdown value like '免免' or 'CC'."""
        if not user_dropdown_val or not isinstance(user_dropdown_val, str):
            return ""
        return user_dropdown_val.strip()

    def _extract_sales_name_from_filename(filename: str) -> str:
        """Extract the trailing salesperson name from filenames like '...销售免免.docx'."""
        stem = os.path.splitext(os.path.basename(filename or ""))[0]
        match = re.search(r"销售\s*([\u4e00-\u9fffA-Za-z0-9_]+)\s*$", stem)
        if match:
            return match.group(1).strip()
        matches = re.findall(r"销售\s*([\u4e00-\u9fffA-Za-z0-9_]+)", stem)
        return matches[-1].strip() if matches else ""

    def _report_label(report):
        return f"{report.sales_name} | {report.source_title} | {report.created_at[:10]} | {report.id[:8]}"

    def _filter_reports_for_user(reports, current_user):
        if not current_user:
            return reports
        user_key = current_user.strip()
        return [
            r for r in reports
            if r.sales_name == user_key
            or getattr(r, "uploader_name", "") == user_key
            or user_key in (r.source_title or "")
            or user_key in (r.source_file or "")
        ]

    def _is_placeholder_report(report) -> bool:
        summary = report.summary or ""
        return (
            "AI面聊汇报暂时生成失败" in summary
            or "文件已上传并保存" in summary
            or not (report.highlights or report.improvements or report.corrected_scripts or report.next_steps)
        )

    def _is_rate_limit_error(error: Exception) -> bool:
        text = str(error).lower()
        return "429" in text or "too many requests" in text or "rate limit" in text

    def _filter_profiles_for_user(profiles, current_user):
        """Filter profiles: user sees own styles + company styles; empty user sees all."""
        if not current_user:
            return profiles
        user_key = current_user.replace("面聊", "")
        company_styles = {"栀夏式"}
        return [p for p in profiles if user_key in p.name or p.name in company_styles]

    def _is_admin_login(login_username):
        if not login_username:
            return False
        try:
            from storage.user_store import UserStore
            user = UserStore().get_user(login_username)
            return bool(user and user.get("role") == "admin")
        except Exception:
            return False

    def preview_before_extract(file):
        from utils.file_parser import parse_file
        from utils.desensitizer import preview_desensitization
        if file is None:
            return "请上传文件", ""
        try:
            messages = parse_file(file.name)
            if not messages:
                return "无法解析文件，请检查格式", ""
            preview = f"解析到 {len(messages)} 条对话记录。\n\n"
            if config.LLM_PROVIDER == "claude" and config.DESENSITIZE_ENABLED:
                original_text = "\n".join(msg.content for msg in messages[:20])
                desensitize_info = preview_desensitization(original_text)
                if "未检测到" not in desensitize_info:
                    preview += f"**云端模式脱敏预览：**\n{desensitize_info}\n\n提取时将自动替换上述敏感信息。"
                else:
                    preview += "未检测到敏感信息。"
            else:
                preview += "**当前为本地模型模式**，数据不出本机，无需脱敏。"
            return preview, ""
        except Exception as e:
            return f"预览失败：{str(e)}", ""

    def upload_and_extract(file, style_name, current_user=""):
        from utils.file_parser import parse_file
        from core.style_extractor import StyleExtractor
        from core.conversation_analyzer import ConversationAnalyzer
        from storage.report_store import ReportStore
        from storage.knowledge_store import KnowledgeStore
        from models.conversation_report import ConversationReport
        _empty = "", None, [], gr.update(choices=[], value=[])
        if file is None:
            return ("请上传文件", _refresh_styles_table(current_user),
                    gr.update(choices=get_style_names(current_user)),
                    gr.update(choices=get_style_names(current_user)),
                    gr.update(choices=get_style_names(current_user)),
                    _refresh_report_choices(current_user=current_user), *_empty)
        try:
            source_filename = os.path.basename(file.name)
            source_stem = os.path.splitext(source_filename)[0]
            messages = parse_file(file.name)
            if not messages:
                return ("无法从文件中解析出对话记录，请检查文件格式",
                        _refresh_styles_table(current_user),
                        gr.update(choices=get_style_names(current_user)),
                        gr.update(choices=get_style_names(current_user)),
                        gr.update(choices=get_style_names(current_user)),
                        _refresh_report_choices(current_user=current_user), *_empty)

            # Save file to knowledge base
            file_sales_name = _extract_sales_name_from_filename(source_filename)
            sales_name = file_sales_name or current_user or (style_name.strip() if style_name and style_name.strip() else "") or "未知"
            report_title = f"销售{sales_name.replace('式', '')}面聊记录（{source_stem}）"
            try:
                knowledge_store = KnowledgeStore()
                from storage.knowledge_store import KnowledgeEntry
                file_content = "\n".join(msg.content for msg in messages[:200])
                knowledge_store.save(KnowledgeEntry(
                    category="customer_doc",
                    title=report_title,
                    content=file_content,
                    source_file=source_filename,
                    uploader_name=sales_name.replace("式", ""),
                ))
            except Exception:
                file_content = "\n".join(msg.content for msg in messages[:200])

            # Generate report FIRST (independent of style slots)
            report = None
            report_md = ""
            report_ctx = None
            share_choices = []
            share_defaults = []
            report_error = ""
            report_rate_limited = False
            try:
                analyzer = ConversationAnalyzer()
                report_store = ReportStore()
                report = analyzer.analyze(
                    content=file_content,
                    sales_name=sales_name.replace("式", ""),
                    source_file=source_filename,
                    source_title=report_title,
                )
                report.uploader_name = sales_name.replace("式", "")
                report_store.save(report)
                report_md = _format_report(report)
                report_ctx = {"report": report, "original_content": file_content}
                if report.summary:
                    share_choices.append("整体评价")
                    share_defaults.append("整体评价")
                if report.highlights:
                    share_choices.append("做得好的地方")
                    share_defaults.append("做得好的地方")
                if report.improvements:
                    share_choices.append("需要改进的地方")
                    share_defaults.append("需要改进的地方")
                if report.corrected_scripts:
                    share_choices.append("改进话术对照")
                    share_defaults.append("改进话术对照")
                if report.next_steps:
                    share_choices.append("下一步行动建议")
                    share_defaults.append("下一步行动建议")
            except Exception as e:
                report_error = str(e)
                report_rate_limited = _is_rate_limit_error(e)
                report = ConversationReport(
                    sales_name=sales_name.replace("式", ""),
                    source_file=source_filename,
                    source_title=report_title,
                    summary=(
                        "文件已上传并保存。AI面聊汇报暂时生成失败，可能是模型接口限流，"
                        "请稍后点击“从知识库导入”或重新上传生成完整分析。"
                    ),
                    uploader_name=sales_name.replace("式", ""),
                )
                ReportStore().save(report)
                report_md = _format_report(report)
                report_ctx = {"report": report, "original_content": file_content}
                share_choices.append("整体评价")
                share_defaults.append("整体评价")

            # Extract style
            style_msg = ""
            if report_rate_limited:
                style_msg = "文件和基础汇报已保存。由于模型接口刚刚限流，本次先跳过风格提取，避免连续请求继续触发限流。"
            else:
                try:
                    extractor = StyleExtractor()
                    profile = extractor.extract(messages, source_file=source_filename)
                    # Name the style: custom input > sales_name式 > LLM-generated
                    if style_name and style_name.strip():
                        profile.name = style_name.strip()
                    elif sales_name and sales_name != "未知":
                        profile.name = f"{sales_name}式"

                    # Auto-merge with existing style: match by normalized name or sales_name
                    existing = store.list_all()
                    existing_match = None
                    normalized_new = _normalize_style_name(profile.name)
                    existing_match = next(
                        (p for p in existing if _normalize_style_name(p.name) == normalized_new),
                        None
                    )
                    if not existing_match and sales_name and sales_name != "未知":
                        user_key = sales_name.replace("面聊", "")
                        existing_match = next(
                            (p for p in existing if p.name.replace("式", "").replace("面聊", "") == user_key),
                            None
                        )

                    if existing_match:
                        store.save(profile)
                        merged_name = _normalize_style_name(existing_match.name)
                        merged = store.merge(existing_match, profile, merged_name=merged_name)
                        profile = merged
                        style_msg = f"风格「{profile.name}」已与同名档案合并\n{profile.description}"
                    else:
                        if len(existing) >= config.MAX_STYLE_SLOTS:
                            return (
                                "面聊汇报已生成。风格提取成功但槽位已满，请先删除已有风格再提取",
                                _refresh_styles_table(current_user),
                                gr.update(choices=get_style_names(current_user)),
                                gr.update(choices=get_style_names(current_user)),
                                gr.update(choices=get_style_names(current_user)),
                                _refresh_report_choices(report, current_user=current_user),
                                report_md, report_ctx, [],
                                gr.update(choices=share_choices, value=share_defaults),
                            )
                        store.save(profile)
                        provider_label = "本地模型" if config.LLM_PROVIDER == "ollama" else "云端API（已脱敏）"
                        style_msg = f"风格「{profile.name}」提取成功！({provider_label})\n{profile.description}"
                except Exception as e:
                    style_msg = (
                        "文件和面聊汇报已保存，但风格提取暂时失败。"
                        f"原因：{str(e)[:160]}。可稍后在流量恢复后重新上传或从知识库导入。"
                    )

            new_names = get_style_names(current_user)
            report_note = ""
            if report_error:
                report_note = f"\n完整AI面聊汇报暂时生成失败：{report_error[:160]}"
            return (
                f"{style_msg}\n面聊记录已保存，并已出现在下方“面聊汇报”列表。{report_note}",
                _refresh_styles_table(current_user),
                gr.update(choices=new_names),
                gr.update(choices=new_names),
                gr.update(choices=new_names),
                _refresh_report_choices(report, current_user=current_user),
                report_md,
                report_ctx,
                [],
                gr.update(choices=share_choices, value=share_defaults),
            )
        except Exception as e:
            return (f"提取失败：{str(e)}", _refresh_styles_table(current_user),
                    gr.update(choices=get_style_names(current_user)),
                    gr.update(choices=get_style_names(current_user)),
                    gr.update(choices=get_style_names(current_user)),
                    _refresh_report_choices(current_user=current_user), *_empty)

    def import_from_knowledge_base(current_user=""):
        """从知识库中已导入的资料提取销售风格，同名销售自动合并，同时生成面聊汇报。"""
        import re
        from storage.knowledge_store import KnowledgeStore
        from core.style_extractor import StyleExtractor
        from core.conversation_analyzer import ConversationAnalyzer
        from storage.report_store import ReportStore
        from models.chat_message import ChatMessage
        knowledge_store = KnowledgeStore()
        extractor = StyleExtractor()
        analyzer = ConversationAnalyzer()
        report_store = ReportStore()
        existing = store.list_all()
        # name_map: 销售名字 → StyleProfile（用于合并）
        # Also track which source_files are already covered per salesperson
        name_map = {}
        existing_sources = {}
        for p in existing:
            key = _normalize_style_name(p.name).replace("式", "")
            name_map[key] = p
            if key not in existing_sources:
                existing_sources[key] = set()
            for src in (p.source_file or "").split(" + "):
                existing_sources[key].add(src.strip())
        existing_report_by_source = {}
        for r in report_store.list_all():
            existing_report_by_source.setdefault(r.source_file, r)
        results = []

        # 从话术库提取风格
        scripts = knowledge_store.list_by_category("script_library")
        if current_user:
            scripts = [e for e in scripts if current_user in e.title or current_user in e.source_file or e.uploader_name == current_user]
        chats_all = knowledge_store.list_by_category("customer_doc")
        if current_user:
            chats_all = [e for e in chats_all if current_user in e.title or current_user in e.source_file or e.uploader_name == current_user]
        total_items = len(scripts) + len(chats_all)
        done = 0
        for entry in scripts:
            match = re.search(r"销售(\w+)", entry.title)
            if not match:
                continue
            sales_name = match.group(1)
            style_name = f"{sales_name}式"

            # Skip if this exact source file already imported for this salesperson
            if sales_name in existing_sources and entry.source_file in existing_sources[sales_name]:
                results.append(f"[跳过] 风格「{style_name}」已存在（话术库）")
                continue

            try:
                content = entry.content[:5000]
                messages = [ChatMessage(role="user", content=content)]
                profile = extractor.extract(messages, source_file=entry.source_file)
                profile.name = style_name

                if sales_name in name_map:
                    merged = store.merge(name_map[sales_name], profile, merged_name=style_name)
                    name_map[sales_name] = merged
                    existing_sources.setdefault(sales_name, set()).add(entry.source_file)
                    results.append(f"[合并] 风格「{style_name}」已与现有档案合并")
                else:
                    store.save(profile)
                    name_map[sales_name] = profile
                    existing_sources.setdefault(sales_name, set()).add(entry.source_file)
                    results.append(f"[成功] 风格「{profile.name}」: {profile.description}")
            except Exception as e:
                results.append(f"[失败] {entry.title}: {str(e)}")
            done += 1

        # 从面聊记录提取风格 + 生成汇报
        chats = chats_all
        for entry in chats:
            match = re.search(r"销售(\w+)", entry.title)
            if not match:
                continue
            sales_name = match.group(1)
            style_name = f"{sales_name}式"

            # Skip if this exact source file already imported
            if sales_name in existing_sources and entry.source_file in existing_sources[sales_name]:
                results.append(f"[跳过] 风格「{style_name}」面聊记录已导入")
                # Still try to generate report if missing
            else:
                try:
                    content = entry.content[:8000]
                    messages = [ChatMessage(role="user", content=content)]
                    profile = extractor.extract(messages, source_file=entry.source_file)
                    profile.name = f"{sales_name}面聊式"

                    if sales_name in name_map:
                        merged = store.merge(name_map[sales_name], profile, merged_name=style_name)
                        name_map[sales_name] = merged
                        existing_sources.setdefault(sales_name, set()).add(entry.source_file)
                        results.append(f"[合并] 风格「{style_name}」已与话术库档案合并")
                    else:
                        profile.name = style_name
                        store.save(profile)
                        name_map[sales_name] = profile
                        existing_sources.setdefault(sales_name, set()).add(entry.source_file)
                        results.append(f"[成功] 风格「{profile.name}」: {profile.description}")
                except Exception as e:
                    results.append(f"[失败] {entry.title}: {str(e)}")

            # 生成面聊汇报
            existing_report = existing_report_by_source.get(entry.source_file)
            if not existing_report or _is_placeholder_report(existing_report):
                try:
                    report = analyzer.analyze(
                        content=entry.content,
                        sales_name=sales_name,
                        source_file=entry.source_file,
                        source_title=entry.title,
                    )
                    report.uploader_name = sales_name
                    if existing_report:
                        report.id = existing_report.id
                        report.created_at = existing_report.created_at
                        report.chat_history = existing_report.chat_history
                    report_store.save(report)
                    existing_report_by_source[entry.source_file] = report
                    results.append(f"[汇报] {entry.title}：{report.summary}")
                except Exception as e:
                    results.append(f"[汇报失败] {entry.title}: {str(e)}")
            else:
                results.append(f"[跳过] {entry.title}汇报已存在")
            done += 1

        return "\n".join(results), _refresh_styles_table(current_user), _refresh_report_choices(current_user=current_user)

    def compare_styles(style_a_name, style_b_name):
        from prompts.style_extraction import STYLE_COMPARISON_PROMPT
        from core.llm_client import get_client
        if not style_a_name or not style_b_name:
            return "请选择两种风格进行对比"
        name_a = _parse_style_name(style_a_name)
        name_b = _parse_style_name(style_b_name)
        if name_a == name_b:
            return "请选择不同的风格进行对比"
        profiles = store.list_all()
        profile_a = next((p for p in profiles if p.name == name_a), None)
        profile_b = next((p for p in profiles if p.name == name_b), None)
        if not profile_a or not profile_b:
            available = [p.name for p in profiles]
            return f"未找到所选风格。\n\n选择：{name_a} / {name_b}\n\n已有风格：{', '.join(available) if available else '无'}"
        prompt = STYLE_COMPARISON_PROMPT.format(
            style_a_name=profile_a.name,
            style_a_traits=json.dumps(profile_a.extracted_traits, ensure_ascii=False, indent=2),
            style_b_name=profile_b.name,
            style_b_traits=json.dumps(profile_b.extracted_traits, ensure_ascii=False, indent=2),
        )
        try:
            client = get_client()
            result = client.chat(messages=[], system_prompt=prompt, temperature=config.EXTRACTION_TEMP, max_tokens=2048, model=config.FAST_MODEL or None)
            if not result or not result.strip():
                return "对比分析返回为空，请重试"
            return result
        except requests.exceptions.Timeout:
            return "请求超时，请稍后重试"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"对比失败：{type(e).__name__}: {str(e)}"

    def _refresh_report_choices(select_report=None, current_user=""):
        from storage.report_store import ReportStore
        report_store = ReportStore()
        reports = _filter_reports_for_user(report_store.list_all(), current_user)
        if not reports:
            return gr.update(choices=[], value=None)
        choices = [_report_label(r) for r in reports]
        if select_report:
            target = _report_label(select_report)
            return gr.update(choices=choices, value=target)
        return gr.update(choices=choices, value=choices[0] if choices else None)

    def _format_report(report) -> str:
        lines = [f"## {report.source_title}\n"]
        lines.append(f"**销售**：{report.sales_name}  |  **日期**：{report.created_at[:10]}")
        lines.append(f"\n**整体评价**：{report.summary}\n")
        if report.highlights:
            lines.append("### 做得好的地方")
            for i, h in enumerate(report.highlights, 1):
                lines.append(f"{i}. {h}")
            lines.append("")
        if report.improvements:
            lines.append("### 需要改进的地方")
            for i, imp in enumerate(report.improvements, 1):
                lines.append(f"{i}. {imp}")
            lines.append("")
        if report.corrected_scripts:
            lines.append("### 改进话术对照")
            for cs in report.corrected_scripts:
                lines.append(f"- **原话**：{cs.get('original', '')}")
                lines.append(f"  **改为**：{cs.get('corrected', '')}")
                lines.append(f"  **原因**：{cs.get('reason', '')}\n")
        if report.next_steps:
            lines.append("### 下一步行动建议")
            for i, ns in enumerate(report.next_steps, 1):
                lines.append(f"{i}. {ns}")
        return "\n".join(lines)

    def _load_report_context(report_choice, current_user=""):
        """根据选择加载汇报上下文（report + 原始对话内容）。"""
        from storage.report_store import ReportStore
        from storage.knowledge_store import KnowledgeStore
        if not report_choice:
            return None
        rstore = ReportStore()
        reports = rstore.list_all()
        parts = report_choice.split(" | ")
        if len(parts) < 2:
            return None
        target_id = parts[-1].strip() if len(parts) >= 4 else ""
        target_title = parts[1].strip()
        report = next((r for r in reports if target_id and r.id.startswith(target_id)), None)
        if not report:
            report = next((r for r in reports if r.source_title == target_title), None)
        if not report:
            return None
        if current_user and report not in _filter_reports_for_user([report], current_user):
            return None
        # 从知识库获取原始对话内容
        knowledge_store = KnowledgeStore()
        original_content = ""
        for entry in knowledge_store.list_by_category("customer_doc"):
            if entry.source_file == report.source_file or entry.title == report.source_title:
                original_content = entry.content
                break
        return {"report": report, "original_content": original_content}

    def delete_report(report_choice, current_user=""):
        """删除选中的面聊汇报，并同步移除对应的面聊记录知识库条目。"""
        context = _load_report_context(report_choice, current_user)
        if not context:
            return (
                "请选择要删除的汇报",
                _refresh_report_choices(current_user=current_user),
                None,
                [],
                gr.update(choices=[], value=[]),
                "",
                None,
            )

        from storage.report_store import ReportStore
        from storage.knowledge_store import KnowledgeStore

        report = context["report"]
        report_store = ReportStore()
        deleted_report = report_store.delete(report.id)

        deleted_entries = 0
        knowledge_store = KnowledgeStore()
        for entry in knowledge_store.list_by_category("customer_doc"):
            if entry.source_file == report.source_file or entry.title == report.source_title:
                if knowledge_store.delete(entry.id):
                    deleted_entries += 1

        if not deleted_report:
            message = "删除失败：未找到该汇报"
        elif deleted_entries:
            message = f"已删除汇报「{report.source_title}」，并移除{deleted_entries}条对应面聊记录"
        else:
            message = f"已删除汇报「{report.source_title}」"

        return (
            message,
            _refresh_report_choices(current_user=current_user),
            None,
            [],
            gr.update(choices=[], value=[]),
            "",
            None,
        )

    def _build_report_share_choices(report, saved_history=None):
        """Build share checkbox choices for report sections and saved chat messages."""
        saved_history = saved_history or []
        section_choices = []
        section_defaults = []
        if report.summary:
            section_choices.append("整体评价")
            section_defaults.append("整体评价")
        if report.highlights:
            section_choices.append("做得好的地方")
            section_defaults.append("做得好的地方")
        if report.improvements:
            section_choices.append("需要改进的地方")
            section_defaults.append("需要改进的地方")
        if report.corrected_scripts:
            section_choices.append("改进话术对照")
            section_defaults.append("改进话术对照")
        if report.next_steps:
            section_choices.append("下一步行动建议")
            section_defaults.append("下一步行动建议")
        for msg in saved_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            label = "销售大师" if role == "assistant" else "我"
            preview = content[:30].replace("\n", " ")
            if len(content) > 30:
                preview += "..."
            section_choices.append(f"💬 {label}：{preview}")
            section_defaults.append(f"💬 {label}：{preview}")
        return section_choices, section_defaults

    def regenerate_report(report_choice, current_user=""):
        """用已保存的原始面聊记录重新生成完整AI汇报，覆盖占位汇报。"""
        context = _load_report_context(report_choice, current_user)
        if not context:
            return "请选择要重新生成的汇报", None, [], gr.update(choices=[], value=[])

        old_report = context["report"]
        original_content = context.get("original_content") or ""
        if not original_content.strip():
            return "未找到原始面聊记录，无法重新生成", context, old_report.chat_history or [], gr.update(choices=[], value=[])

        try:
            from core.conversation_analyzer import ConversationAnalyzer
            from storage.report_store import ReportStore

            new_report = ConversationAnalyzer().analyze(
                content=original_content,
                sales_name=old_report.sales_name,
                source_file=old_report.source_file,
                source_title=old_report.source_title,
            )
            new_report.id = old_report.id
            new_report.created_at = old_report.created_at
            new_report.chat_history = old_report.chat_history
            new_report.uploader_name = getattr(old_report, "uploader_name", old_report.sales_name)
            ReportStore().save(new_report)

            saved_history = old_report.chat_history or []
            choices, defaults = _build_report_share_choices(new_report, saved_history)
            new_context = {"report": new_report, "original_content": original_content}
            return (
                _format_report(new_report),
                new_context,
                saved_history,
                gr.update(choices=choices, value=defaults),
            )
        except Exception as e:
            return (
                f"重新生成失败：{str(e)[:200]}",
                context,
                old_report.chat_history or [],
                gr.update(choices=[], value=[]),
            )

    def view_report_and_prepare_chat(report_choice, current_user=""):
        """查看汇报内容，同时加载聊天上下文和已有聊天记录，并生成分享勾选项。"""
        if not report_choice:
            return "暂无汇报", None, [], gr.update(choices=[], value=[])
        context = _load_report_context(report_choice, current_user)
        if not context:
            return "未找到汇报", None, [], gr.update(choices=[], value=[])
        report = context["report"]
        # 加载已保存的聊天记录，兼容Gradio内部格式
        saved_history = []
        for msg in (report.chat_history or []):
            role = msg.get("role", "")
            content = msg.get("content", "")
            # Gradio可能把content存为[{"text": ..., "type": "text"}]格式
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                content = "".join(text_parts)
            if role and content:
                saved_history.append({"role": role, "content": content})

        # Build share checkboxes: report sections + chat messages
        section_choices, section_defaults = _build_report_share_choices(report, saved_history)

        return (
            _format_report(report), context, saved_history,
            gr.update(choices=section_choices, value=section_defaults),
        )

    def _build_chat_system_prompt(report, original_content):
        """构建汇报问答的系统提示词，压缩原始对话到3000字。"""
        from prompts.report_chat import REPORT_CHAT_SYSTEM_PROMPT
        highlights_text = "\n".join(f"- {h}" for h in report.highlights) if report.highlights else "无"
        improvements_text = "\n".join(f"- {imp}" for imp in report.improvements) if report.improvements else "无"
        corrected_text = ""
        if report.corrected_scripts:
            for cs in report.corrected_scripts:
                corrected_text += f"- 原话：{cs.get('original', '')}\n  改为：{cs.get('corrected', '')}\n  原因：{cs.get('reason', '')}\n"
        else:
            corrected_text = "无"
        next_steps_text = "\n".join(f"- {ns}" for ns in report.next_steps) if report.next_steps else "无"

        trimmed_content = (original_content or "（未找到原始对话记录）")[:3000]

        return REPORT_CHAT_SYSTEM_PROMPT.format(
            sales_name=report.sales_name,
            source_title=report.source_title,
            summary=report.summary,
            highlights=highlights_text,
            improvements=improvements_text,
            corrected_scripts=corrected_text,
            next_steps=next_steps_text,
            conversation_content=trimmed_content,
        )

    def chat_with_report(message, history, context):
        """基于汇报上下文的问答对话，自动保存聊天记录。"""
        from core.llm_client import get_client
        if not context:
            return "", history
        if not message or not message.strip():
            return "", history

        report = context["report"]
        original_content = context["original_content"]
        system_prompt = _build_chat_system_prompt(report, original_content)

        # 从已有聊天历史中提取LLM对话格式
        chat_messages = []
        for msg in history:
            content = msg.get("content", "") if isinstance(msg, dict) else msg["content"]
            # 兼容Gradio内部格式
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            chat_messages.append({"role": msg.get("role", msg["role"]), "content": content})
        chat_messages.append({"role": "user", "content": message.strip()})

        # 加入用户消息
        history.append({"role": "user", "content": message.strip()})

        try:
            client = get_client()
            full_reply = client.chat(
                messages=chat_messages,
                system_prompt=system_prompt,
                temperature=config.EVALUATION_TEMP,
                max_tokens=1500,
            )
            history.append({"role": "assistant", "content": full_reply})

            # 保存聊天记录
            from storage.report_store import ReportStore
            rstore = ReportStore()
            rstore.save_chat_history(report.id, list(history))
        except Exception as e:
            err_msg = str(e)
            if "500" in err_msg or "allocate" in err_msg or "CUDA" in err_msg:
                friendly = "模型加载失败（GPU显存不足），请重启电脑后重试。"
            elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                friendly = "模型响应超时，请稍后重试或缩短提问。"
            else:
                friendly = f"回答失败：{err_msg}"
            history.append({"role": "assistant", "content": friendly})

        return "", history


    def _build_selected_md(context, chat_history, selected_items):
        """根据勾选项构建 Markdown 文本。"""
        if not context or not selected_items:
            return ""
        report = context["report"]

        # Separate section selections from chat message selections
        section_keys = {"整体评价", "做得好的地方", "需要改进的地方", "改进话术对照", "下一步行动建议"}
        selected_sections = [s for s in selected_items if s in section_keys]
        # Chat items start with 💬
        chat_indices = []
        for s in selected_items:
            if s.startswith("💬"):
                # Find the index of this chat message by matching content
                label_part = s.split("：", 1)[0].replace("💬 ", "")  # "销售大师" or "我"
                preview_part = s.split("：", 1)[1] if "：" in s else ""
                for i, msg in enumerate(chat_history):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    # Handle Gradio internal format where content may be a list
                    if isinstance(content, list):
                        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
                    if not isinstance(content, str):
                        content = str(content)
                    msg_label = "销售大师" if role == "assistant" else "我"
                    if msg_label == label_part and content[:30].replace("\n", " ") in preview_part:
                        if i not in chat_indices:
                            chat_indices.append(i)
                        break

        # Build report markdown with selected sections only
        lines = [f"# {report.source_title}\n"]
        lines.append(f"**销售**：{report.sales_name}  |  **日期**：{report.created_at[:10]}\n")

        if "整体评价" in selected_sections and report.summary:
            lines.append(f"## 整体评价\n{report.summary}\n")
        if "做得好的地方" in selected_sections and report.highlights:
            lines.append("## 做得好的地方")
            for i, h in enumerate(report.highlights, 1):
                lines.append(f"{i}. {h}")
            lines.append("")
        if "需要改进的地方" in selected_sections and report.improvements:
            lines.append("## 需要改进的地方")
            for i, imp in enumerate(report.improvements, 1):
                lines.append(f"{i}. {imp}")
            lines.append("")
        if "改进话术对照" in selected_sections and report.corrected_scripts:
            lines.append("## 改进话术对照")
            for cs in report.corrected_scripts:
                lines.append(f"- **原话**：{cs.get('original', '')}")
                lines.append(f"  **改为**：{cs.get('corrected', '')}")
                lines.append(f"  **原因**：{cs.get('reason', '')}\n")
        if "下一步行动建议" in selected_sections and report.next_steps:
            lines.append("## 下一步行动建议")
            for i, ns in enumerate(report.next_steps, 1):
                lines.append(f"{i}. {ns}")
            lines.append("")

        # Build selected chat messages
        if chat_indices:
            lines.append("---\n## 话术讨论记录\n")
            for idx in sorted(chat_indices):
                if idx < len(chat_history):
                    msg = chat_history[idx]
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
                    if not isinstance(content, str):
                        content = str(content)
                    if not content:
                        continue
                    label = "销售大师" if role == "assistant" else "我"
                    lines.append(f"**{label}**：{content}\n")

        return "\n".join(lines)

    def share_copy_text(context, chat_history, selected_items):
        if not context:
            return "请先查看汇报"
        if not selected_items:
            return "请勾选要分享的内容"
        md = _build_selected_md(context, chat_history, selected_items)
        return md

    def share_export_docx(context, chat_history, selected_items):
        from utils.share import export_as_docx
        if not context or not selected_items:
            return None
        report = context["report"]
        md = _build_selected_md(context, chat_history, selected_items)
        if not md.strip():
            return None
        path = export_as_docx(md, title=f"面聊汇报_{report.sales_name}")
        return path

    def share_export_image(context, chat_history, selected_items):
        from utils.share import generate_image
        if not context or not selected_items:
            return None
        report = context["report"]
        md = _build_selected_md(context, chat_history, selected_items)
        if not md.strip():
            return None
        path = generate_image(md, title=f"面聊汇报 · {report.sales_name}")
        return path

    def share_generate_link(context, chat_history, selected_items):
        from utils.share import generate_share_link
        if not context:
            return "请先查看汇报"
        if not selected_items:
            return "请勾选要分享的内容"
        report = context["report"]
        md = _build_selected_md(context, chat_history, selected_items)
        url = generate_share_link(md, title=f"面聊汇报 · {report.sales_name}")
        return url

    provider_info = (
        "**本地模型模式**：数据不出本机，零出网"
        if config.LLM_PROVIDER == "ollama"
        else "**云端API模式**：发送前自动脱敏"
    )

    gr.Markdown("## 风格管理")
    gr.Markdown(f"上传销售对话文件，AI将自动提取销售风格特征。最多支持4种风格。\n\n{provider_info}")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 上传与提取")
            file_input = gr.File(label="上传销售对话文件", file_types=[".txt", ".csv", ".json", ".docx", ".doc", ".pdf", ".pptx", ".ppt"])
            style_name_input = gr.Textbox(label="风格名称（可选，留空自动生成）", placeholder="如：顾问式")
            with gr.Row():
                preview_btn = gr.Button("预览脱敏")
                extract_btn = gr.Button("提取风格", variant="primary")
            import_kb_btn = gr.Button("从知识库导入", variant="secondary")
            import_kb_result = gr.Textbox(label="导入结果", lines=5, interactive=False)
            preview_result = gr.Textbox(label="脱敏预览", lines=6, interactive=False)
            extract_result = gr.Textbox(label="提取结果", lines=3, interactive=False)
            gr.Markdown("### 支持的文件格式")
            gr.Markdown("- **TXT**：每行以\"销售：\"或\"客户：\"开头\n- **CSV**：包含 speaker 和 content 列\n- **JSON**：数组格式，含 role 和 content 字段\n- **Word**：.docx/.doc 对话记录或话术文档\n- **PDF**：对话记录或品牌资料\n- **PPT**：.pptx/.ppt 培训课件或方案展示")

        with gr.Column(scale=1):
            gr.Markdown("### 我的风格档案")
            styles_display = gr.HTML(
                value=_refresh_styles_table(),
            )
            with gr.Row():
                delete_style_dropdown = gr.Dropdown(label="选择风格", choices=get_style_names(), scale=3)
                delete_style_btn = gr.Button("删除", variant="stop", scale=1)
            with gr.Row():
                merge_a = gr.Dropdown(label="风格A", choices=get_style_names(), scale=2)
                merge_b = gr.Dropdown(label="风格B", choices=get_style_names(), scale=2)
                merge_style_btn = gr.Button("合并", variant="secondary", scale=1)
            style_action_result = gr.Markdown("")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 风格对比")
            with gr.Row():
                style_a = gr.Dropdown(label="风格A", choices=get_style_names(), scale=1)
                style_b = gr.Dropdown(label="风格B", choices=get_style_names(), scale=1)
            compare_btn = gr.Button("对比分析")
            compare_result = gr.Markdown()

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 面聊汇报")
            from storage.report_store import ReportStore
            report_store_init = ReportStore()
            report_choices = [
                _report_label(r)
                for r in report_store_init.list_all()
            ]
            report_dropdown = gr.Dropdown(
                choices=report_choices,
                value=report_choices[0] if report_choices else None,
                label="选择汇报",
            )
            with gr.Row():
                view_report_btn = gr.Button("查看汇报", variant="primary", scale=2)
                regenerate_report_btn = gr.Button("重新生成汇报", variant="secondary", scale=2)
                delete_report_btn = gr.Button("删除汇报", variant="stop", scale=1)
            report_display = gr.Markdown()
            report_context = gr.State(None)

            gr.Markdown("### 分享汇报")
            share_select = gr.CheckboxGroup(label="选择要分享的内容", choices=[], value=[])
            with gr.Row():
                share_copy_btn = gr.Button("复制文本", scale=1)
                share_docx_btn = gr.Button("导出Word", scale=1)
                share_image_btn = gr.Button("生成图片", scale=1)
            share_text_output = gr.Textbox(label="复制内容", visible=True, interactive=False, lines=3)
            share_file_output = gr.File(label="下载文件", visible=True)

            gr.Markdown("### 与销售大师讨论")
            gr.Markdown("选择汇报后，可以就这次面聊向AI教练提问，获取具体的跟进建议和话术优化。")
            report_chatbot = gr.Chatbot(height=350, label="面聊复盘对话")
            report_chat_input = gr.Textbox(
                placeholder="如：下一步怎么跟进这个客户？这个异议该怎么回应？",
                label="提问",
            )

    _user_state = user_dropdown or gr.State("")
    _login_state = login_user_state or gr.State("")

    preview_btn.click(fn=preview_before_extract, inputs=[file_input], outputs=[preview_result, extract_result])
    extract_btn.click(fn=upload_and_extract, inputs=[file_input, style_name_input, _user_state], outputs=[extract_result, styles_display, delete_style_dropdown, merge_a, merge_b, report_dropdown, report_display, report_context, report_chatbot, share_select])
    import_kb_btn.click(fn=import_from_knowledge_base, inputs=[_user_state], outputs=[import_kb_result, styles_display, report_dropdown])

    def delete_style(label, current_user="", login_username=""):
        if not _is_admin_login(login_username):
            style_names = get_style_names(current_user)
            return "仅管理员可以删除风格", _refresh_styles_table(current_user), gr.update(choices=style_names), gr.update(choices=style_names), gr.update(choices=style_names)
        name = _parse_style_name(label)
        if not name:
            return "请选择要删除的风格", _refresh_styles_table(current_user), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user))
        # Delete ALL profiles with this name (handles duplicates)
        profiles = store.list_all()
        deleted_count = 0
        for p in profiles:
            if p.name == name:
                store.delete(p.id)
                deleted_count += 1
        if deleted_count:
            new_names = get_style_names(current_user)
            return f"已删除{deleted_count}个「{name}」", _refresh_styles_table(current_user), gr.update(choices=new_names), gr.update(choices=new_names), gr.update(choices=new_names)
        return f"未找到「{name}」", _refresh_styles_table(current_user), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user))

    def merge_styles(label_a, label_b, current_user="", login_username=""):
        if not _is_admin_login(login_username):
            style_names = get_style_names(current_user)
            return "仅管理员可以合并风格", _refresh_styles_table(current_user), gr.update(choices=style_names), gr.update(choices=style_names), gr.update(choices=style_names)
        name_a = _parse_style_name(label_a)
        name_b = _parse_style_name(label_b)
        if not name_a or not name_b:
            return "请选择两个风格进行合并", _refresh_styles_table(current_user), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user))
        if name_a == name_b:
            return "请选择不同的风格", _refresh_styles_table(current_user), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user))
        profiles = store.list_all()
        pa_list = [p for p in profiles if p.name == name_a]
        pb_list = [p for p in profiles if p.name == name_b]
        if not pa_list or not pb_list:
            return "未找到所选风格", _refresh_styles_table(current_user), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user)), gr.update(choices=get_style_names(current_user))
        pa, pb = pa_list[0], pb_list[0]
        merged_name = name_a.replace("面聊式", "").replace("式", "") + "式"
        store.merge(pa, pb, merged_name=merged_name)
        new_names = get_style_names(current_user)
        return f"已合并为「{merged_name}」", _refresh_styles_table(current_user), gr.update(choices=new_names), gr.update(choices=new_names), gr.update(choices=new_names)

    def refresh_for_user(current_user=""):
        style_names = get_style_names(current_user)
        return (
            _refresh_styles_table(current_user),
            gr.update(choices=style_names, value=None),
            gr.update(choices=style_names, value=None),
            gr.update(choices=style_names, value=None),
            gr.update(choices=style_names, value=None),
            gr.update(choices=style_names, value=None),
            _refresh_report_choices(current_user=current_user),
        )

    delete_style_btn.click(fn=delete_style, inputs=[delete_style_dropdown, _user_state, _login_state], outputs=[style_action_result, styles_display, delete_style_dropdown, merge_a, merge_b])
    merge_style_btn.click(fn=merge_styles, inputs=[merge_a, merge_b, _user_state, _login_state], outputs=[style_action_result, styles_display, delete_style_dropdown, merge_a, merge_b])

    compare_btn.click(fn=compare_styles, inputs=[style_a, style_b], outputs=[compare_result])
    view_report_btn.click(fn=view_report_and_prepare_chat, inputs=[report_dropdown, _user_state], outputs=[report_display, report_context, report_chatbot, share_select])
    regenerate_report_btn.click(fn=regenerate_report, inputs=[report_dropdown, _user_state], outputs=[report_display, report_context, report_chatbot, share_select])
    delete_report_btn.click(fn=delete_report, inputs=[report_dropdown, _user_state], outputs=[report_display, report_dropdown, report_context, report_chatbot, share_select, share_text_output, share_file_output])
    if user_dropdown is not None:
        user_dropdown.change(
            fn=refresh_for_user,
            inputs=[user_dropdown],
            outputs=[styles_display, delete_style_dropdown, merge_a, merge_b, style_a, style_b, report_dropdown],
        )
    report_chat_input.submit(fn=chat_with_report, inputs=[report_chat_input, report_chatbot, report_context], outputs=[report_chat_input, report_chatbot])
    share_copy_btn.click(fn=share_copy_text, inputs=[report_context, report_chatbot, share_select], outputs=[share_text_output])
    share_docx_btn.click(fn=share_export_docx, inputs=[report_context, report_chatbot, share_select], outputs=[share_file_output])
    share_image_btn.click(fn=share_export_image, inputs=[report_context, report_chatbot, share_select], outputs=[share_file_output])
