#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика загрузки профилей
"""

import os
import sys

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.profiles import list_profiles, load_profile

def test_profiles():
    print("🔍 ДИАГНОСТИКА ЗАГРУЗКИ ПРОФИЛЕЙ")
    print("=" * 50)
    
    # Текущая директория
    current_dir = os.path.dirname(__file__)
    print(f"📂 Текущая директория: {current_dir}")
    
    # Путь к профилям как в коде
    profiles_path = os.path.join(current_dir, 'src', '..', 'profiles')
    print(f"📁 Путь к профилям (как в коде): {profiles_path}")
    
    # Абсолютный путь
    abs_profiles_path = os.path.abspath(profiles_path)
    print(f"📍 Абсолютный путь: {abs_profiles_path}")
    
    # Проверяем существование папки
    if os.path.exists(abs_profiles_path):
        print("✅ Папка профилей существует")
        
        # Список файлов в папке
        files = os.listdir(abs_profiles_path)
        print(f"📄 Файлы в папке: {files}")
        
        # Загружаем профили
        try:
            profile_files = list_profiles(abs_profiles_path)
            print(f"📋 Загружено профилей: {len(profile_files)}")
            
            for name, path in profile_files.items():
                print(f"  • {name}: {path}")
                
                # Пробуем загрузить профиль
                try:
                    profile = load_profile(path)
                    print(f"    ✅ Профиль загружен: {profile.get('name', 'Без названия')}")
                except Exception as e:
                    print(f"    ❌ Ошибка загрузки: {e}")
                    
        except Exception as e:
            print(f"❌ Ошибка при загрузке профилей: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Папка профилей НЕ существует")
        
        # Ищем папку профилей в других местах
        search_paths = [
            os.path.join(current_dir, 'profiles'),
            os.path.join(current_dir, 'src', 'profiles'),
            'profiles'
        ]
        
        print("\n🔍 Поиск папки profiles в других местах:")
        for path in search_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                print(f"  ✅ Найдена: {abs_path}")
                files = os.listdir(abs_path)
                print(f"    📄 Файлы: {files}")
            else:
                print(f"  ❌ Не найдена: {abs_path}")

if __name__ == "__main__":
    test_profiles()
