#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест загрузки профилей
"""

import os
import sys

# Добавляем путь к модулям
sys.path.insert(0, os.path.abspath('src'))

def test_profiles_loading():
    """Тестирует загрузку профилей"""
    
    print("🧪 Тестирование загрузки профилей")
    print("=" * 40)
    
    try:
        from core.profiles import list_profiles, get_resource_path
        
        # Проверяем автоматическое определение пути
        print(f"📂 Путь к ресурсам: {get_resource_path('profiles')}")
        
        # Загружаем профили
        profiles = list_profiles()
        
        print(f"\n📋 Результат:")
        print(f"   Найдено профилей: {len(profiles)}")
        
        if profiles:
            print("   Список профилей:")
            for name, path in profiles.items():
                print(f"     • {name}")
                print(f"       Путь: {path}")
        else:
            print("   ❌ Профили не найдены!")
            
            # Проверяем что есть в папке profiles
            profiles_dir = "profiles"
            if os.path.exists(profiles_dir):
                files = os.listdir(profiles_dir)
                print(f"   📁 В папке profiles/ найдено файлов: {len(files)}")
                for f in files:
                    print(f"     - {f}")
            else:
                print(f"   ❌ Папка {profiles_dir} не существует!")
        
        return len(profiles) > 0
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_profiles_loading()
    
    if success:
        print("\n✅ ТЕСТ ПРОШЕЛ!")
        print("Профили загружаются корректно.")
    else:
        print("\n❌ ТЕСТ НЕ ПРОШЕЛ!")
        print("Проблемы с загрузкой профилей.")
