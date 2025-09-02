#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест исправленной версии загрузки с обработкой ошибок
"""

import os
import sys
import tempfile
from PIL import Image
import keyring
from src.core.yadisk_client import upload_sku_photos

def create_test_photo(filename, size=(300, 300), color=(255, 0, 0)):
    """Создает тестовое изображение"""
    img = Image.new('RGB', size, color)
    img.save(filename, 'JPEG')
    print(f"✅ Создано тестовое фото: {filename}")

def test_fixed_upload():
    """Тестирует исправленную загрузку"""
    
    # Получаем токен из файла final_setup.py
    final_setup_path = "final_setup.py"
    token = None
    
    if os.path.exists(final_setup_path):
        with open(final_setup_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'YANDEX_TOKEN' in content:
                start = content.find('YANDEX_TOKEN = "') + len('YANDEX_TOKEN = "')
                end = content.find('"', start)
                token = content[start:end]
    
    if not token:
        print("❌ Токен не найден!")
        return False
    
    print(f"🔑 Используем токен: {token[:20]}...")
    
    # Создаем временную папку с тестовыми фото
    temp_dir = tempfile.mkdtemp(prefix="wb_test_")
    print(f"📁 Временная папка: {temp_dir}")
    
    try:
        # Создаем тестовые фото
        test_files = [
            os.path.join(temp_dir, "тест-исправлений.1.jpg"),
            os.path.join(temp_dir, "тест-исправлений.2.jpg")
        ]
        
        for i, filepath in enumerate(test_files):
            color = (255, 0, 0) if i == 0 else (0, 255, 0)  # Красное и зеленое фото
            create_test_photo(filepath, color=color)
        
        print("\n🚀 Тестируем исправленную загрузку...")
        
        # Тестируем загрузку
        results = upload_sku_photos(
            keyring=keyring,
            token=token,
            root_path="/WB/Kruzhki",
            sku="тест-исправлений",
            files=test_files,
            overwrite_mode="Всегда перезаписывать"
        )
        
        print(f"\n✅ Загрузка завершена! Получено {len(results)} ссылок:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.name}")
            print(f"     Публичная: {result.public_url}")
            print(f"     Прямая: {result.direct_url[:60]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Очищаем временные файлы
        try:
            for filepath in test_files:
                if os.path.exists(filepath):
                    os.remove(filepath)
            os.rmdir(temp_dir)
            print(f"🧹 Временные файлы очищены")
        except Exception:
            pass

if __name__ == "__main__":
    print("🔧 Тестирование исправленной версии загрузки\n")
    
    success = test_fixed_upload()
    
    if success:
        print("\n🎉 ТЕСТ ПРОШЕЛ УСПЕШНО!")
        print("Исправления работают корректно.")
    else:
        print("\n❌ ТЕСТ НЕ ПРОШЕЛ")
        print("Требуются дополнительные исправления.")
