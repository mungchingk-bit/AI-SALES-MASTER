import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

import config
from core.llm_client import get_client
from prompts.file_discussion import (
    FILE_DISCUSSION_SYSTEM_PROMPT,
    FILE_DISCUSSION_TOO_LONG_NOTE,
    FILE_SUMMARY_PROMPT,
)
from utils.file_parser import extract_text
from utils.text_utils import estimate_tokens, truncate_to_token_limit


@dataclass
class FileSession:
    """Per-channel file discussion state."""
    channel_id: int
    filename: str
    file_type: str
    file_content: str
    file_summary: str
    conversation: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FileDiscussionManager:
    def __init__(self):
        self.client = get_client()
        self._sessions: dict[int, FileSession] = {}
        self.download_dir = config.FILE_DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)

    async def process_attachment(self, channel_id: int, attachment) -> FileSession | None:
        ext = attachment.filename.lower().split(".")[-1]
        if ext not in config.SUPPORTED_FILE_EXTENSIONS:
            return None

        if attachment.size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
            return None

        file_path = os.path.join(self.download_dir, f"{channel_id}_{attachment.filename}")
        await attachment.save(file_path)

        try:
            text = extract_text(file_path)
            if text.startswith("[无法解析") or text.startswith("[无法进行") or text.startswith("[OCR"):
                return None

            full_content = text
            if estimate_tokens(text) > config.MAX_CHUNK_TOKENS:
                text = truncate_to_token_limit(text, config.MAX_CHUNK_TOKENS) + FILE_DISCUSSION_TOO_LONG_NOTE

            file_type = self._get_file_type_label(ext)
            summary = self._generate_summary(attachment.filename, file_type, full_content)

            session = FileSession(
                channel_id=channel_id,
                filename=attachment.filename,
                file_type=file_type,
                file_content=text,
                file_summary=summary,
            )
            self._sessions[channel_id] = session
            return session

        except Exception as e:
            logging.error(f"Error processing attachment: {e}")
            return None
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass

    def answer_question(self, channel_id: int, question: str) -> str | None:
        session = self._sessions.get(channel_id)
        if not session:
            return None

        system_prompt = FILE_DISCUSSION_SYSTEM_PROMPT.format(
            filename=session.filename,
            file_type=session.file_type,
            file_summary=session.file_summary,
            file_content=session.file_content,
        )

        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": msg}
            for i, msg in enumerate(session.conversation)
        ]
        messages.append({"role": "user", "content": question})

        try:
            response = self.client.chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=2048,
            )
            session.conversation.append(question)
            session.conversation.append(response)
            return response
        except Exception as e:
            logging.error(f"Error answering file question: {e}")
            return f"处理你的问题时出错了：{str(e)}"

    def end_session(self, channel_id: int) -> bool:
        if channel_id in self._sessions:
            del self._sessions[channel_id]
            return True
        return False

    def has_session(self, channel_id: int) -> bool:
        return channel_id in self._sessions

    def get_session(self, channel_id: int) -> FileSession | None:
        return self._sessions.get(channel_id)

    def _generate_summary(self, filename: str, file_type: str, content: str) -> str:
        prompt = FILE_SUMMARY_PROMPT.format(
            filename=filename,
            file_type=file_type,
            file_content=content,
        )
        try:
            return self.client.chat(
                messages=[],
                system_prompt=prompt,
                temperature=config.EXTRACTION_TEMP,
                max_tokens=2048,
            )
        except Exception as e:
            logging.error(f"Error generating summary: {e}")
            return f"摘要生成失败：{str(e)}"

    def _get_file_type_label(self, ext: str) -> str:
        labels = {
            "docx": "Word文档", "doc": "Word文档",
            "pdf": "PDF文档",
            "xlsx": "Excel表格", "xls": "Excel表格",
            "pptx": "PowerPoint演示", "ppt": "PowerPoint演示",
            "txt": "文本文件", "csv": "CSV表格", "json": "JSON文件",
            "jpg": "图片", "jpeg": "图片", "png": "图片",
        }
        return labels.get(ext, "未知类型")
