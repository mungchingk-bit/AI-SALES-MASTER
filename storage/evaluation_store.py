import json
import os

import config
from models.evaluation_report import EvaluationReport


class EvaluationStore:
    def __init__(self):
        self.evaluations_dir = config.EVALUATIONS_DIR

    def save(self, report: EvaluationReport) -> str:
        path = os.path.join(self.evaluations_dir, f"{report.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        return report.id

    def load(self, report_id: str) -> EvaluationReport | None:
        path = os.path.join(self.evaluations_dir, f"{report_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return EvaluationReport.from_dict(data)

    def load_by_session(self, session_id: str) -> EvaluationReport | None:
        for filename in os.listdir(self.evaluations_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.evaluations_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("session_id") == session_id:
                    return EvaluationReport.from_dict(data)
        return None

    def list_all(self) -> list[EvaluationReport]:
        reports = []
        if not os.path.exists(self.evaluations_dir):
            return reports
        for filename in os.listdir(self.evaluations_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.evaluations_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reports.append(EvaluationReport.from_dict(data))
        return sorted(reports, key=lambda r: r.created_at, reverse=True)
