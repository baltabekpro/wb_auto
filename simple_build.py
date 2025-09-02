#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простая сборка исправленной версии
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def simple_build():
    """Простая сборка exe файла"""
    
    print("🔧 Простая сборка WB Auto")
    print("=" * 40)
    
    # Обновляем версию
    version_file = Path("version.txt")
    if version_file.exists():
        current_version = version_file.read_text().strip()
        version_parts = current_version.split('.')
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        new_version = '.'.join(version_parts)
    else:
        new_version = "1.1.0"
    
    version_file.write_text(new_version, encoding='utf-8')
    print(f"📈 Версия: {new_version}")
    
    # Команда сборки
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole", 
        "--name", f"WB_Auto_v{new_version}",
        "--add-data", "version.txt;.",
        "--add-data", "profiles;profiles",
        "--hidden-import", "PyQt5",
        "--hidden-import", "requests", 
        "--hidden-import", "keyring",
        "--hidden-import", "yadisk",
        "--hidden-import", "openpyxl",
        "--hidden-import", "tenacity",
        "--hidden-import", "Pillow",
        "src/app.py"
    ]
    
    print("🔨 Запуск сборки...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Сборка завершена!")
            
            exe_path = Path("dist") / f"WB_Auto_v{new_version}.exe"
            if exe_path.exists():
                print(f"📦 Файл: {exe_path}")
                print(f"📊 Размер: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
                return True
            else:
                print("❌ Файл exe не найден")
                return False
        else:
            print("❌ Ошибка сборки:")
            print(result.stderr[-1000:])  # Последние 1000 символов ошибки
            return False
            
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

if __name__ == "__main__":
    success = simple_build()
    
    if success:
        print("\n🎉 ГОТОВО!")
        print("Исправленная версия собрана.")
        print("\nИсправления:")
        print("• Исправлена ошибка PathExistsError")
        print("• Добавлено автообновление")
        print("• Улучшена обработка ошибок")
    else:
        print("\n❌ Сборка не удалась")
