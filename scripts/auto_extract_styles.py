"""启动时从知识库自动提取销售风格，同名销售自动合并。"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.style_extractor import StyleExtractor
from core.conversation_analyzer import ConversationAnalyzer
from core.llm_client import get_client
from storage.knowledge_store import KnowledgeStore
from storage.style_store import StyleStore
from storage.report_store import ReportStore
from models.chat_message import ChatMessage
from models.style_profile import StyleProfile

import config


def _extract_sales_name(title: str) -> str | None:
    """从标题中提取销售名字（如'销售CC话术库'→'CC'）。"""
    match = re.search(r"销售(\w+)", title)
    return match.group(1) if match else None


def auto_extract_styles():
    """从知识库中已有的资料自动提取销售风格，同名销售自动合并。"""
    knowledge_store = KnowledgeStore()
    style_store = StyleStore()
    report_store = ReportStore()
    extractor = StyleExtractor()
    analyzer = ConversationAnalyzer()

    # 已有汇报的 source_file 集合，避免重复生成
    existing_reports = {r.source_file for r in report_store.list_all()}

    existing = style_store.list_all()
    # name_map: 销售名字 → StyleProfile（用于合并）
    name_map = {p.name.replace("式", "").replace("面聊", ""): p for p in existing}

    # 1. 从话术库提取风格
    scripts = knowledge_store.list_by_category("script_library")
    for entry in scripts:
        sales_name = _extract_sales_name(entry.title)
        if not sales_name:
            continue

        style_name = f"{sales_name}式"
        if sales_name in name_map and entry.source_file in name_map[sales_name].source_file:
            print(f"[跳过] 风格「{style_name}」已存在（话术库）")
            continue

        print(f"[提取] 从话术库提取{entry.title}的销售风格...")
        try:
            content = entry.content[:5000]
            messages = [ChatMessage(role="user", content=content)]
            profile = extractor.extract(messages, source_file=entry.source_file)
            profile.name = style_name

            if sales_name in name_map:
                # 已有同名销售，合并
                existing_profile = name_map[sales_name]
                merged = style_store.merge(existing_profile, profile, merged_name=style_name)
                name_map[sales_name] = merged
                print(f"  [合并] 风格「{style_name}」已与现有档案合并")
            else:
                style_store.save(profile)
                name_map[sales_name] = profile
                print(f"  [成功] 风格「{profile.name}」: {profile.description}")
        except Exception as e:
            print(f"  [失败] {str(e)}")

    # 2. 从面聊记录提取风格
    chats = knowledge_store.list_by_category("customer_doc")
    for entry in chats:
        sales_name = _extract_sales_name(entry.title)
        if not sales_name:
            continue

        style_name = f"{sales_name}式"
        print(f"[提取] 从面聊记录提取{entry.title}的销售风格...")
        try:
            content = entry.content[:8000]
            messages = [ChatMessage(role="user", content=content)]
            profile = extractor.extract(messages, source_file=entry.source_file)
            profile.name = f"{sales_name}面聊式"

            if sales_name in name_map:
                # 已有同名销售，合并
                existing_profile = name_map[sales_name]
                merged = style_store.merge(existing_profile, profile, merged_name=style_name)
                name_map[sales_name] = merged
                print(f"  [合并] 风格「{style_name}」已与话术库档案合并")
            else:
                profile.name = style_name
                style_store.save(profile)
                name_map[sales_name] = profile
                print(f"  [成功] 风格「{profile.name}」: {profile.description}")
        except Exception as e:
            print(f"  [失败] {str(e)}")

        # 生成面聊汇报
        if entry.source_file not in existing_reports:
            print(f"[汇报] 分析{entry.title}的面聊表现...")
            try:
                report = analyzer.analyze(
                    content=entry.content,
                    sales_name=sales_name,
                    source_file=entry.source_file,
                    source_title=entry.title,
                )
                report_store.save(report)
                existing_reports.add(entry.source_file)
                print(f"  [成功] 汇报已生成：{report.summary}")
            except Exception as e:
                print(f"  [失败] 汇报生成失败: {str(e)}")
        else:
            print(f"[跳过] {entry.title}的汇报已存在")

    # 3. 从公司简介构建上下文（不需要提取风格，但确认存在）
    profiles = knowledge_store.list_by_category("company_profile")
    for entry in profiles:
        print(f"[确认] 公司简介已就绪: {entry.title}")

    # 汇总
    all_styles = style_store.list_all()
    print(f"\n当前风格档案共 {len(all_styles)} 个：")
    for p in all_styles:
        print(f"  - {p.name}: {p.description}")

    all_reports = report_store.list_all()
    print(f"当前面聊汇报共 {len(all_reports)} 个：")
    for r in all_reports:
        print(f"  - {r.sales_name} | {r.source_title} | {r.summary[:50]}")


if __name__ == "__main__":
    auto_extract_styles()
