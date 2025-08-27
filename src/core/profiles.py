import json
import os
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Profile:
    data: Dict[str, Any]

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    @property
    def name(self) -> str:
        return self.data.get("name", "Профиль")


def load_profile(path: str) -> Profile:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Profile(data=data)


def list_profiles(folder: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not os.path.isdir(folder):
        return result
    for fn in os.listdir(folder):
        if not fn.lower().endswith('.json'):
            continue
        full = os.path.join(folder, fn)
        try:
            prof = load_profile(full)
            result[prof.name] = full
        except Exception:
            continue
    return result
