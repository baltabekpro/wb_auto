#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальная сборка с исправлением загрузки профилей
"""

import os
import sys
import subprocess
from pathlib import Path

def final_build_with_profiles():
    """Собирает exe с правильной упаковкой профилей"""
    
    print("🔧 Финальная сборка с исправлением профилей")
    print("=" * 50)
    
    version = "1.0.6"
    print(f"📈 Версия: {version}")
    
    # Команда сборки с правильной упаковкой профилей
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole", 
        "--name", f"WB_Auto_v{version}_FINAL",
        # Правильная упаковка данных
        "--add-data", "version.txt;.",
        "--add-data", "profiles/*.json;profiles",  # Упаковываем JSON файлы профилей
        # Скрытые импорты
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
        # Исключаем проблемные модули
        "--exclude-module", "core.direct_yadisk_api",
        # Дополнительные опции
        "--clean",
        "--noconfirm",
        "src/app.py"
    ]
    
    print("🔨 Запуск финальной сборки...")
    print("📂 Упаковываем профили...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Финальная сборка завершена!")
            
            exe_path = Path("dist") / f"WB_Auto_v{version}_FINAL.exe"
            if exe_path.exists():
                print(f"📦 Файл: {exe_path}")
                print(f"📊 Размер: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
                
                # Создаем финальную копию
                final_path = Path("dist") / "WB_Auto_FINAL.exe" 
                if final_path.exists():
                    final_path.unlink()
                exe_path.rename(final_path)
                print(f"📎 Финальная версия: {final_path}")
                
                return True
            else:
                print("❌ Файл exe не найден")
                return False
        else:
            print("❌ Ошибка финальной сборки:")
            print(result.stderr[-1500:])
            print("\n--- STDOUT ---")
            print(result.stdout[-1000:])
            return False
            
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

if __name__ == "__main__":
    success = final_build_with_profiles()
    
    if success:
        print("\n🎉 ФИНАЛЬНАЯ ВЕРСИЯ ГОТОВА!")
        print("\nВсе исправления в v1.0.6:")
        print("• ✅ Исправлена ошибка PathExistsError")
        print("• ✅ Убран проблемный импорт direct_yadisk_api") 
        print("• ✅ ИСПРАВЛЕНА загрузка профилей в exe")
        print("• ✅ Добавлено автообновление")
        print("• ✅ Подробная диагностика ошибок")
        print("\n📦 Готовый файл: dist/WB_Auto_FINAL.exe")
        print("🧪 Протестируйте загрузку профилей в exe!")
    else:
        print("\n❌ Финальная сборка не удалась")
