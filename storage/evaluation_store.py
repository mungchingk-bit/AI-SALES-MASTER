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

    def build_correction_guide(self, user: str = "", max_chars: int = 2000) -> str:
        """Build a correction guide from historical corrections for injection into evaluation prompts."""
        reports = self.list_all()
        corrected = [r for r in reports if r.is_corrected]
        if user:
            corrected = [r for r in corrected if r.corrected_by == user]
        if not corrected:
            return ""

        # Group corrections by dimension
        dim_corrections = {}
        for report in corrected:
            for dim, corr in report.corrections.items():
                if dim not in dim_corrections:
                    dim_corrections[dim] = []
                dim_corrections[dim].append(corr)

        lines = ["## 评分标准补充（基于历史修正记录）\n"]
        lines.append("以下是用户对AI评估的修正，代表团队的真实评分标准。请严格参照：\n")
        total_len = len("\n".join(lines))

        for dim, corrs in dim_corrections.items():
            # Only last 5 corrections per dimension
            recent = corrs[-5:]
            dim_lines = [f"### {dim}"]
            for corr in recent:
                orig_score = corr.get("original_score", 0)
                new_score = corr.get("corrected_score", 0)
                diff = new_score - orig_score
                direction = "偏低" if diff > 0 else "偏高"
                line = f"- AI原评{orig_score}分→修正{new_score}分（AI{direction}）"
                corrected_just = corr.get("corrected_justification", "")
                orig_just = corr.get("original_justification", "")
                if corrected_just and corrected_just != orig_just:
                    line += f"\n  修正理由：{corrected_just[:100]}"
                dim_lines.append(line)
            dim_lines.append("")
            dim_text = "\n".join(dim_lines) + "\n"
            if total_len + len(dim_text) > max_chars:
                break
            lines.extend(dim_lines)
            total_len += len(dim_text)

        return "\n".join(lines)[:max_chars]
