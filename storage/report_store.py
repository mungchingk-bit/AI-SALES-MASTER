"""面聊汇报存储模块。"""
import json
import os

import config
from models.conversation_report import ConversationReport


class ReportStore:
    def __init__(self):
        self.reports_dir = config.REPORTS_DIR

    def save(self, report: ConversationReport) -> str:
        path = os.path.join(self.reports_dir, f"{report.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        return report.id

    def load(self, report_id: str) -> ConversationReport | None:
        path = os.path.join(self.reports_dir, f"{report_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return ConversationReport.from_dict(json.load(f))

    def list_all(self) -> list[ConversationReport]:
        reports = []
        if not os.path.exists(self.reports_dir):
            return reports
        for filename in os.listdir(self.reports_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.reports_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        reports.append(ConversationReport.from_dict(json.load(f)))
                except Exception:
                    continue
        return sorted(reports, key=lambda r: r.created_at, reverse=True)

    def list_by_sales(self, sales_name: str) -> list[ConversationReport]:
        return [r for r in self.list_all() if r.sales_name == sales_name]

    def delete(self, report_id: str) -> bool:
        path = os.path.join(self.reports_dir, f"{report_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def save_chat_history(self, report_id: str, chat_history: list) -> bool:
        """保存汇报的聊天历史。"""
        report = self.load(report_id)
        if not report:
            return False
        report.chat_history = chat_history
        self.save(report)
        return True
