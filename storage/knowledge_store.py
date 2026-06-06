"""知识库模块 — 存储公司简介、备婚文件、宴会场景等非对话资料。"""
import json
import os
import uuid
from datetime import datetime

import config


class KnowledgeEntry:
    def __init__(self, title: str, content: str, category: str, source_file: str = "",
                 uploader_id: str = "", uploader_name: str = "",
                 id: str | None = None, created_at: str | None = None):
        self.id = id or str(uuid.uuid4())
        self.title = title
        self.content = content
        self.category = category  # "company_profile" | "customer_doc" | "banquet_type" | "script_library"
        self.source_file = source_file
        self.uploader_id = str(uploader_id)
        self.uploader_name = uploader_name
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "content": self.content,
            "category": self.category, "source_file": self.source_file,
            "uploader_id": self.uploader_id, "uploader_name": self.uploader_name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id"), title=data["title"], content=data["content"],
            category=data["category"], source_file=data.get("source_file", ""),
            uploader_id=data.get("uploader_id", ""), uploader_name=data.get("uploader_name", ""),
            created_at=data.get("created_at"),
        )


class KnowledgeStore:
    def __init__(self):
        self.knowledge_dir = os.path.join(config.DATA_DIR, "knowledge")
        os.makedirs(self.knowledge_dir, exist_ok=True)

    def save(self, entry: KnowledgeEntry) -> str:
        # Deduplicate by title + category
        for existing in self.list_by_category(entry.category):
            if existing.title == entry.title:
                self.delete(existing.id)
                break
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

    def list_by_user(self, user_name: str, is_admin: bool = False) -> list[KnowledgeEntry]:
        """List entries visible to a user. Admin sees all; others see their own + shared (empty uploader_id)."""
        entries = self.list_all()
        if is_admin:
            return entries
        return [e for e in entries if not e.uploader_id or e.uploader_name == user_name]

    def delete(self, entry_id: str) -> bool:
        path = os.path.join(self.knowledge_dir, f"{entry_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def build_context(self, category: str | None = None, max_chars: int = 0) -> str:
        """Build a context string from knowledge entries for prompt injection.

        Args:
            category: Filter by category, or None for all.
            max_chars: If > 0, truncate total output to this many chars.
                       Prioritizes newer entries and ensures all entries
                       get at least a summary included.
        """
        if category:
            entries = self.list_by_category(category)
        else:
            entries = self.list_all()

        if not entries:
            return ""

        if max_chars <= 0:
            parts = []
            for entry in entries:
                parts.append(f"## {entry.title}\n{entry.content}")
            return "\n\n".join(parts)

        # Smart truncation: try to include all entries proportionally
        separator_len = 4  # "\n\n" between entries
        header_overhead = 50  # safety margin for "## title\n"
        available = max_chars

        # First pass: calculate total raw length
        raw_parts = [(f"## {entry.title}\n{entry.content}", entry) for entry in entries]
        total_raw = sum(len(p[0]) for p in raw_parts)

        if total_raw <= available:
            return "\n\n".join(p[0] for p in raw_parts)

        # Second pass: allocate space proportionally, ensure each entry
        # gets at least 100 chars (title + beginning of content)
        min_per_entry = 100
        n = len(entries)
        budget_per = max(min_per_entry, (available - (n - 1) * separator_len) // n)

        parts = []
        for raw, entry in raw_parts:
            alloc = min(len(raw), budget_per)
            if alloc < len(raw):
                truncated = raw[:alloc] + "\n...(已压缩)"
            else:
                truncated = raw
            parts.append(truncated)

        result = "\n\n".join(parts)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n...(已截断)"
        return result
