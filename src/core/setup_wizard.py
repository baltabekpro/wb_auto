"""
Мастер первой настройки приложения
"""
from PyQt5 import QtCore, QtGui, QtWidgets


class SetupWizard(QtWidgets.QWizard):
    """Мастер первой настройки для новых пользователей"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Мастер настройки WB Autoload')
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.setMinimumSize(600, 500)
        
        # Устанавливаем названия кнопок на русском
        self.setButtonText(QtWidgets.QWizard.NextButton, 'Далее >')
        self.setButtonText(QtWidgets.QWizard.BackButton, '< Назад')
        self.setButtonText(QtWidgets.QWizard.FinishButton, 'Завершить')
        self.setButtonText(QtWidgets.QWizard.CancelButton, 'Отмена')
        
        # Добавляем страницы
        self.addPage(WelcomePage())
        self.addPage(YandexDiskPage())
        self.addPage(ProfilePage())
        self.addPage(FinalPage())
        
        # Принудительно применяем стили к заголовкам
        self.currentIdChanged.connect(self._apply_title_styles)
        self.currentIdChanged.connect(self._on_page_changed)
    
    def _on_page_changed(self):
        """Вызывается при смене страницы"""
        # Применяем стили к текущей странице
        current_page = self.currentPage()
        if current_page:
            current_page.setStyleSheet("""
                QWizardPage {
                    background: #2b2b2b;
                    color: #f0f0f0;
                }
                QWizardPage * {
                    color: #f0f0f0;
                }
                QLabel {
                    color: #f0f0f0 !important;
                    background: transparent;
                }
            """)
    
    def _apply_title_styles(self):
        """Принудительно применяет стили к заголовкам страниц"""
        # Ищем и стилизуем все лейблы в мастере
        for label in self.findChildren(QtWidgets.QLabel):
            # Применяем тёмную тему ко всем лейблам
            label.setStyleSheet("QLabel { color: #f0f0f0 !important; background: transparent !important; }")
            
            # Если это заголовок или подзаголовок страницы
            parent = label.parent()
            if parent and isinstance(parent, QtWidgets.QWizardPage):
                # Проверяем, является ли это заголовком страницы
                if (hasattr(parent, 'title') and label.text() == parent.title()) or \
                   'title' in label.objectName().lower():
                    label.setStyleSheet("""
                        QLabel {
                            color: #f0f0f0 !important;
                            background: #2b2b2b !important;
                            font-size: 16px;
                            font-weight: bold;
                            padding: 10px;
                        }
                    """)
                elif (hasattr(parent, 'subTitle') and label.text() == parent.subTitle()) or \
                     'subtitle' in label.objectName().lower():
                    label.setStyleSheet("""
                        QLabel {
                            color: #cccccc !important;
                            background: #2b2b2b !important;
                            font-size: 12px;
                            padding: 5px 10px;
                        }
                    """)
        
        # Дополнительно применяем глобальные стили
        current_styles = self.styleSheet()
        if "QWizard * { color: #f0f0f0; }" not in current_styles:
            self.setStyleSheet(current_styles + """
                QWizard * {
                    color: #f0f0f0 !important;
                }
                QWizard QLabel {
                    color: #f0f0f0 !important;
                    background: transparent !important;
                }
            """)
    
    def showEvent(self, event):
        """Переопределяем для применения стилей при показе"""
        super().showEvent(event)
        # Применяем стили с задержкой
        QtCore.QTimer.singleShot(100, self._apply_title_styles)
        QtCore.QTimer.singleShot(200, self._force_dark_theme)
    
    def _force_dark_theme(self):
        """Принудительно применяет тёмную тему ко всем элементам"""
        # Применяем тёмную тему ко всему мастеру
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#2b2b2b"))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#f0f0f0"))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#2b2b2b"))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#404040"))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#f0f0f0"))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#404040"))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#f0f0f0"))
        palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor("#f0f0f0"))
        palette.setColor(QtGui.QPalette.Link, QtGui.QColor("#4a90e2"))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#4a90e2"))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
        
        # Применяем палитру
        self.setPalette(palette)
        QtWidgets.QApplication.instance().setPalette(palette)
        
        # Применяем палитру ко всем дочерним элементам
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.setPalette(palette)
            
        # Принудительно стилизуем все лейблы
        for label in self.findChildren(QtWidgets.QLabel):
            label.setStyleSheet("QLabel { color: #f0f0f0 !important; background: transparent !important; }")
            
        # Стилизуем сообщения об ошибках
        QtWidgets.QApplication.instance().setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QMessageBox * {
                color: #f0f0f0 !important;
                background-color: #2b2b2b !important;
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
        """)
        
        self.setStyleSheet("""
            /* Глобальные стили для мастера */
            QWizard { 
                background-color: #2b2b2b; 
                color: #f0f0f0; 
            }
            QWizardPage { 
                background-color: #2b2b2b; 
                color: #f0f0f0; 
            }
            /* Все лейблы в мастере */
            QWizard QLabel, QWizardPage QLabel {
                color: #f0f0f0 !important;
                background-color: transparent !important;
            }
            /* Заголовки страниц */
            QWizard::title, QWizardPage::title {
                color: #f0f0f0 !important;
                background-color: #2b2b2b !important;
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
            }
            /* Подзаголовки страниц */
            QWizard::subtitle, QWizardPage::subtitle {
                color: #cccccc !important;
                background-color: #2b2b2b !important;
                font-size: 12px;
                padding: 5px 10px;
            }
            /* Поля ввода */
            QLineEdit { 
                background: #232323; 
                color: #eee; 
                border: 1px solid #4a4a4a; 
                padding: 8px; 
                border-radius: 4px; 
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #4a90e2;
            }
            /* Кнопки */
            QPushButton { 
                background: #4a90e2; 
                color: white; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px; 
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover { 
                background: #5aa0f2; 
            }
            QPushButton:pressed {
                background: #357acc;
            }
            /* Спин-боксы */
            QSpinBox {
                background: #232323; 
                color: #eee; 
                border: 1px solid #4a4a4a; 
                padding: 6px; 
                border-radius: 4px;
            }
            QSpinBox:focus {
                border: 2px solid #4a90e2;
            }
            /* Кнопки мастера */
            QWizard QPushButton {
                min-width: 100px;
                padding: 10px 20px;
                font-size: 12px;
            }
            /* Исправление для системных диалогов */
            QMessageBox {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QMessageBox QLabel {
                color: #f0f0f0 !important;
                background-color: transparent !important;
            }
            QMessageBox QPushButton {
                background: #4a90e2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
        """)


