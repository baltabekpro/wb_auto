#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание минималистичной иконки для WB Auto
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Создает минималистичную иконку с буквами WB"""
    # Размеры иконки
    sizes = [16, 32, 48, 64, 128, 256]
    
    # Создаем папку для иконок
    icons_dir = "icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    images = []
    
    for size in sizes:
        # Создаем изображение с черным фоном
        img = Image.new('RGBA', (size, size), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        
        # Определяем размер шрифта в зависимости от размера иконки
        font_size = max(8, size // 4)
        
        try:
            # Пытаемся использовать системный шрифт
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except:
                # Используем дефолтный шрифт если не найден Arial
                font = ImageFont.load_default()
        
        # Текст для отображения
        text = "WB"
        
        # Получаем размеры текста
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Центрируем текст
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - bbox[1]
        
        # Рисуем белый текст на черном фоне
        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
        
        # Добавляем тонкую белую рамку для эстетики
        border_width = max(1, size // 64)
        if border_width > 0:
            draw.rectangle([0, 0, size-1, size-1], outline=(255, 255, 255, 100), width=border_width)
        
        images.append(img)
        
        # Сохраняем отдельные PNG файлы
        img.save(f"{icons_dir}/icon_{size}x{size}.png")
    
    # Создаем ICO файл с несколькими размерами
    images[0].save(f"{icons_dir}/app_icon.ico", format='ICO', sizes=[(s, s) for s in sizes])
    
    print(f"✅ Иконка создана: {icons_dir}/app_icon.ico")
    print(f"   Размеры: {', '.join([f'{s}x{s}' for s in sizes])}")
    
    return f"{icons_dir}/app_icon.ico"

if __name__ == "__main__":
    create_icon()
