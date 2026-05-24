"""文档存储 — 持久化上传的文档，按编号管理，支持权限控制。"""
import json
import os
from datetime import datetime

import config


class DocEntry:
    def __init__(self, number: int, filename: str, file_type: str, content: str,
                 summary: str, uploader_id: str, uploader_name: str = "",
                 conversation: list | None = None, created_at: str | None = None):
        self.number = number
        self.filename = filename
        self.file_type = file_type
        self.content = content
        self.summary = summary
        self.uploader_id = str(uploader_id)
        self.uploader_name = uploader_name
        self.conversation = conversation or []
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self):
        return {
            "number": self.number, "filename": self.filename, "file_type": self.file_type,
            "content": self.content, "summary": self.summary,
            "uploader_id": self.uploader_id, "uploader_name": self.uploader_name,
            "conversation": self.conversation, "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            number=data["number"], filename=data["filename"], file_type=data["file_type"],
            content=data["content"], summary=data["summary"],
            uploader_id=data["uploader_id"], uploader_name=data.get("uploader_name", ""),
            conversation=data.get("conversation", []), created_at=data.get("created_at", ""),
        )


class DocStore:
    def __init__(self):
        self.file_path = os.path.join(config.DATA_DIR, "documents.json")
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load(self) -> list[dict]:
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, entries: list[dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def _next_number(self) -> int:
        entries = self._load()
        if not entries:
            return 1
        return max(e["number"] for e in entries) + 1

    def add(self, filename: str, file_type: str, content: str, summary: str,
            uploader_id: str, uploader_name: str = "") -> DocEntry:
        number = self._next_number()
        entry = DocEntry(
            number=number, filename=filename, file_type=file_type,
            content=content, summary=summary,
            uploader_id=uploader_id, uploader_name=uploader_name,
        )
        entries = self._load()
        entries.append(entry.to_dict())
        self._save(entries)
        return entry

    def get(self, number: int) -> DocEntry | None:
        entries = self._load()
        for e in entries:
            if e["number"] == number:
                return DocEntry.from_dict(e)
        return None

    def update_conversation(self, number: int, question: str, answer: str):
        entries = self._load()
        for e in entries:
            if e["number"] == number:
                e["conversation"].append(question)
                e["conversation"].append(answer)
                break
        self._save(entries)

    def list_by_user(self, user_id: str, is_admin: bool = False) -> list[DocEntry]:
        entries = self._load()
        results = []
        for e in entries:
            if is_admin or str(e["uploader_id"]) == str(user_id):
                results.append(DocEntry.from_dict(e))
        return results

    def delete(self, number: int) -> bool:
        entries = self._load()
        new_entries = [e for e in entries if e["number"] != number]
        if len(new_entries) == len(entries):
            return False
        self._save(new_entries)
        return True
