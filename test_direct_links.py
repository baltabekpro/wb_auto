#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Исправленная функция для получения прямых ссылок на скачивание
"""

import requests
import time
from typing import Optional

def get_direct_download_link(token: str, file_path: str) -> Optional[str]:
    """
    Получает прямую ссылку для скачивания файла из Яндекс.Диска
    
    Args:
        token: OAuth токен
        file_path: Путь к файлу в Яндекс.Диске
        
    Returns:
        Прямая ссылка для скачивания или None
    """
    headers = {
        'Authorization': f'OAuth {token}',
        'Accept': 'application/json'
    }
    
    try:
        # 1. Сначала публикуем файл (если еще не опубликован)
        publish_url = "https://cloud-api.yandex.net/v1/disk/resources/publish"
        params = {'path': file_path}
        
        response = requests.put(publish_url, headers=headers, params=params, timeout=30)
        # Игнорируем ошибку если файл уже опубликован
        
        time.sleep(0.5)  # Даем время на обработку
        
        # 2. Получаем метаданные файла с публичной ссылкой
        meta_url = "https://cloud-api.yandex.net/v1/disk/resources"
        params = {'path': file_path}
        
        response = requests.get(meta_url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            print(f"❌ Ошибка получения метаданных: {response.status_code}")
            return None
            
        meta_data = response.json()
        public_url = meta_data.get('public_url')
        
        if not public_url:
            print(f"❌ Публичная ссылка не найдена для {file_path}")
            return None
            
        print(f"📎 Публичная ссылка: {public_url}")
        
        # 3. Получаем прямую ссылку для скачивания через публичное API
        download_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
        params = {'public_key': public_url}
        
        response = requests.get(download_url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"❌ Ошибка получения ссылки для скачивания: {response.status_code}")
            print(f"Ответ: {response.text}")
            # Возвращаем публичную ссылку с параметром download как fallback
            return public_url + "&download=1"
            
        download_data = response.json()
        direct_link = download_data.get('href')
        
        if direct_link:
            print(f"✅ Прямая ссылка получена: {direct_link[:100]}...")
            return direct_link
        else:
            print(f"❌ Прямая ссылка не найдена в ответе")
            # Возвращаем публичную ссылку с параметром download как fallback
            return public_url + "&download=1"
            
    except Exception as e:
        print(f"❌ Ошибка при получении прямой ссылки: {e}")
        return None

if __name__ == "__main__":
    # Тест функции
    TOKEN = "y0__xDfuNb6BRjs_jkg083yoxQw1_KTrwhbabBmRXLRvOpGmx6pPvI9gbp0RA"
    
    # Создаем тестовый файл
    test_file = "test_direct_link.txt"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("Тест прямой ссылки для скачивания")
    
    # Загружаем файл в Яндекс.Диск
    headers = {'Authorization': f'OAuth {TOKEN}'}
    
    # Получаем ссылку для загрузки
    upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    params = {'path': f'/WB_AUTO_TEST/{test_file}', 'overwrite': 'true'}
    
    response = requests.get(upload_url, headers=headers, params=params, timeout=30)
    if response.status_code == 200:
        upload_data = response.json()
        upload_href = upload_data['href']
        
        # Загружаем файл
        with open(test_file, 'rb') as f:
            upload_response = requests.put(upload_href, data=f, timeout=30)
            
        if upload_response.status_code in [201, 202]:
            print(f"✅ Файл загружен: {test_file}")
            
            # Тестируем получение прямой ссылки
            direct_link = get_direct_download_link(TOKEN, f'/WB_AUTO_TEST/{test_file}')
            
            if direct_link:
                print(f"🎉 Успех! Прямая ссылка: {direct_link}")
                
                # Проверяем, что ссылка работает
                test_response = requests.get(direct_link, timeout=10)
                if test_response.status_code == 200:
                    print(f"✅ Ссылка работает! Скачано {len(test_response.content)} байт")
                else:
                    print(f"❌ Ссылка не работает: {test_response.status_code}")
            else:
                print("❌ Не удалось получить прямую ссылку")
        else:
            print(f"❌ Ошибка загрузки файла: {upload_response.status_code}")
    else:
        print(f"❌ Ошибка получения ссылки для загрузки: {response.status_code}")
    
    # Удаляем тестовый файл
    import os
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"🗑️ Удален тестовый файл: {test_file}")
