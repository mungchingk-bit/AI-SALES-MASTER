import json
import os

import config
from models.style_profile import StyleProfile


class StyleStore:
    def __init__(self):
        self.styles_dir = config.STYLES_DIR

    def save(self, profile: StyleProfile) -> str:
        path = os.path.join(self.styles_dir, f"{profile.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        return profile.id

    def load(self, profile_id: str) -> StyleProfile | None:
        path = os.path.join(self.styles_dir, f"{profile_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StyleProfile.from_dict(data)

    def list_all(self) -> list[StyleProfile]:
        profiles = []
        if not os.path.exists(self.styles_dir):
            return profiles
        for filename in os.listdir(self.styles_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.styles_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(StyleProfile.from_dict(data))
        return profiles

    def delete(self, profile_id: str) -> bool:
        path = os.path.join(self.styles_dir, f"{profile_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def update(self, profile_id: str, updates: dict) -> StyleProfile | None:
        profile = self.load(profile_id)
        if profile is None:
            return None
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        from datetime import datetime
        profile.updated_at = datetime.now().isoformat()
        self.save(profile)
        return profile
