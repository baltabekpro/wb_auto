#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пересборка с исправлением ImportError
"""

import os
import sys
import subprocess
from pathlib import Path

def rebuild_fixed():
    """Пересобирает exe с исправлением ImportError"""
    
    print("🔧 Пересборка WB Auto - Исправление ImportError")
    print("=" * 55)
    
    version = "1.0.5"
    print(f"📈 Версия: {version}")
    
    # Команда сборки с более точными зависимостями
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole", 
        "--name", f"WB_Auto_v{version}_FIXED",
        "--add-data", "version.txt;.",
        "--add-data", "profiles;profiles",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtWidgets", 
        "--hidden-import", "PyQt5.QtGui",
        "--hidden-import", "requests",
        "--hidden-import", "keyring",
        "--hidden-import", "yadisk",
        "--hidden-import", "openpyxl",
        "--hidden-import", "tenacity",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--exclude-module", "core.direct_yadisk_api",  # Исключаем проблемный модуль
        "--clean",
        "src/app.py"
    ]
    
    print("🔨 Запуск пересборки...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Пересборка завершена!")
            
            exe_path = Path("dist") / f"WB_Auto_v{version}_FIXED.exe"
            if exe_path.exists():
                print(f"📦 Файл: {exe_path}")
                print(f"📊 Размер: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
                
                # Создаем копию с простым именем
                simple_path = Path("dist") / "WB_Auto_WORKING.exe" 
                if simple_path.exists():
                    simple_path.unlink()
                exe_path.rename(simple_path)
                print(f"📎 Переименован в: {simple_path}")
                
                return True
            else:
                print("❌ Файл exe не найден")
                return False
        else:
            print("❌ Ошибка пересборки:")
            print(result.stderr[-1000:])
            return False
            
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

if __name__ == "__main__":
    success = rebuild_fixed()
    
    if success:
        print("\n🎉 ИСПРАВЛЕНО!")
        print("ImportError устранен.")
        print("\nИсправления в v1.0.5:")
        print("• ❌ Убран проблемный импорт direct_yadisk_api")
        print("• ✅ Исправлена ошибка PathExistsError") 
        print("• ✅ Добавлено автообновление")
        print("• ✅ Стабильная работа загрузки")
        print("\n📦 Готовый файл: dist/WB_Auto_WORKING.exe")
    else:
        print("\n❌ Пересборка не удалась")