class WelcomePage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle('Добро пожаловать!')
        self.setSubTitle('Настройка программы для загрузки товаров на Wildberries')
        
        # Принудительно устанавливаем стили для заголовков
        self.setStyleSheet("""
            QWizardPage {
                background: #2b2b2b;
                color: #f0f0f0;
            }
            QLabel {
                color: #f0f0f0 !important;
                background: transparent;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Описание
        description = QtWidgets.QLabel(
            'Эта программа поможет вам автоматизировать загрузку карточек товаров на Wildberries.\n\n'
            'Основные возможности:\n'
            '- Автоматическое распознавание товаров по именам файлов\n'
            '- Загрузка изображений в Яндекс.Диск\n'
            '- Генерация Excel-файлов для массовой загрузки\n'
            '- Управление профилями с общими параметрами\n\n'
            'Давайте настроим программу для работы.'
        )
        description.setWordWrap(True)
        description.setAlignment(QtCore.Qt.AlignTop)
        description.setStyleSheet("""
            QLabel {
                color: #f0f0f0;
                background: transparent;
                font-size: 12px;
                line-height: 1.4;
                padding: 10px;
            }
        """)
        description.setToolTip(
            'Мастер настройки поможет вам быстро настроить все необходимые параметры для работы с программой'
        )
        
        layout.addWidget(description)
        layout.addStretch()
        self.setLayout(layout)


class YandexDiskPage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle('Настройка Яндекс.Диска')
        self.setSubTitle('Для загрузки изображений требуется авторизация в Яндекс.Диске')
        
        layout = QtWidgets.QVBoxLayout()
        
        # Инструкция
        instruction = QtWidgets.QLabel(
            'Для работы с Яндекс.Диском вам потребуется OAuth токен:\n\n'
            '1. Перейдите по ссылке: https://oauth.yandex.ru/\n'
            '2. Создайте новое приложение\n'
            '3. Выберите платформу "Веб-сервисы"\n'
            '4. В разрешениях укажите "Яндекс.Диск REST API"\n'
            '5. Получите токен и вставьте его ниже\n\n'
            'Токен будет сохранён безопасно в системе.'
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("""
            QLabel {
                color: #f0f0f0;
                background: transparent;
                font-size: 11px;
                padding: 5px;
            }
        """)
        instruction.setToolTip(
            'OAuth токен позволяет программе загружать файлы на ваш Яндекс.Диск без сохранения пароля'
        )
        
        # Поле для токена
        self.tokenEdit = QtWidgets.QLineEdit()
        self.tokenEdit.setPlaceholderText('Вставьте OAuth токен здесь...')
        self.tokenEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.tokenEdit.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0;
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
                font-family: monospace;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.tokenEdit.setToolTip(
            'Токен выглядит примерно так: y0_AgAAAABkB5H2AApU7...\n'
            'Его можно получить на oauth.yandex.ru после создания приложения'
        )
        
        # Кнопка показать/скрыть
        showBtn = QtWidgets.QPushButton('[ ] Показать')
        showBtn.setCheckable(True)
        showBtn.toggled.connect(self._toggle_token_visibility)
        showBtn.setToolTip('Показать или скрыть введённый токен')
        showBtn.setMaximumWidth(120)
        showBtn.setStyleSheet("""
            QPushButton {
                color: #f0f0f0;
                background: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
            }
            QPushButton:hover {
                background: #505050;
            }
            QPushButton:pressed {
                background: #303030;
            }
        """)
        
        # Корневая папка
        self.rootEdit = QtWidgets.QLineEdit('/WB/Kruzhki')
        self.rootEdit.setPlaceholderText('Корневая папка на Яндекс.Диске')
        self.rootEdit.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0;
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.rootEdit.setToolTip(
            'В этой папке будут создаваться подпапки для каждого товара\n'
            'Например: /WB/Kruzhki/mama_1/, /WB/Kruzhki/papa_1/ и т.д.'
        )
        
        tokenLayout = QtWidgets.QHBoxLayout()
        tokenLayout.addWidget(self.tokenEdit)
        tokenLayout.addWidget(showBtn)
        
        layout.addWidget(instruction)
        
        tokenLabel = QtWidgets.QLabel('OAuth токен:')
        tokenLabel.setStyleSheet("QLabel { color: #f0f0f0; font-weight: bold; }")
        tokenLabel.setToolTip('Токен для доступа к API Яндекс.Диска')
        layout.addWidget(tokenLabel)
        
        layout.addLayout(tokenLayout)
        
        rootLabel = QtWidgets.QLabel('Корневая папка:')
        rootLabel.setStyleSheet("QLabel { color: #f0f0f0; font-weight: bold; }")
        rootLabel.setToolTip('Базовая папка для хранения изображений товаров')
        layout.addWidget(rootLabel)
        
        layout.addWidget(self.rootEdit)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Регистрируем поля для валидации
        self.registerField('token*', self.tokenEdit)
        self.registerField('root', self.rootEdit)
    
    def _toggle_token_visibility(self, show):
        self.tokenEdit.setEchoMode(QtWidgets.QLineEdit.Normal if show else QtWidgets.QLineEdit.Password)
        button = self.sender()
        button.setText('[X] Скрыть' if show else '[ ] Показать')


class ProfilePage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle('Создание профиля товара')
        self.setSubTitle('Настройте параметры для вашей категории товаров')
        
        layout = QtWidgets.QFormLayout()
        
        # Название профиля
        self.profileNameEdit = QtWidgets.QLineEdit('Мой профиль')
        self.profileNameEdit.setToolTip(
            'Название профиля для удобного выбора\n'
            'Например: "Кружки для мам", "Футболки детские"'
        )
        
        self.brandEdit = QtWidgets.QLineEdit('Мой бренд')
        self.brandEdit.setToolTip(
            'Название вашего бренда или торговой марки\n'
            'Будет отображаться на карточке товара в WB'
        )
        
        self.categoryEdit = QtWidgets.QLineEdit('Кружки')
        self.categoryEdit.setToolTip(
            'Категория товаров, например: Кружки, Футболки, Сумки\n'
            'Используется для группировки и поиска на маркетплейсе'
        )
        
        self.vatEdit = QtWidgets.QLineEdit('20%')
        self.vatEdit.setToolTip(
            'Ставка НДС для ваших товаров\n'
            'Обычно 20% для большинства товаров в России'
        )
        
        self.materialEdit = QtWidgets.QLineEdit('Керамика')
        self.materialEdit.setToolTip(
            'Основной материал изготовления товара\n'
            'Например: Керамика, Хлопок, Полиэстер, Пластик'
        )
        
        self.weightEdit = QtWidgets.QSpinBox()
        self.weightEdit.setRange(100, 2000)
        self.weightEdit.setValue(350)
        self.weightEdit.setSuffix(' г')
        self.weightEdit.setToolTip(
            'Вес товара с упаковкой в граммах\n'
            'Влияет на стоимость доставки и логистики'
        )
        
        # Добавляем поле цены по умолчанию
        self.defaultPriceEdit = QtWidgets.QSpinBox()
        self.defaultPriceEdit.setRange(1, 999999)
        self.defaultPriceEdit.setValue(499)
        self.defaultPriceEdit.setSuffix(' руб.')
        self.defaultPriceEdit.setToolTip(
            'Цена товара по умолчанию\n'
            'Можно будет изменить для каждого SKU отдельно'
        )
        
        # Добавляем поле описания
        self.descriptionEdit = QtWidgets.QTextEdit()
        self.descriptionEdit.setPlaceholderText('Описание товара...')
        self.descriptionEdit.setMaximumHeight(80)  # Ограничиваем высоту
        self.descriptionEdit.setToolTip(
            'Описание товара для карточки на Wildberries\n'
            'Можно использовать переменные: {sku}, {volume}\n'
            'Например: "Керамическая кружка {sku}. Объем {volume} мл."'
        )
        
        # Добавляем стили для лучшей видимости
        for widget in [self.profileNameEdit, self.brandEdit, self.categoryEdit, self.vatEdit, self.materialEdit]:
            widget.setStyleSheet("""
                QLineEdit {
                    color: #f0f0f0;
                    background: #3a3a3a;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 5px;
                }
                QLineEdit:focus {
                    border-color: #0078d4;
                }
            """)
        
        # Стили для текстового поля описания
        self.descriptionEdit.setStyleSheet("""
            QTextEdit {
                color: #f0f0f0;
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
                font-family: system-ui;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)
        
        self.weightEdit.setStyleSheet("""
            QSpinBox {
                color: #f0f0f0;
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QSpinBox:focus {
                border-color: #0078d4;
            }
        """)
        
        self.defaultPriceEdit.setStyleSheet("""
            QSpinBox {
                color: #f0f0f0;
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QSpinBox:focus {
                border-color: #0078d4;
            }
        """)
        
        layout.addRow('Название профиля:', self.profileNameEdit)
        
        layout.addRow('Бренд:', self.brandEdit)
        layout.addRow('Категория:', self.categoryEdit)
        layout.addRow('НДС:', self.vatEdit)
        layout.addRow('Материал:', self.materialEdit)
        layout.addRow('Описание товара:', self.descriptionEdit)
        layout.addRow('Вес упаковки:', self.weightEdit)
        layout.addRow('Цена по умолчанию:', self.defaultPriceEdit)
        
        # Стили для лейблов
        layout.setLabelAlignment(QtCore.Qt.AlignRight)
        for i in range(layout.rowCount()):
            label = layout.itemAt(i, QtWidgets.QFormLayout.LabelRole)
            if label and label.widget():
                label.widget().setStyleSheet("""
                    QLabel {
                        color: #f0f0f0;
                        font-weight: bold;
                        padding-right: 5px;
                    }
                """)
        
        self.setLayout(layout)
        
        # Регистрируем поля
        self.registerField('profile_name', self.profileNameEdit)
        self.registerField('brand', self.brandEdit)
        self.registerField('category', self.categoryEdit)
        self.registerField('vat', self.vatEdit)
        self.registerField('material', self.materialEdit)
        self.registerField('description', self.descriptionEdit)
        self.registerField('weight', self.weightEdit)
        self.registerField('default_price', self.defaultPriceEdit)


class FinalPage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle('Настройка завершена!')
        self.setSubTitle('Программа готова к работе')
        
        layout = QtWidgets.QVBoxLayout()
        
        # Иконка успеха
        successIcon = QtWidgets.QLabel('OK!')
        successIcon.setAlignment(QtCore.Qt.AlignCenter)
        successIcon.setStyleSheet("""
            QLabel {
                font-size: 48px;
                color: #4CAF50;
                background: transparent;
                margin: 10px;
                font-weight: bold;
            }
        """)
        
        summary = QtWidgets.QLabel(
            'Отлично! Настройка завершена.\n\n'
            'Что дальше:\n\n'
            '1. Подготовьте изображения с правильными именами файлов\n'
            '   Формат: товар_номер.расширение (например: мама_1.1.jpg, мама_1.2.jpg)\n\n'
            '2. Используйте кнопку "Сканировать" для загрузки папки с фото\n\n'
            '3. Заполните данные товаров в правой панели\n\n'
            '4. Запустите загрузку в Яндекс.Диск\n\n'
            '5. Сформируйте Excel-файл для загрузки на Wildberries\n\n'
            'Удачной работы!'
        )
        summary.setWordWrap(True)
        summary.setAlignment(QtCore.Qt.AlignLeft)
        summary.setStyleSheet("""
            QLabel {
                color: #f0f0f0;
                background: transparent;
                font-size: 11px;
                line-height: 1.4;
                padding: 10px;
            }
        """)
        summary.setToolTip(
            'После завершения мастера откроется главное окно программы\n'
            'Все настройки сохранены и будут загружены автоматически'
        )
        
        # Дополнительные советы
        tips = QtWidgets.QLabel(
            'Полезные советы:\n'
            '- Сохраняйте резервные копии Excel-файлов\n'
            '- Используйте профили для разных категорий товаров\n'
            '- Проверяйте публичные ссылки перед отправкой на WB'
        )
        tips.setWordWrap(True)
        tips.setStyleSheet("""
            QLabel {
                color: #FFD700;
                background: rgba(255, 215, 0, 0.1);
                border: 1px solid #FFD700;
                border-radius: 5px;
                padding: 8px;
                font-style: italic;
                font-size: 10px;
            }
        """)
        tips.setToolTip(
            'Эти советы помогут вам эффективнее работать с программой'
        )
        
        layout.addWidget(successIcon)
        layout.addWidget(summary)
        layout.addWidget(tips)
        layout.addStretch()
        self.setLayout(layout)


def show_setup_wizard(parent=None):
    """Показывает мастер настройки и возвращает результаты"""
    wizard = SetupWizard(parent)
    
    if wizard.exec_() == QtWidgets.QDialog.Accepted:
        return {
            'token': wizard.field('token'),
            'root': wizard.field('root'),
            'profile_name': wizard.field('profile_name'),
            'brand': wizard.field('brand'),
            'category': wizard.field('category'),
            'vat': wizard.field('vat'),
            'material': wizard.field('material'),
            'description': wizard.field('description'),
            'weight': wizard.field('weight'),
            'default_price': wizard.field('default_price'),
        }
    return None
