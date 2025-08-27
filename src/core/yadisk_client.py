import io
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import yadisk
from tenacity import retry, stop_after_attempt, wait_exponential

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
    # Publish and then fetch public resources to get direct link
    y.publish(path)
    time.sleep(0.3)
    pr = y.get_public_resources(public_key=y.get_meta(path).public_url)
    # fallback: use public_url + "&download=1" if direct_url unavailable
    href = None
    for item in pr._embedded.items:
        if hasattr(item, 'file') and item.file:
            href = item.file
            break
    if not href:
        href = y.get_meta(path).public_url + "&download=1"
    return href


def ensure_folder(y: yadisk.YaDisk, folder: str):
    if not y.exists(folder):
        y.mkdir(folder)


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
