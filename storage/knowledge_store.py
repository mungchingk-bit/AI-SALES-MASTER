"""知识库模块 — 存储公司简介、备婚文件、宴会场景等非对话资料。"""
import json
import os
import uuid
from datetime import datetime

import config


class KnowledgeEntry:
    def __init__(self, title: str, content: str, category: str, source_file: str = "",
                 id: str | None = None, created_at: str | None = None):
        self.id = id or str(uuid.uuid4())
        self.title = title
        self.content = content
        self.category = category  # "company_profile" | "customer_doc" | "banquet_type" | "script_library"
        self.source_file = source_file
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "content": self.content,
            "category": self.category, "source_file": self.source_file,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id"), title=data["title"], content=data["content"],
            category=data["category"], source_file=data.get("source_file", ""),
            created_at=data.get("created_at"),
        )


class KnowledgeStore:
    def __init__(self):
        self.knowledge_dir = os.path.join(config.DATA_DIR, "knowledge")
        os.makedirs(self.knowledge_dir, exist_ok=True)

    def save(self, entry: KnowledgeEntry) -> str:
        path = os.path.join(self.knowledge_dir, f"{entry.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)
        return entry.id

    def load(self, entry_id: str) -> KnowledgeEntry | None:
        path = os.path.join(self.knowledge_dir, f"{entry_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return KnowledgeEntry.from_dict(json.load(f))

    def list_by_category(self, category: str) -> list[KnowledgeEntry]:
        entries = []
        for filename in os.listdir(self.knowledge_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.knowledge_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("category") == category:
                entries.append(KnowledgeEntry.from_dict(data))
        return entries

    def list_all(self) -> list[KnowledgeEntry]:
        entries = []
        for filename in os.listdir(self.knowledge_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.knowledge_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                entries.append(KnowledgeEntry.from_dict(json.load(f)))
        return sorted(entries, key=lambda e: e.created_at, reverse=True)

    def delete(self, entry_id: str) -> bool:
        path = os.path.join(self.knowledge_dir, f"{entry_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def build_context(self, category: str | None = None) -> str:
        """Build a context string from knowledge entries for prompt injection."""
        if category:
            entries = self.list_by_category(category)
        else:
            entries = self.list_all()

        if not entries:
            return ""

        parts = []
        for entry in entries:
            parts.append(f"## {entry.title}\n{entry.content}")
        return "\n\n".join(parts)
