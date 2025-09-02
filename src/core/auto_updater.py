#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль автообновления приложения через GitHub
"""

import requests
import json
import os
import sys
import subprocess
import tempfile
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import QThread, pyqtSignal, Qt

class UpdateChecker:
    """Проверка обновлений через GitHub API"""
    
    def __init__(self, repo_owner="baltabekpro", repo_name="wb_auto"):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_base = "https://api.github.com"
        self.current_version = self.get_current_version()
        
    def get_current_version(self):
        """Получает текущую версию приложения"""
        try:
            version_file = Path(__file__).parent.parent.parent / "version.txt"
            if version_file.exists():
                return version_file.read_text().strip()
            return "1.0.0"
        except Exception:
            return "1.0.0"
    
    def check_for_updates(self):
        """Проверяет наличие новых версий"""
        try:
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            latest_version = release_data["tag_name"].lstrip("v")
            
            return {
                "has_update": self.compare_versions(self.current_version, latest_version),
                "latest_version": latest_version,
                "current_version": self.current_version,
                "download_url": self.get_download_url(release_data),
                "release_notes": release_data.get("body", ""),
                "published_at": release_data.get("published_at", "")
            }
            
        except Exception as e:
            print(f"Ошибка проверки обновлений: {e}")
            return None
    
    def compare_versions(self, current, latest):
        """Сравнивает версии (простая реализация)"""
        try:
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            
            # Дополняем до одинаковой длины
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            
            return latest_parts > current_parts
        except Exception:
            return False
    
    def get_download_url(self, release_data):
        """Получает URL для скачивания исполняемого файла"""
        assets = release_data.get("assets", [])
        
        # Ищем .exe файл
        for asset in assets:
            if asset["name"].endswith(".exe"):
                return asset["browser_download_url"]
        
        # Если нет .exe, возвращаем zipball
        return release_data.get("zipball_url")


class UpdateDownloader(QThread):
    """Поток для скачивания обновления"""
    
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, path_or_error
    
    def __init__(self, download_url, filename):
        super().__init__()
        self.download_url = download_url
        self.filename = filename
        self.temp_dir = tempfile.mkdtemp()
        
    def run(self):
        try:
            self.status.emit("Скачивание обновления...")
            
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            file_path = os.path.join(self.temp_dir, self.filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress.emit(progress)
            
            self.status.emit("Обновление скачано успешно!")
            self.finished.emit(True, file_path)
            
        except Exception as e:
            self.status.emit(f"Ошибка скачивания: {e}")
            self.finished.emit(False, str(e))


class AutoUpdater:
    """Главный класс автообновления"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.checker = UpdateChecker()
        self.downloader = None
        
    def check_and_notify(self, silent=False):
        """Проверяет обновления и уведомляет пользователя"""
        update_info = self.checker.check_for_updates()
        
        if not update_info:
            if not silent:
                QMessageBox.warning(
                    self.parent,
                    "Проверка обновлений",
                    "Не удалось проверить обновления.\nПроверьте подключение к интернету."
                )
            return False
        
        if not update_info["has_update"]:
            if not silent:
                QMessageBox.information(
                    self.parent,
                    "Обновления",
                    f"У вас установлена последняя версия {update_info['current_version']}"
                )
            return False
        
        # Есть обновление
        self.show_update_dialog(update_info)
        return True
    
    def show_update_dialog(self, update_info):
        """Показывает диалог с информацией об обновлении"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Доступно обновление")
        
        text = f"""
Доступна новая версия WB Auto!

Текущая версия: {update_info['current_version']}
Новая версия: {update_info['latest_version']}

Обновления:
{update_info['release_notes'][:300]}...

