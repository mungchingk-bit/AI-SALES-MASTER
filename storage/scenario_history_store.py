"""场景历史记录 — 跟踪每个用户最近训练过的场景元素，用于去重和多样化。"""
import json
import os

import config

_MAX_WEDDING_TYPES = 8
_MAX_DIMENSIONS = 10
_MAX_PERSONALITIES = 5
_MAX_NAMES = 15


class ScenarioHistoryStore:
    def __init__(self):
        self._dir = config.SCENARIO_HISTORY_DIR

    def _path(self, user: str) -> str:
        safe = user.replace("/", "_").replace("\\", "_") or "_anon"
        return os.path.join(self._dir, f"{safe}.json")

    def load(self, user: str) -> dict:
        p = self._path(user)
        if not os.path.exists(p):
            return self._empty(user)
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return self._empty(user)

    def save(self, user: str, data: dict):
        os.makedirs(self._dir, exist_ok=True)
        data["user"] = user
        p = self._path(user)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_session(self, user: str, elements: dict):
        data = self.load(user)
        data["session_count"] = data.get("session_count", 0) + 1

        if "wedding_type" in elements and elements["wedding_type"]:
            lst = data.get("used_wedding_types", [])
            lst.append(elements["wedding_type"])
            data["used_wedding_types"] = lst[-_MAX_WEDDING_TYPES:]

        if "objection_dimensions" in elements and elements["objection_dimensions"]:
            lst = data.get("used_objection_dimensions", [])
            lst.extend(elements["objection_dimensions"])
            data["used_objection_dimensions"] = lst[-_MAX_DIMENSIONS:]

        if "personality" in elements and elements["personality"]:
            lst = data.get("used_personalities", [])
            lst.append(elements["personality"])
            data["used_personalities"] = lst[-_MAX_PERSONALITIES:]

        if "customer_name" in elements and elements["customer_name"]:
            lst = data.get("used_customer_names", [])
            lst.append(elements["customer_name"])
            data["used_customer_names"] = lst[-_MAX_NAMES:]

        from datetime import datetime
        data["last_updated"] = datetime.now().isoformat()
        self.save(user, data)

    def get_recent(self, user: str) -> dict:
        data = self.load(user)
        return {
            "used_wedding_types": data.get("used_wedding_types", []),
            "used_objection_dimensions": data.get("used_objection_dimensions", []),
            "used_personalities": data.get("used_personalities", []),
            "used_customer_names": data.get("used_customer_names", []),
        }

    def _empty(self, user: str) -> dict:
        return {
            "user": user,
            "session_count": 0,
            "used_wedding_types": [],
            "used_objection_dimensions": [],
            "used_personalities": [],
            "used_customer_names": [],
        }
