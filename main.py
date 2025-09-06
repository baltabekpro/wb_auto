#!/usr/bin/env python3
"""
WB Auto - Быстрый запуск без splash screen
"""

import sys
import os
from PyQt5 import QtWidgets, QtCore, QtGui

# Добавляем путь к src для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    """Основная функция запуска приложения - быстрый старт"""
    # Создаем приложение
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('WB Auto')
    app.setOrganizationName('WBAuto')
    
    # Устанавливаем глобальную тёмную тему
    app.setStyle('Fusion')
    
    # Глобальная палитра для тёмной темы
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(43, 43, 43))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(64, 64, 64))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(64, 64, 64))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(74, 144, 226))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(74, 144, 226))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(palette)
    
    # Глобальные стили для всех диалогов
    app.setStyleSheet("""
        /* Стили для всех диалогов */
        QDialog {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        QDialog * {
            color: #f0f0f0;
        }
        
        /* Стили для сообщений об ошибках */
        QMessageBox {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        QMessageBox * {
            color: #f0f0f0 !important;
            background-color: transparent !important;
        }
        QMessageBox QLabel {
            color: #f0f0f0 !important;
            background-color: transparent !important;
        }
        QMessageBox QPushButton {
            background: #4a90e2;
            color: white !important;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background: #5aa0f2;
        }
        
        /* Стили для мастера настройки */
        QWizard {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        QWizard * {
            color: #f0f0f0 !important;
        }
        QWizard QLabel {
            color: #f0f0f0 !important;
            background-color: transparent !important;
        }
        QWizardPage {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
    """)
    
    try:
        # Импортируем главное окно напрямую - без splash screen для быстрого запуска
        try:
            from src.app import MainWindow
        except ImportError:
            # Для exe файла
            from app import MainWindow
        
        # Создаем и показываем главное окно сразу
        main_window = MainWindow()
        main_window.show()
        main_window.raise_()
        main_window.activateWindow()
        
        # Запускаем приложение
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        
        # Показываем ошибку пользователю
        try:
            QtWidgets.QMessageBox.critical(
                None,
                "Ошибка запуска",
                f"Не удалось запустить приложение:\n\n{str(e)}\n\nПроверьте целостность файлов программы."
            )
        except:
            print("Не удалось показать диалог ошибки")
        
        sys.exit(1)

if __name__ == '__main__':
    main()
