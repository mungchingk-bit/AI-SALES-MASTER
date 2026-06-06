"""给现有知识库条目补 uploader_id，从 title/source_file 推断归属。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

KNOWLEDGE_DIR = os.path.join(config.DATA_DIR, "knowledge")
SALES_USERS = [u.strip() for u in config.SALES_USERS if u.strip()]


def infer_owner(title: str, source_file: str) -> tuple[str, str]:
    """从 title/source_file 推断归属用户。返回 (uploader_id, uploader_name)。"""
    text = f"{title} {source_file}".lower()
    for name in SALES_USERS:
        if name.lower() in text:
            return "", name  # uploader_id 为空，用 name 匹配
    # 无法推断的归属 admin（公共）
    return "", ""


def main():
    updated = 0
    for filename in os.listdir(KNOWLEDGE_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(KNOWLEDGE_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("uploader_id") or data.get("uploader_name"):
            continue  # 已有归属

        uid, uname = infer_owner(data.get("title", ""), data.get("source_file", ""))
        data["uploader_id"] = uid
        data["uploader_name"] = uname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        label = uname or "公共/管理员"
        print(f"  {filename}: 归属 -> {label}")
        updated += 1

    print(f"\n更新了 {updated} 条条目")


if __name__ == "__main__":
    main()
