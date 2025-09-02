import io
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import yadisk
from tenacity import retry, stop_after_attempt, wait_exponential

def get_direct_download_link(public_url: str) -> Optional[str]:
    """
    Получает прямую ссылку для скачивания файла из публичной ссылки Яндекс.Диска
    """
    try:
        # Извлекаем public_key из URL
        if '/d/' in public_url:
            public_key = public_url.split('/d/')[1].split('?')[0]
        elif '/i/' in public_url:
            public_key = public_url.split('/i/')[1].split('?')[0]
        else:
            return None
        
        # Делаем запрос к API для получения прямой ссылки
        api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
        params = {'public_key': public_url}
        
        response = requests.get(api_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('href')
        else:
            print(f"⚠️ Ошибка получения прямой ссылки: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Исключение при получении прямой ссылки: {e}")
        return None

TOKEN_SERVICE = "wb_auto_yadisk"

@dataclass
class UploadedFile:
    sku: str
    name: str
    public_url: str
    direct_url: str
    size: int


def get_saved_token(keyring):
    try:
        return keyring.get_password(TOKEN_SERVICE, os.getlogin())
    except Exception:
        return None


def save_token(keyring, token: str):
    try:
        keyring.set_password(TOKEN_SERVICE, os.getlogin(), token)
    except Exception:
        pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _publish_and_get_direct(y: yadisk.YaDisk, path: str) -> str:
    """
    Публикует файл и получает прямую ссылку на скачивание
    """
    try:
        # Пробуем опубликовать файл
        y.publish(path)
    except yadisk.exceptions.PathAlreadyExistsError:
        # Файл уже опубликован - это нормально
        pass
    except Exception as e:
        # Возможно файл уже опубликован, пробуем получить ссылку
        try:
            meta = y.get_meta(path)
            if meta.public_url:
                # Файл уже опубликован
                pass
            else:
                # Файл не опубликован и опубликовать не удалось
                raise e
        except Exception:
            # Если метаданные тоже не получаются, перебрасываем исходную ошибку
            raise e
    
    time.sleep(0.3)
    
    try:
        meta = y.get_meta(path)
        if not meta.public_url:
            raise RuntimeError(f"Не удалось получить публичную ссылку для {path}")
        
        print(f"📎 Публичная ссылка: {meta.public_url}")
        
        # Пытаемся получить прямую ссылку через новую функцию
        try:
            direct_url = get_direct_download_link(meta.public_url)
            if direct_url and direct_url.startswith('https://downloader.disk.yandex.ru'):
                print(f"🔗 Прямая ссылка получена: {direct_url[:60]}...")
                return direct_url
        except Exception as e:
            print(f"⚠️ Не удалось получить прямую ссылку: {e}")
        
        # Если прямая ссылка не получена, попробуем еще раз через API
        print("🔄 Пробуем получить прямую ссылку через альтернативный способ...")
        
        # Новый способ через публичное API
        try:
            public_info_url = "https://cloud-api.yandex.net/v1/disk/public/resources"
            response = requests.get(
                public_info_url,
                params={"public_key": meta.public_url},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'file' in data and data['file']:
                    download_url = data['file']
                    print(f"✅ Альтернативная прямая ссылка получена")
                    return download_url
        except Exception as e:
            print(f"⚠️ Альтернативный способ тоже не сработал: {e}")
        
        # Если ничего не помогло, используем старый способ
        pr = y.get_public_resources(public_key=meta.public_url)
        
        # Ищем прямую ссылку на файл
        href = None
        if hasattr(pr, '_embedded') and hasattr(pr._embedded, 'items'):
            for item in pr._embedded.items:
                if hasattr(item, 'file') and item.file:
                    href = item.file
                    break
        
        # Если прямой ссылки нет, используем публичную с параметром download
        if not href:
            href = meta.public_url + "&download=1"
            
        return href
        
    except Exception as e:
        # В крайнем случае возвращаем базовую публичную ссылку
        try:
            meta = y.get_meta(path)
            if meta.public_url:
                return meta.public_url + "&download=1"
        except Exception:
            pass
        raise RuntimeError(f"Не удалось получить ссылку для {path}: {str(e)}")


def ensure_folder(y: yadisk.YaDisk, folder: str):
    """
    Безопасное создание папки - не вызывает ошибку если папка уже существует
    """
    try:
        # Сначала проверяем существует ли папка
        if y.exists(folder):
            print(f"📁 Папка уже существует: {folder}")
            return
        
        # Если не существует, создаем
        y.mkdir(folder)
        print(f"✅ Папка создана: {folder}")
        
    except yadisk.exceptions.PathExistsError:
        # Папка уже существует - это нормально
        print(f"📁 Папка уже существует: {folder}")
        pass
    except yadisk.exceptions.ForbiddenError as e:
        print(f"🚫 Недостаточно прав для создания папки {folder}: {e}")
        # Проверяем, может папка уже существует
        try:
            if y.exists(folder):
                print(f"📁 Папка всё же существует: {folder}")
                return
        except Exception:
            pass
        raise e
    except Exception as e:
        print(f"❌ Ошибка создания папки {folder}: {e}")
        # Проверяем существует ли папка другим способом
        try:
            if y.exists(folder):
                print(f"📁 Папка существует (проверка после ошибки): {folder}")
                return
            else:
                # Папка не существует и создать не удалось - это проблема
                raise e
        except Exception as check_error:
            print(f"❌ Не удалось проверить существование папки {folder}: {check_error}")
            raise e
        except Exception:
            # Если и проверка не работает, пробуем ещё раз создать
            try:
                y.mkdir(folder)
            except yadisk.exceptions.PathExistsError:
                # Папка уже существует - хорошо
                pass


def file_signature(fp: str) -> int:
    return os.path.getsize(fp)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def upload_file(y: yadisk.YaDisk, local_path: str, remote_path: str, overwrite: bool = False):
    with open(local_path, 'rb') as f:
        y.upload(f, remote_path, overwrite=overwrite)


def upload_sku_photos(
    keyring,
    token: str,
    root: str,
    sku: str,
    files: List[str],
    overwrite_mode: str = 'never',  # 'never' | 'changed' | 'always'
) -> List[UploadedFile]:
    """
    Загружает фотографии товара в Яндекс.Диск с fallback к прямому API
    """
    # Сначала пробуем стандартный способ через библиотеку yadisk
    try:
        return _upload_sku_photos_standard(keyring, token, root, sku, files, overwrite_mode)
    except Exception as e:
        print(f"❌ Загрузка не удалась: {e}")
        print("� Проверьте токен и права доступа к Яндекс.Диску")
        raise e  # Перебрасываем ошибку
        
        return uploaded

def _upload_sku_photos_standard(
    keyring,
    token: str,
    root: str,
    sku: str,
    files: List[str],
    overwrite_mode: str = 'never',  # 'never' | 'changed' | 'always'
) -> List[UploadedFile]:
    if token:
        save_token(keyring, token)
    else:
        token = get_saved_token(keyring)
    if not token:
        raise RuntimeError("OAuth-токен Яндекс.Диска не задан")

    y = yadisk.YaDisk(token=token)
    if not y.check_token():
        raise RuntimeError("Недействительный токен Яндекс.Диска")

    sku_root = root.rstrip('/') + f"/{sku}"
    ensure_folder(y, root)
    ensure_folder(y, sku_root)

    uploaded: List[UploadedFile] = []

    # Idempotency: skip same name+size
    existing: Dict[str, int] = {}
    try:
        for item in y.listdir(sku_root):
            if not item.is_dir:
                existing[item.name] = item.size or 0
    except Exception:
        pass

    for lp in files:
        name = os.path.basename(lp)
        rp = f"{sku_root}/{name}"
        sig = file_signature(lp)
        # If identical exists, just ensure public link and reuse
        if name in existing and existing[name] == sig:
            try:
                direct = _publish_and_get_direct(y, rp)
                uploaded.append(UploadedFile(sku=sku, name=name, public_url=y.get_meta(rp).public_url, direct_url=direct, size=sig))
                continue
            except Exception:
                pass

        if overwrite_mode == 'never' and name in existing:
            # Do not overwrite, reuse existing even if size changed
            try:
                direct = _publish_and_get_direct(y, rp)
                uploaded.append(UploadedFile(sku=sku, name=name, public_url=y.get_meta(rp).public_url, direct_url=direct, size=existing[name]))
                continue
            except Exception:
                # fallback: skip
                continue

        if overwrite_mode == 'always':
            ow = True
        elif overwrite_mode == 'changed':
            ow = (name in existing and existing[name] != sig)
        else:
            ow = False

        upload_file(y, lp, rp, overwrite=ow)
        direct = _publish_and_get_direct(y, rp)
        uploaded.append(UploadedFile(sku=sku, name=name, public_url=y.get_meta(rp).public_url, direct_url=direct, size=sig))

    return uploaded
