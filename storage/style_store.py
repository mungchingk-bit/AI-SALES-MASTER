import json
import os

import config
from models.style_profile import StyleProfile


def _merge_traits(traits_a: dict, traits_b: dict) -> dict:
    """合并两个风格特征字典。列表字段合并去重，文本字段取更长者。"""
    merged = {}
    list_keys = {"key_phrases", "avoid_patterns", "sample_dialogues"}
    for key in set(list(traits_a.keys()) + list(traits_b.keys())):
        va = traits_a.get(key)
        vb = traits_b.get(key)
        if key in list_keys:
            combined = []
            seen = set()
            for item in (va or []) + (vb or []):
                if item not in seen:
                    combined.append(item)
                    seen.add(item)
            merged[key] = combined
        elif isinstance(va, str) and isinstance(vb, str):
            merged[key] = va if len(va) >= len(vb) else vb
        else:
            merged[key] = va or vb
    return merged


def _merge_confidence(ca: dict, cb: dict) -> dict:
    """合并置信度，取较高值。"""
    merged = {}
    for key in set(list(ca.keys()) + list(cb.keys())):
        merged[key] = max(ca.get(key, 0), cb.get(key, 0))
    return merged


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
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    profiles.append(StyleProfile.from_dict(data))
                except Exception:
                    continue
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

    def merge(self, profile_a: StyleProfile, profile_b: StyleProfile, merged_name: str | None = None) -> StyleProfile:
        """合并两个同销售的风格档案（话术+面聊）。"""
        merged = StyleProfile(
            name=merged_name or profile_a.name,
            description=profile_a.description if len(profile_a.description or "") >= len(profile_b.description or "") else profile_b.description,
            source_file=f"{profile_a.source_file} + {profile_b.source_file}",
            extracted_traits=_merge_traits(profile_a.extracted_traits, profile_b.extracted_traits),
            confidence_scores=_merge_confidence(profile_a.confidence_scores, profile_b.confidence_scores),
            sample_dialogues=(profile_a.sample_dialogues or []) + (profile_b.sample_dialogues or []),
        )
        self.delete(profile_a.id)
        self.delete(profile_b.id)
        self.save(merged)
        return merged
