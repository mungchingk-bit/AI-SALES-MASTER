"""导入知识库脚本 — 将桌面资料导入AI销售训练系统。

使用方式：
    cd AI_SALES_MASTER
    pip install python-docx PyMuPDF
    python scripts/import_knowledge.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.file_parser import extract_text
from storage.knowledge_store import KnowledgeStore, KnowledgeEntry

SOURCE_DIR = r"C:\Users\admin\Desktop\AI SALES MASTER"


def import_all():
    store = KnowledgeStore()
    imported = 0

    # 1. 销售话术库 → script_library
    script_files = [
        ("婚礼顾问实战话术库", "销售CC-婚礼顾问实战话术库《从品牌初识到决策签约的问题集锦》.docx", "CC"),
        ("婚礼顾问实战话术库", "销售免免-婚礼顾问实战话术库《从品牌初识到决策签约的问题集锦》.docx", "免免"),
        ("婚礼顾问实战话术库", "销售茉莉-婚礼顾问实战话术库《从品牌初识到决策签约的问题集锦》.docx", "茉莉"),
    ]

    for subfolder, filename, sales_name in script_files:
        path = os.path.join(SOURCE_DIR, subfolder, filename)
        if not os.path.exists(path):
            print(f"[跳过] 文件不存在: {filename}")
            continue

        print(f"[导入] 销售话术库 - {sales_name}...")
        text = extract_text(path)
        if text.startswith("[无法解析"):
            print(f"  [失败] {text}")
            continue

        entry = KnowledgeEntry(
            title=f"销售{sales_name}话术库",
            content=text,
            category="script_library",
            source_file=filename,
        )
        store.save(entry)
        imported += 1
        print(f"  [成功] {len(text)} 字符")

    # 2. 公司简介 → company_profile
    profile_files = [
        ("客户初面工具包/公司简介", "克拉时刻婚礼公司简介2025版（繁体版）.pdf", "克拉时刻公司简介"),
        ("客户初面工具包/公司简介", "栀夏婚礼品牌简介.pdf", "栀夏品牌简介"),
    ]

    for subfolder, filename, title in profile_files:
        path = os.path.join(SOURCE_DIR, subfolder, filename)
        if not os.path.exists(path):
            print(f"[跳过] 文件不存在: {filename}")
            continue

        print(f"[导入] 公司简介 - {title}...")
        text = extract_text(path)
        if text.startswith("[无法解析"):
            print(f"  [失败] {text}")
            continue

        entry = KnowledgeEntry(
            title=title,
            content=text,
            category="company_profile",
            source_file=filename,
        )
        store.save(entry)
        imported += 1
        print(f"  [成功] {len(text)} 字符")

    # 3. 线下面聊记录 → customer_doc
    chat_files = [
        ("线下面聊语音转文字记录", "编号0001-广东婚礼策划与服务策略探讨-销售丸子.docx", "广东婚礼策划-销售丸子"),
        ("线下面聊语音转文字记录", "编号0002-深圳保利洲际展厅布局与运营细节解析-销售免免.docx", "深圳保利洲际-销售免免"),
        ("线下面聊语音转文字记录", "编号7150-婚礼策划与服务流程详解-销售免免.docx", "婚礼策划流程-销售免免"),
        ("线下面聊语音转文字记录", "编号G3886-20260430婚礼策划方案及服务流程沟通会-销售免免.docx", "婚礼策划沟通会-销售免免"),
        ("线下面聊语音转文字记录", "客户编号0003-马蹄莲法则下的婚礼策划与服务流程-销售免免.docx", "马蹄莲法则婚礼策划-销售免免"),
        ("线下面聊语音转文字记录", "客户编号0004-建筑设计与策划的多元方案-销售免免.docx", "建筑设计与策划方案-销售免免"),
        ("线下面聊语音转文字记录", "客户编号7143-京都庭院主题婚宴装饰构思-销售免免.docx", "京都庭院婚宴构思-销售免免"),
        ("线下面聊语音转文字记录", "客户编号0005-婚礼策划顾问的分享与挑战-销售免免.docx", "婚礼策划顾问分享与挑战-销售免免"),
    ]

    for subfolder, filename, title in chat_files:
        path = os.path.join(SOURCE_DIR, subfolder, filename)
        if not os.path.exists(path):
            print(f"[跳过] 文件不存在: {filename}")
            continue

        print(f"[导入] 面聊记录 - {title}...")
        text = extract_text(path)
        if text.startswith("[无法解析"):
            print(f"  [失败] {text}")
            continue

        entry = KnowledgeEntry(
            title=title,
            content=text,
            category="customer_doc",
            source_file=filename,
        )
        store.save(entry)
        imported += 1
        print(f"  [成功] {len(text)} 字符")

    # 4. 策划方案 → banquet_type
    banquet_files = [
        ("客户初面工具包/四季", "策划方案.pdf", "四季酒店婚礼策划方案-法式庄园风格"),
    ]

    for subfolder, filename, title in banquet_files:
        path = os.path.join(SOURCE_DIR, subfolder, filename)
        if not os.path.exists(path):
            print(f"[跳过] 文件不存在: {filename}")
            continue

        print(f"[导入] 宴会方案 - {title}...")
        text = extract_text(path)
        if text.startswith("[无法解析"):
            print(f"  [失败] {text}")
            continue

        entry = KnowledgeEntry(
            title=title,
            content=text,
            category="banquet_type",
            source_file=filename,
        )
        store.save(entry)
        imported += 1
        print(f"  [成功] {len(text)} 字符")

    print(f"\n导入完成！共导入 {imported} 个文件到知识库。")


if __name__ == "__main__":
    import_all()
