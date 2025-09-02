import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict

def get_resource_path(relative_path):
    """Получает путь к ресурсу, работает как в разработке, так и в exe"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # В режиме разработки используем обычный путь
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

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


def list_profiles(folder: str = None) -> Dict[str, str]:
    """Загружает список профилей. Автоматически определяет папку профилей."""
    result: Dict[str, str] = {}
    
    if folder is None:
        # Автоматически определяем папку профилей
        folder = get_resource_path("profiles")
    
    print(f"🔍 Ищем профили в: {folder}")
    
    if not os.path.isdir(folder):
        print(f"❌ Папка профилей не найдена: {folder}")
        return result
    
    files = os.listdir(folder)
    print(f"📁 Найдено файлов в папке: {len(files)}")
    
    for fn in files:
        if not fn.lower().endswith('.json'):
            continue
        full = os.path.join(folder, fn)
        print(f"📄 Обрабатываем файл: {fn}")
        try:
            prof = load_profile(full)
            result[prof.name] = full
            print(f"✅ Загружен профиль: {prof.name}")
        except Exception as e:
            print(f"❌ Ошибка загрузки {fn}: {e}")
            continue
    
    print(f"📋 Итого загружено профилей: {len(result)}")
    return result