Обновить сейчас?
        """.strip()
        
        msg.setText(text)
        msg.addButton("Обновить", QMessageBox.AcceptRole)
        msg.addButton("Позже", QMessageBox.RejectRole)
        msg.addButton("Пропустить версию", QMessageBox.DestructiveRole)
        
        result = msg.exec_()
        
        if result == 0:  # Обновить
            self.start_update(update_info)
        elif result == 2:  # Пропустить версию
            self.skip_version(update_info['latest_version'])
    
    def start_update(self, update_info):
        """Запускает процесс обновления"""
        if not update_info["download_url"]:
            QMessageBox.warning(
                self.parent,
                "Ошибка обновления",
                "Не найден файл для скачивания."
            )
            return
        
        # Определяем имя файла
        filename = "WB_Auto_new.exe" if update_info["download_url"].endswith(".exe") else "update.zip"
        
        # Создаем прогресс диалог
        progress_dialog = QProgressDialog(
            "Скачивание обновления...",
            "Отмена",
            0, 100,
            self.parent
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setWindowTitle("Обновление WB Auto")
        
        # Создаем загрузчик
        self.downloader = UpdateDownloader(update_info["download_url"], filename)
        
        # Подключаем сигналы
        self.downloader.progress.connect(progress_dialog.setValue)
        self.downloader.status.connect(progress_dialog.setLabelText)
        self.downloader.finished.connect(
            lambda success, path: self.on_download_finished(success, path, progress_dialog)
        )
        progress_dialog.canceled.connect(self.downloader.terminate)
        
        # Запускаем загрузку
        progress_dialog.show()
        self.downloader.start()
    
    def on_download_finished(self, success, path_or_error, progress_dialog):
        """Обработка завершения загрузки"""
        progress_dialog.close()
        
        if not success:
            QMessageBox.critical(
                self.parent,
                "Ошибка обновления",
                f"Не удалось скачать обновление:\n{path_or_error}"
            )
            return
        
        # Успешно скачано
        if path_or_error.endswith(".exe"):
            self.install_exe_update(path_or_error)
        else:
            self.install_zip_update(path_or_error)
    
    def install_exe_update(self, exe_path):
        """Устанавливает обновление из exe файла"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Установка обновления")
        msg.setText(
            "Обновление скачано успешно!\n\n"
            "Для завершения установки приложение будет перезапущено.\n"
            "Продолжить?"
        )
        msg.addButton("Да", QMessageBox.AcceptRole)
        msg.addButton("Нет", QMessageBox.RejectRole)
        
        if msg.exec_() == 0:
            self.apply_exe_update(exe_path)
    
    def apply_exe_update(self, new_exe_path):
        """Применяет обновление exe файла"""
        try:
            current_exe = sys.executable
            backup_exe = current_exe + ".backup"
            
            # Создаем батник для обновления
            batch_content = f"""
@echo off
echo Обновление WB Auto...
timeout /t 2 /nobreak > nul

rem Делаем резервную копию
move "{current_exe}" "{backup_exe}"

rem Копируем новую версию
move "{new_exe_path}" "{current_exe}"

rem Запускаем новую версию
start "" "{current_exe}"

rem Удаляем резервную копию через 10 секунд
timeout /t 10 /nobreak > nul
del "{backup_exe}"

rem Удаляем батник
del "%~f0"
            """.strip()
            
            batch_file = os.path.join(tempfile.gettempdir(), "wb_auto_update.bat")
            with open(batch_file, 'w', encoding='cp1251') as f:
                f.write(batch_content)
            
            # Запускаем батник и закрываем приложение
            subprocess.Popen([batch_file], shell=True)
            
            if self.parent:
                self.parent.close()
            else:
                sys.exit(0)
                
        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Ошибка установки",
                f"Не удалось установить обновление:\n{e}"
            )
    
    def install_zip_update(self, zip_path):
        """Устанавливает обновление из zip архива"""
        QMessageBox.information(
            self.parent,
            "Обновление",
            f"Обновление скачано в:\n{zip_path}\n\n"
            "Распакуйте архив и замените файлы приложения."
        )
    
    def skip_version(self, version):
        """Помечает версию как пропущенную"""
        try:
            skip_file = Path(__file__).parent.parent.parent / "skipped_versions.txt"
            with open(skip_file, 'a', encoding='utf-8') as f:
                f.write(f"{version}\n")
        except Exception:
            pass
    
    def is_version_skipped(self, version):
        """Проверяет, была ли версия пропущена"""
        try:
            skip_file = Path(__file__).parent.parent.parent / "skipped_versions.txt"
            if skip_file.exists():
                skipped = skip_file.read_text(encoding='utf-8').strip().split('\n')
                return version in skipped
        except Exception:
            pass
        return False


def create_version_file(version="1.0.1"):
    """Создает файл версии"""
    version_file = Path(__file__).parent.parent.parent / "version.txt"
    version_file.write_text(version, encoding='utf-8')
    print(f"Создан файл версии: {version}")


if __name__ == "__main__":
    # Создаем файл версии
    create_version_file()
    
    # Тестируем проверку обновлений
    checker = UpdateChecker()
    print(f"Текущая версия: {checker.current_version}")
    
    update_info = checker.check_for_updates()
    if update_info:
        print(f"Доступна версия: {update_info['latest_version']}")
        print(f"Есть обновление: {update_info['has_update']}")
    else:
        print("Не удалось проверить обновления")
