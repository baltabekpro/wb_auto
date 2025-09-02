import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List

from PyQt5 import QtCore, QtGui, QtWidgets
import keyring

from core.parser import group_photos_flat
from core.profiles import list_profiles, load_profile
from core.xlsx_gen import create_wb_workbook, append_row
from core.yadisk_client import upload_sku_photos
from core.reports import generate_upload_report, export_csv_report
from core.setup_wizard import show_setup_wizard
from core.auto_updater import AutoUpdater


class Worker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, int)  # done, total
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(dict)  # sku -> [links]

    def __init__(self, grouped, token, root, overwrite_mode, max_photos, concurrency=1, limit=0, parent=None):
        super().__init__(parent)
        self.grouped = grouped
        self.token = token
        self.root = root
        self.overwrite_mode = overwrite_mode
        self.max_photos = int(max_photos or 6)
        self.concurrency = max(1, int(concurrency or 1))
        self.limit = max(0, int(limit or 0))
        self.results: Dict[str, List[str]] = {}

    def _upload_one(self, sku, files):
        files_to_upload = [f.path for f in files][: self.max_photos]
        urls = upload_sku_photos(keyring, self.token, self.root, sku, files_to_upload, self.overwrite_mode)
        return sku, [u.direct_url for u in urls][: self.max_photos]

    def run(self):
        try:
            items = list(self.grouped.by_sku.items())
            if self.limit > 0:
                items = items[: self.limit]
            total = len(items)
            done = 0
            if self.concurrency <= 1:
                for sku, files in items:
                    try:
                        sku, links = self._upload_one(sku, files)
                        self.results[sku] = links
                    except Exception as e:
                        self.message.emit(f"Ошибка для {sku}: {e}")
                    finally:
                        done += 1
                        self.progress.emit(done, total)
            else:
                with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
                    futures = {ex.submit(self._upload_one, sku, files): sku for sku, files in items}
                    for fut in as_completed(futures):
                        sku_key = futures[fut]
                        try:
                            sku_res, links = fut.result()
                            self.results[sku_res] = links
                        except Exception as e:
                            self.message.emit(f"Ошибка для {sku_key}: {e}")
                        finally:
                            done += 1
                            self.progress.emit(done, total)
            self.finished_ok.emit(self.results)
        except Exception as e:
            self.message.emit(str(e))


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return QtCore.QSize(400, 300)

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        for item in self.itemList:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + self.spacing()
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = x + w + self.spacing()
            lineHeight = max(lineHeight, h)
        return y + lineHeight - rect.y()


class DropLineEdit(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e: QtGui.QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            local = urls[0].toLocalFile()
            if local and os.path.isdir(local):
                self.setText(local)
        super().dropEvent(e)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('WB Кружки — автозагрузка')
        self.resize(1280, 800)
        self.grouped = None
        self.profile = None
        self.profile_files = {}
        self.upload_results: Dict[str, List[str]] = {}
        self.settings = QtCore.QSettings('WBAuto', 'WBAuto')
        
        # Инициализация автообновления
        self.auto_updater = AutoUpdater(self)
        
        self._build_ui()
        self._create_menu()  # Создаем меню
        self._apply_styles()
        
        # Проверяем, нужно ли показать мастер настройки
        self._check_first_run()
        
        # Принудительная загрузка профилей на всякий случай
        if not self.profile_files:
            self._load_profiles()

    def _build_ui(self):
        # Central splitter: left controls, center table, right preview
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left panel — controls
        left = QtWidgets.QWidget()
        leftLayout = QtWidgets.QVBoxLayout(left)
        leftLayout.setContentsMargins(12, 12, 12, 12)
        leftLayout.setSpacing(12)
        left.setMinimumWidth(420)

        grpProfile = QtWidgets.QGroupBox('Профиль и источник')
        f1 = QtWidgets.QFormLayout(grpProfile)
        f1.setFormAlignment(QtCore.Qt.AlignTop)
        f1.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.profileCombo = QtWidgets.QComboBox()
        self.refreshProfilesBtn = QtWidgets.QPushButton('R')
        self.refreshProfilesBtn.setMaximumWidth(30)
        self.refreshProfilesBtn.setToolTip('Обновить список профилей')
        self.refreshProfilesBtn.clicked.connect(self._load_profiles)
        
        hProfiles = QtWidgets.QHBoxLayout()
        hProfiles.addWidget(self.profileCombo)
        hProfiles.addWidget(self.refreshProfilesBtn)
        
        self.photosEdit = DropLineEdit()
        self.photosEdit.setPlaceholderText('Путь к папке с фото')
        btnChoose = QtWidgets.QPushButton('Обзор…')
        btnChoose.clicked.connect(self.choose_folder)
        hPhotos = QtWidgets.QHBoxLayout()
        hPhotos.addWidget(self.photosEdit)
        hPhotos.addWidget(btnChoose)
        self.patternEdit = QtWidgets.QLineEdit(r"^(?P<sku>.+)\.(?P<n>\d+)\.(?P<ext>jpe?g|png)$")
        self.patternEdit.setClearButtonEnabled(True)
        f1.addRow('Профиль:', hProfiles)
        f1.addRow('Фото:', hPhotos)
        f1.addRow('Паттерн:', self.patternEdit)

        grpYD = QtWidgets.QGroupBox('Яндекс.Диск')
        f2 = QtWidgets.QFormLayout(grpYD)
        self.tokenEdit = QtWidgets.QLineEdit()
        self.tokenEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.tokenEdit.setPlaceholderText('OAuth токен')
        tokenRow = QtWidgets.QHBoxLayout()
        btnEye = QtWidgets.QToolButton()
        btnEye.setCheckable(True)
        btnEye.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DesktopIcon))
        btnEye.setToolTip('Показать/скрыть токен')
        btnClearToken = QtWidgets.QToolButton()
        btnClearToken.setText('Очистить токен')
        btnClearToken.setToolTip('Удалить токен из поля (и не сохранять)')
        tokenRow.addWidget(self.tokenEdit)
        tokenRow.addWidget(btnEye)
        tokenRow.addWidget(btnClearToken)
        self.rootEdit = QtWidgets.QLineEdit('/WB/Kruzhki')
        self.overwriteMode = QtWidgets.QComboBox()
        self.overwriteMode.addItems(['Не перезаписывать', 'Перезаписывать изменившиеся', 'Всегда перезаписывать'])
        self.concSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.concSlider.setRange(1, 6)
        self.concSlider.setValue(2)
        self.concSlider.setToolTip('Одновременных загрузок SKU')
        self.limitSpin = QtWidgets.QSpinBox()
        self.limitSpin.setRange(0, 9999)
        self.limitSpin.setValue(0)
        self.limitSpin.setToolTip('Загружать только первые N SKU (0 — все)')
        f2.addRow('OAuth токен:', tokenRow)
        f2.addRow('Корень:', self.rootEdit)
        f2.addRow('Режим перезаписи:', self.overwriteMode)
        f2.addRow('Параллельность:', self.concSlider)
        f2.addRow('Тестовый лимит N:', self.limitSpin)
        warn = QtWidgets.QLabel('Токен хранится локально; вы можете удалить его в Настройках.')
        warn.setStyleSheet('color:#caa; font-size:11px;')
        f2.addRow('', warn)

        btns = QtWidgets.QGridLayout()
        self.scanBtn = QtWidgets.QPushButton('Сканировать')
        self.importBtn = QtWidgets.QPushButton('Импорт данных')
        self.startBtn = QtWidgets.QPushButton('Загрузить в Яндекс.Диск')
        self.saveBtn = QtWidgets.QPushButton('Сформировать XLSX')
        self.reportBtn = QtWidgets.QPushButton('Экспорт отчёта')
        self.openFolderBtn = QtWidgets.QPushButton('Открыть папку')
        
        # Устанавливаем минимальную ширину для всех кнопок
        button_min_width = 140
        for btn in [self.scanBtn, self.importBtn, self.startBtn, self.saveBtn, self.reportBtn, self.openFolderBtn]:
            btn.setMinimumWidth(button_min_width)
            btn.setMinimumHeight(32)
        
        # Размещаем кнопки в сетке 2x3
        btns.addWidget(self.scanBtn, 0, 0)
        btns.addWidget(self.importBtn, 0, 1)
        btns.addWidget(self.startBtn, 0, 2)
        btns.addWidget(self.saveBtn, 1, 0)
        btns.addWidget(self.reportBtn, 1, 1)
        btns.addWidget(self.openFolderBtn, 1, 2)

        leftLayout.addWidget(grpProfile)
        leftLayout.addWidget(grpYD)
        leftLayout.addLayout(btns)
        leftLayout.addStretch(1)

        splitter.addWidget(left)

        # Center — table with search
        center = QtWidgets.QWidget()
        centerLayout = QtWidgets.QVBoxLayout(center)
        searchLayout = QtWidgets.QHBoxLayout()
        self.searchEdit = QtWidgets.QLineEdit()
        self.searchEdit.setPlaceholderText('Поиск по SKU…')
        act = self.searchEdit.addAction(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogContentsView), QtWidgets.QLineEdit.LeadingPosition)
        act.setVisible(True)
        searchLayout.addWidget(QtWidgets.QLabel('Поиск:'))
        searchLayout.addWidget(self.searchEdit)
        centerLayout.addLayout(searchLayout)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['SKU', 'Файлов', 'Список файлов'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setShowGrid(False)
        centerLayout.addWidget(self.table)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        centerLayout.addWidget(self.progress)

        splitter.addWidget(center)

        # Right — SKU details form + preview thumbnails
        right = QtWidgets.QWidget()
        rightLayout = QtWidgets.QVBoxLayout(right)
        right.setMinimumWidth(320)
        
        # SKU Edit Form
        grpSku = QtWidgets.QGroupBox('Карточка SKU')
        skuForm = QtWidgets.QFormLayout(grpSku)
        skuForm.setFormAlignment(QtCore.Qt.AlignTop)
        skuForm.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        
        self.skuNameEdit = QtWidgets.QLineEdit()
        self.skuNameEdit.setPlaceholderText('Наименование товара')
        self.skuPriceEdit = QtWidgets.QLineEdit()
        self.skuPriceEdit.setPlaceholderText('Цена (руб.)')
        self.skuColorEdit = QtWidgets.QLineEdit()
        self.skuColorEdit.setPlaceholderText('Цвет')
        self.skuVolumeEdit = QtWidgets.QLineEdit()
        self.skuVolumeEdit.setPlaceholderText('Объем (мл)')
        self.skuMaterialEdit = QtWidgets.QLineEdit()
        self.skuMaterialEdit.setPlaceholderText('Материал посуды')
        self.skuGiftEdit = QtWidgets.QLineEdit()
        self.skuGiftEdit.setPlaceholderText('Назначение подарка')
        self.skuPatternEdit = QtWidgets.QLineEdit()
        self.skuPatternEdit.setPlaceholderText('Рисунок')
        self.skuComplectEdit = QtWidgets.QLineEdit()
        self.skuComplectEdit.setPlaceholderText('Комплектация')
        
        skuForm.addRow('Название:', self.skuNameEdit)
        skuForm.addRow('Цена:', self.skuPriceEdit)
        skuForm.addRow('Цвет:', self.skuColorEdit)
        skuForm.addRow('Объем (мл):', self.skuVolumeEdit)
        skuForm.addRow('Материал:', self.skuMaterialEdit)
        skuForm.addRow('Подарок для:', self.skuGiftEdit)
        skuForm.addRow('Рисунок:', self.skuPatternEdit)
        skuForm.addRow('Комплектация:', self.skuComplectEdit)
        
        self.currentSku = None
        self.skuData = {}  # sku -> {name, price, color, volume, material, gift, pattern, complect}
        
        rightLayout.addWidget(grpSku)
        
        # Preview section
        lblPrev = QtWidgets.QLabel('Превью фото')
        lblPrev.setStyleSheet('color:#bbb; font-weight:600; padding:4px 6px;')
        rightLayout.addWidget(lblPrev)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background:#242424; } QScrollArea { border:1px solid #333; border-radius:6px; }')
        # Ensure viewport specifically is dark
        scroll.viewport().setStyleSheet('background:#242424;')
        self.previewContainer = QtWidgets.QWidget()
        self.previewFlow = FlowLayout(self.previewContainer)
        scroll.setWidget(self.previewContainer)
        rightLayout.addWidget(scroll)
        splitter.addWidget(right)

        splitter.setSizes([420, 760, 380])

        # Bottom collapsible log panel
        self.logDock = QtWidgets.QDockWidget('Лог', self)
        self.logDock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)
        logW = QtWidgets.QWidget()
        logL = QtWidgets.QVBoxLayout(logW)
        logTop = QtWidgets.QHBoxLayout()
        self.logLevel = QtWidgets.QComboBox()
        self.logLevel.addItems(['INFO', 'WARN', 'ERROR'])
        btnCopyLog = QtWidgets.QPushButton('Скопировать лог')
        logTop.addWidget(QtWidgets.QLabel('Уровень:'))
        logTop.addWidget(self.logLevel)
        logTop.addStretch(1)
        logTop.addWidget(btnCopyLog)
        self.logEdit = QtWidgets.QPlainTextEdit()
        self.logEdit.setReadOnly(True)
        self.logEdit.setMaximumBlockCount(5000)
        logL.addLayout(logTop)
        logL.addWidget(self.logEdit)
        logW.setLayout(logL)
        self.logDock.setWidget(logW)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.logDock)
        self.logDock.setVisible(False)

        # Toolbar
        tb = self.addToolBar('Действия')
        tb.setIconSize(QtCore.QSize(22, 22))
        tb.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        style = self.style()
        actScan = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_BrowserReload), 'Сканировать', self)
        actStart = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_MediaPlay), 'Загрузить в Я.Диск', self)
        actSave = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), 'Сформировать XLSX', self)
        actOpen = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_DirOpenIcon), 'Открыть папку', self)
        actSetup = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_ComputerIcon), 'Мастер настройки', self)
        tb.addAction(actScan)
        tb.addAction(actStart)
        tb.addAction(actSave)
        tb.addSeparator()
        tb.addAction(actOpen)
        tb.addAction(actSetup)
        actLog = QtWidgets.QAction('Лог', self)
        actLog.setCheckable(True)
        actLog.toggled.connect(self.logDock.setVisible)
        tb.addSeparator()
        tb.addAction(actLog)

        # Signals
        self.scanBtn.clicked.connect(self.scan)
        self.importBtn.clicked.connect(self.import_data)
        self.startBtn.clicked.connect(self.start_upload)
        self.saveBtn.clicked.connect(self.save_xlsx)
        self.reportBtn.clicked.connect(self.export_report)
        self.openFolderBtn.clicked.connect(self.open_current_folder)
        self.profileCombo.currentIndexChanged.connect(self.profile_changed)
        self.searchEdit.textChanged.connect(self.apply_filter)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        actScan.triggered.connect(self.scan)
        actStart.triggered.connect(self.start_upload)
        actSave.triggered.connect(self.save_xlsx)
        actOpen.triggered.connect(self.open_current_folder)
        actSetup.triggered.connect(self.show_setup_wizard)
        # Context menu for table
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_context_menu)
        btnEye.toggled.connect(self._toggle_token_visibility)
        btnClearToken.clicked.connect(lambda: self.tokenEdit.clear())
        btnCopyLog.clicked.connect(self._copy_log)
        
        # SKU form signals for auto-save
        self.skuNameEdit.textChanged.connect(self._save_current_sku_data)
        self.skuPriceEdit.textChanged.connect(self._save_current_sku_data)
        self.skuColorEdit.textChanged.connect(self._save_current_sku_data)
        self.skuVolumeEdit.textChanged.connect(self._save_current_sku_data)
        self.skuMaterialEdit.textChanged.connect(self._save_current_sku_data)
        self.skuGiftEdit.textChanged.connect(self._save_current_sku_data)
        self.skuPatternEdit.textChanged.connect(self._save_current_sku_data)
        self.skuComplectEdit.textChanged.connect(self._save_current_sku_data)

    def _create_menu(self):
        """Создает главное меню приложения"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu('Файл')
        
        # Действие "Выход"
        exit_action = QtWidgets.QAction('Выход', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню "Инструменты"
        tools_menu = menubar.addMenu('Инструменты')
        
        # Действие "Мастер настройки"
        setup_action = QtWidgets.QAction('Мастер настройки', self)
        setup_action.triggered.connect(self.show_setup_wizard)
        tools_menu.addAction(setup_action)
        
        tools_menu.addSeparator()
        
        # Действие "Настройки"
        settings_action = QtWidgets.QAction('Настройки', self)
        settings_action.triggered.connect(self.show_settings)
        tools_menu.addAction(settings_action)
        
        # Меню "Справка"
        help_menu = menubar.addMenu('Справка')
        
        # Действие "Проверить обновления"
        update_action = QtWidgets.QAction('Проверить обновления', self)
        update_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(update_action)
        
        help_menu.addSeparator()
        
        # Действие "О программе"
        about_action = QtWidgets.QAction('О программе', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _load_settings(self):
        """Загружает настройки приложения"""
        # Restore last settings
        last_folder = self.settings.value('photos_dir', '')
        self.photosEdit.setText(last_folder)
        
        # Загружаем токен Яндекс.Диска
        token = self.settings.value('yandex_token', '')
        self.tokenEdit.setText(token)
        
        # Загружаем корневую папку
        root = self.settings.value('yandex_root', '/WB/Kruzhki')
        self.rootEdit.setText(root)
        
        # restore overwrite mode, concurrency, limit
        ow_idx = int(self.settings.value('overwrite_idx', 0) or 0)
        self.overwriteMode.setCurrentIndex(max(0, min(2, ow_idx)))
        conc = int(self.settings.value('concurrency', 2) or 2)
        self.concSlider.setValue(max(1, min(6, conc)))
        limit = int(self.settings.value('limit', 0) or 0)
        self.limitSpin.setValue(max(0, limit))

    def _toggle_token_visibility(self, checked: bool):
        self.tokenEdit.setEchoMode(QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password)

    def _copy_log(self):
        QtWidgets.QApplication.clipboard().setText(self.logEdit.toPlainText())

    def _save_current_sku_data(self):
        """Auto-save current SKU data when any field changes"""
        if not self.currentSku:
            return
        
        self.skuData[self.currentSku] = {
            'name': self.skuNameEdit.text().strip(),
            'price': self.skuPriceEdit.text().strip(),
            'color': self.skuColorEdit.text().strip(),
            'volume': self.skuVolumeEdit.text().strip(),
            'material': self.skuMaterialEdit.text().strip(),
            'gift': self.skuGiftEdit.text().strip(),
            'pattern': self.skuPatternEdit.text().strip(),
            'complect': self.skuComplectEdit.text().strip()
        }

    def _load_sku_data(self, sku: str):
        """Load SKU data into the form"""
        self.currentSku = sku
        data = self.skuData.get(sku, {})
        
        # Temporarily disconnect signals to avoid recursive save
        self.skuNameEdit.textChanged.disconnect()
        self.skuPriceEdit.textChanged.disconnect()
        self.skuColorEdit.textChanged.disconnect()
        self.skuVolumeEdit.textChanged.disconnect()
        self.skuMaterialEdit.textChanged.disconnect()
        self.skuGiftEdit.textChanged.disconnect()
        self.skuPatternEdit.textChanged.disconnect()
        self.skuComplectEdit.textChanged.disconnect()
        
        self.skuNameEdit.setText(data.get('name', ''))
        self.skuPriceEdit.setText(data.get('price', ''))
        self.skuColorEdit.setText(data.get('color', ''))
        self.skuVolumeEdit.setText(data.get('volume', ''))
        self.skuMaterialEdit.setText(data.get('material', ''))
        self.skuGiftEdit.setText(data.get('gift', ''))
        self.skuPatternEdit.setText(data.get('pattern', ''))
        self.skuComplectEdit.setText(data.get('complect', ''))
        
        # Reconnect signals
        self.skuNameEdit.textChanged.connect(self._save_current_sku_data)
        self.skuPriceEdit.textChanged.connect(self._save_current_sku_data)
        self.skuColorEdit.textChanged.connect(self._save_current_sku_data)
        self.skuVolumeEdit.textChanged.connect(self._save_current_sku_data)
        self.skuMaterialEdit.textChanged.connect(self._save_current_sku_data)
        self.skuGiftEdit.textChanged.connect(self._save_current_sku_data)
        self.skuPatternEdit.textChanged.connect(self._save_current_sku_data)
        self.skuComplectEdit.textChanged.connect(self._save_current_sku_data)

    def _clear_sku_form(self):
        """Clear the SKU form"""
        self.currentSku = None
        
        # Temporarily disconnect signals
        self.skuNameEdit.textChanged.disconnect()
        self.skuPriceEdit.textChanged.disconnect()
        self.skuColorEdit.textChanged.disconnect()
        self.skuVolumeEdit.textChanged.disconnect()
        self.skuMaterialEdit.textChanged.disconnect()
        self.skuGiftEdit.textChanged.disconnect()
        self.skuPatternEdit.textChanged.disconnect()
        self.skuComplectEdit.textChanged.disconnect()
        
        self.skuNameEdit.clear()
        self.skuPriceEdit.clear()
        self.skuColorEdit.clear()
        self.skuVolumeEdit.clear()
        self.skuMaterialEdit.clear()
        self.skuGiftEdit.clear()
        self.skuPatternEdit.clear()
        self.skuComplectEdit.clear()
        
        # Reconnect signals
        self.skuNameEdit.textChanged.connect(self._save_current_sku_data)
        self.skuPriceEdit.textChanged.connect(self._save_current_sku_data)
        self.skuColorEdit.textChanged.connect(self._save_current_sku_data)
        self.skuVolumeEdit.textChanged.connect(self._save_current_sku_data)
        self.skuMaterialEdit.textChanged.connect(self._save_current_sku_data)
        self.skuGiftEdit.textChanged.connect(self._save_current_sku_data)
        self.skuPatternEdit.textChanged.connect(self._save_current_sku_data)
        self.skuComplectEdit.textChanged.connect(self._save_current_sku_data)

    def _apply_styles(self):
        # Base style & font
        QtWidgets.QApplication.setStyle('Fusion')
        QtWidgets.QApplication.setFont(QtGui.QFont('Segoe UI', 10))
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 45))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 45))
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(170, 170, 170))
        # Better disabled contrast
        palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor(170, 170, 170))
        palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtGui.QColor(170, 170, 170))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
        palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(76, 163, 224))
        palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
        self.setPalette(palette)
        self.setStyleSheet(
            """
            QMainWindow { background:#2b2b2b; }
            QSplitter::handle { background: #3a3a3a; width: 6px; }
            QLabel { color: #ddd; }
            QGroupBox { border: 1px solid #4a4a4a; border-radius: 8px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 2px 6px; color: #ddd; font-weight:600; }
            QPushButton { background-color: #4a90e2; color: white; border: none; padding: 8px 12px; border-radius: 6px; font-weight: 500; min-width: 120px; }
            QPushButton:hover { background-color: #5aa0f2; }
            QPushButton:disabled { background-color: #666; color: #aaa; }
            QLineEdit { background: #232323; color: #eee; border: 1px solid #4a4a4a; padding: 6px 8px; border-radius: 6px; }
            QLineEdit:focus { border: 1px solid #5aa0f2; }
            QPlainTextEdit, QTextEdit { background: #1f1f1f; color: #eee; border: 1px solid #444; border-radius: 6px; }
            QComboBox { background:#232323; color:#eee; border:1px solid #4a4a4a; padding: 4px 8px; border-radius:6px; }
            QComboBox QAbstractItemView { background:#2a2a2a; color:#eee; selection-background-color:#4a90e2; selection-color:white; }
            QSpinBox, QDoubleSpinBox { background:#232323; color:#eee; border:1px solid #4a4a4a; border-radius:6px; padding: 2px 6px; }
            QSlider::groove:horizontal { height:6px; background:#3a3a3a; border-radius:3px; }
            QSlider::handle:horizontal { background:#4a90e2; width:14px; margin:-4px 0; border-radius:7px; }
            QTableWidget { gridline-color: #555; background:#1f1f1f; }
            QHeaderView::section { background: #343434; color: #ddd; padding: 8px; border: 0; }
            QToolBar { background:#2b2b2b; border-bottom: 1px solid #3a3a3a; }
            /* Toolbar buttons: make text brighter and more legible */
            QToolBar QToolButton { color:#f0f0f0; padding:6px 10px; border-radius:4px; }
            QToolBar QToolButton:hover { background:#3a3a3a; color:#ffffff; }
            QToolBar QToolButton:pressed { background:#357acc; color:#ffffff; }
            QToolBar QToolButton:checked { background:#4a90e2; color:#ffffff; }
            QToolBar QToolButton:disabled { color:#8c8c8c; }
            QDockWidget { background:#2b2b2b; titlebar-close-icon: url(none); titlebar-normal-icon: url(none); }
            QDockWidget::title { background:#2f2f2f; padding:6px; color:#ddd; border-bottom:1px solid #3a3a3a; }
            /* Menus: brighter text */
            QMenu { background:#2a2a2a; color:#f2f2f2; border:1px solid #3a3a3a; }
            QMenu::item { padding:6px 14px; }
            QMenu::item:selected { background:#4a90e2; color:#ffffff; }
            /* Menu bar */
            QMenuBar { background:#2b2b2b; color:#f2f2f2; spacing:6px; padding:4px; }
            QMenuBar::item { background:transparent; padding:4px 8px; margin:0 2px; }
            QMenuBar::item:selected { background:#3a3a3a; color:#ffffff; border-radius:4px; }
            QMenuBar::item:pressed { background:#357acc; color:#ffffff; border-radius:4px; }
            QProgressBar { background: #2d2d2d; border: 1px solid #555; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: #4a90e2; }
            /* Make all scroll areas dark, including viewport */
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background:#242424; }
            QScrollBar:vertical { background:#2a2a2a; width:12px; }
            QScrollBar::handle:vertical { background:#4a4a4a; min-height:24px; border-radius:6px; }
            QScrollBar:horizontal { background:#2a2a2a; height:12px; }
            QScrollBar::handle:horizontal { background:#4a4a4a; min-width:24px; border-radius:6px; }
            """
        )

    def _check_first_run(self):
        """Проверяет первый запуск и показывает мастер настройки при необходимости"""
        # Загружаем профили для проверки
        self._load_profiles()
        
        # Проверяем настройки первого запуска
        first_run = self.settings.value('first_run', True, type=bool)
        has_profiles = len(self.profile_files) > 0
        has_token = bool(self.settings.value('yandex_token', ''))
        
        # Если первый запуск или нет профилей/токена, показываем мастер
        if first_run or not has_profiles or not has_token:
            self._show_setup_wizard()
        else:
            # Загружаем последний профиль
            self._load_last_profile()
            # Показываем главное окно
            self.show()
    
    def _show_setup_wizard(self):
        """Показывает мастер настройки"""
        
        # Скрываем главное окно
        self.hide()
        
        # Показываем мастер настройки
        result = show_setup_wizard(self)
        
        if result:
            # Сохраняем настройки из мастера
            self._save_wizard_settings(result)
            
            # Перезагружаем профили
            self._load_profiles()
            
            # Показываем главное окно
            self.show()
            
            # Отмечаем, что первый запуск завершён
            self.settings.setValue('first_run', False)
        else:
            # Пользователь отменил настройку - закрываем приложение
            QtWidgets.QApplication.quit()
    
    def _save_wizard_settings(self, wizard_data):
        """Сохраняет настройки из мастера"""
        # Сохраняем токен Яндекс.Диска
        if wizard_data.get('token'):
            self.settings.setValue('yandex_token', wizard_data['token'])
        
        # Сохраняем корневую папку
        if wizard_data.get('root'):
            self.settings.setValue('yandex_root', wizard_data['root'])
        
        # Создаём профиль из данных мастера
        self._create_profile_from_wizard(wizard_data)
    
    def _create_profile_from_wizard(self, wizard_data):
        """Создаёт профиль из данных мастера"""
        profiles_path = os.path.join(os.path.dirname(__file__), '..', 'profiles')
        
        # Создаём папку если не существует
        os.makedirs(profiles_path, exist_ok=True)
        
        # Данные профиля
        profile_name = wizard_data.get('profile_name', 'Мой профиль')
        
        # Используем описание из мастера, если есть, иначе генерируем автоматически
        if wizard_data.get('description'):
            description_template = wizard_data['description']
        else:
            description_template = f"{wizard_data.get('material', 'Качественный')} {wizard_data.get('category', 'товар')} {{sku}}. Объем {{volume}} мл."
        
        profile_data = {
            "name": profile_name,
            "brand": wizard_data.get('brand', 'Мой бренд'),
            "title_template": f"{wizard_data.get('category', 'Товар')} {{sku}} {{volume}} мл",
            "description_template": description_template,
            "gender": "унисекс",
            "composition": f"{wizard_data.get('material', 'материал')} 100%",
            "color": "белый",
            "vat": wizard_data.get('vat', '20%'),
            "package_weight_g": wizard_data.get('weight', 350),
            "dims": {"H_cm": 10, "L_cm": 12, "W_cm": 9},
            "age18": "Нет",
            "photo_sep": ";",
            "max_photos": 6,
            "wb_category": wizard_data.get('category', 'Товары'),
            "seller_category": f"{wizard_data.get('category', 'Товары')}/Разное",
            "calc_weight_kg_from_g": True,
            "yadisk_root": wizard_data.get('root', '/WB/Товары'),
            "defaults": {
                "size": "универсальный",
                "rus_size": "универсальный", 
                "price": wizard_data.get('default_price', 499),
                "volume": 330
            }
        }
        
        # Сохраняем профиль
        import json
        profile_name_safe = profile_name.lower().replace(' ', '_').replace('—', '_').replace('-', '_')
        profile_file = os.path.join(profiles_path, f'{profile_name_safe}_profile.json')
        
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    def _load_last_profile(self):
        """Загружает последний использованный профиль"""
        # Загружаем основные настройки
        self._load_settings()
        
        # Загружаем последний профиль
        last_profile = self.settings.value('profile_name', '')
        if last_profile and last_profile in self.profile_files:
            idx = self.profileCombo.findText(last_profile)
            if idx >= 0:
                self.profileCombo.setCurrentIndex(idx)

    def _load_profiles(self):
        """Загружает профили (автоматически определяет путь для exe и dev режима)"""
        print("🔄 Загрузка профилей...")
        self.profile_files = list_profiles()  # Без параметра - автоматический поиск
        
        self.profileCombo.clear()
        for name in self.profile_files.keys():
            self.profileCombo.addItem(name)
        if self.profileCombo.count() > 0:
            self.profileCombo.setCurrentIndex(0)
            self.profile_changed(0)
        else:
            print("⚠️ Профили не загружены! Проверьте папку profiles")

    def profile_changed(self, idx):
        name = self.profileCombo.currentText()
        if name and name in self.profile_files:
            self.profile = load_profile(self.profile_files[name])
            root = self.profile.get('yadisk_root') or '/WB/Kruzhki'
            self.rootEdit.setText(root)

    def import_data(self):
        """Import SKU data from CSV/Excel file"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Импорт данных SKU', '', 
            'Excel и CSV файлы (*.xlsx *.xls *.csv);;Excel (*.xlsx *.xls);;CSV (*.csv)'
        )
        if not path:
            return
            
        try:
            import pandas as pd
            
            # Try to read the file
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path, encoding='utf-8')
            else:
                df = pd.read_excel(path)
            
            # Expected columns: sku, name, price, barcode, color
            # (case-insensitive matching)
            columns = {col.lower(): col for col in df.columns}
            
            sku_col = None
            for possible in ['sku', 'артикул', 'article', 'артикул продавца']:
                if possible in columns:
                    sku_col = columns[possible]
                    break
                    
            if not sku_col:
                QtWidgets.QMessageBox.warning(
                    self, 'Ошибка импорта', 
                    'Не найден столбец SKU/Артикул в файле'
                )
                return
            
            imported_count = 0
            
            for _, row in df.iterrows():
                sku = str(row[sku_col]).strip()
                if not sku or sku.lower() in ['nan', 'none']:
                    continue
                
                data = {}
                
                # Import name
                for possible in ['name', 'название', 'наименование', 'title']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['name'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import price
                for possible in ['price', 'цена', 'cost']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        try:
                            price_val = float(row[columns[possible]])
                            data['price'] = str(int(price_val) if price_val.is_integer() else price_val)
                        except (ValueError, TypeError):
                            data['price'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import color
                for possible in ['color', 'цвет', 'colour']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['color'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import volume
                for possible in ['volume', 'объем', 'объём', 'мл']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['volume'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import material
                for possible in ['material', 'материал', 'состав']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['material'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import gift purpose
                for possible in ['gift', 'подарок', 'назначение', 'для кого']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['gift'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import pattern
                for possible in ['pattern', 'рисунок', 'узор']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['pattern'] = str(row[columns[possible]]).strip()
                        break
                        
                # Import complect
                for possible in ['complect', 'комплектация', 'комплект']:
                    if possible in columns and not pd.isna(row[columns[possible]]):
                        data['complect'] = str(row[columns[possible]]).strip()
                        break
                
                # Update SKU data
                if sku not in self.skuData:
                    self.skuData[sku] = {}
                self.skuData[sku].update(data)
                imported_count += 1
            
            # Update current form if the displayed SKU was imported
            if self.currentSku and self.currentSku in self.skuData:
                self._load_sku_data(self.currentSku)
            
            QtWidgets.QMessageBox.information(
                self, 'Импорт завершен', 
                f'Импортированы данные для {imported_count} SKU'
            )
            self.statusBar().showMessage(f'Импортированы данные для {imported_count} SKU', 5000)
            
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self, 'Ошибка', 
                'Для импорта требуется библиотека pandas.\nУстановите её: pip install pandas openpyxl'
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 'Ошибка импорта', 
                f'Не удалось импортировать данные:\n{str(e)}'
            )

    def show_setup_wizard(self):
        """Запуск мастера настройки"""
        result = show_setup_wizard(self)
        
        if result:
            # Применяем настройки из мастера
            self.tokenEdit.setText(result['token'])
            self.rootEdit.setText(result['root'])
            
            # Можно создать профиль автоматически
            QtWidgets.QMessageBox.information(
                self, 'Настройка завершена',
                'Настройки применены! Рекомендуем создать профиль с указанными параметрами.'
            )

    def export_report(self):
        """Export detailed report about upload process"""
        if not self.grouped:
            QtWidgets.QMessageBox.warning(self, 'Ошибка', 'Нет данных для отчёта. Выполните сканирование.')
            return
        
        # Choose export format
        reply = QtWidgets.QMessageBox.question(
            self, 'Формат отчёта', 
            'Выберите формат отчёта:\n\nYes = Подробный отчёт (Excel)\nNo = Простой отчёт (CSV)',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
        )
        
        if reply == QtWidgets.QMessageBox.Cancel:
            return
        
        # Get export path
        now = datetime.now().strftime('%Y%m%d-%H%M%S')
        if reply == QtWidgets.QMessageBox.Yes:
            default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports', f'wb_report_{now}.xlsx'))
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Сохранить отчёт', default_path, 'Excel файлы (*.xlsx)'
            )
            if not path:
                return
            
            try:
                warnings = getattr(self.grouped, 'warnings', [])
                report_path = generate_upload_report(self.grouped, self.upload_results, warnings, path)
                QtWidgets.QMessageBox.information(self, 'Отчёт создан', f'Подробный отчёт сохранён:\n{report_path}')
                self.statusBar().showMessage(f'Отчёт сохранён: {os.path.basename(report_path)}', 5000)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Ошибка', f'Не удалось создать отчёт:\n{str(e)}')
        
        else:  # CSV
            default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports', f'wb_report_{now}.csv'))
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Сохранить отчёт', default_path, 'CSV файлы (*.csv)'
            )
            if not path:
                return
            
            try:
                report_path = export_csv_report(self.grouped, self.upload_results, path)
                QtWidgets.QMessageBox.information(self, 'Отчёт создан', f'CSV отчёт сохранён:\n{report_path}')
                self.statusBar().showMessage(f'Отчёт сохранён: {os.path.basename(report_path)}', 5000)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Ошибка', f'Не удалось создать отчёт:\n{str(e)}')

    def choose_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Выбор папки с фото')
        if path:
            self.photosEdit.setText(path)

    def populate_table(self, filter_text: str = ""):
        self.table.setRowCount(0)
        if not self.grouped:
            return
        for sku, files in self.grouped.by_sku.items():
            if filter_text and filter_text.lower() not in sku.lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(sku))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(len(files))))
            names = ', '.join(os.path.basename(f.path) for f in files)
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(names))
        self.table.resizeColumnsToContents()
        self.table.sortItems(0, QtCore.Qt.AscendingOrder)

    def scan(self):
        folder = self.photosEdit.text().strip()
        pattern = self.patternEdit.text().strip()
        if not folder or not os.path.isdir(folder):
            QtWidgets.QMessageBox.warning(self, 'Ошибка', 'Укажите корректную папку с фото')
            return
        
        # Clear previous SKU data when scanning new folder
        self.skuData.clear()
        self._clear_sku_form()
        
        self.grouped = group_photos_flat(folder, pattern)
        self.populate_table(self.searchEdit.text().strip())
        if self.grouped.warnings:
            self.statusBar().showMessage('Предупреждения: ' + ' | '.join(self.grouped.warnings), 10000)
        else:
            self.statusBar().showMessage(f'Найдено SKU: {len(self.grouped.by_sku)}', 5000)

    def apply_filter(self, _text: str = ""):
        self.populate_table(self.searchEdit.text().strip())

    def on_table_selection_changed(self):
        items = self.table.selectedItems()
        if not items:
            self.clear_preview()
            self._clear_sku_form()
            return
        sku = self.table.item(items[0].row(), 0).text()
        self.update_preview_for_sku(sku)
        self._load_sku_data(sku)

    def clear_preview(self):
        while self.previewFlow.count():
            item = self.previewFlow.takeAt(0)
            if item:
                w = item.widget()
                if w:
                    w.setParent(None)

    def update_preview_for_sku(self, sku: str):
        self.clear_preview()
        if not self.grouped or sku not in self.grouped.by_sku:
            return
        files = self.grouped.by_sku[sku]
        count = 0
        for pf in files:
            if count >= 12:
                break
            lbl = QtWidgets.QLabel()
            lbl.setFixedSize(160, 160)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            pix = QtGui.QPixmap(pf.path)
            if not pix.isNull():
                lbl.setPixmap(pix.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                lbl.setText(os.path.basename(pf.path))
            lbl.setToolTip(os.path.basename(pf.path))
            self.previewFlow.addWidget(lbl)
            count += 1

    def start_upload(self):
        if not self.grouped or not self.grouped.by_sku:
            QtWidgets.QMessageBox.warning(self, 'Ошибка', 'Сначала выполните сканирование')
            return
        token = self.tokenEdit.text().strip()
        root = self.rootEdit.text().strip() or '/WB/Kruzhki'
        # map overwrite mode index -> string
        idx = max(0, self.overwriteMode.currentIndex())
        overwrite_mode = 'never' if idx == 0 else ('changed' if idx == 1 else 'always')
        max_photos = 6
        if self.profile:
            try:
                max_photos = int(self.profile.get('max_photos') or 6)
            except Exception:
                max_photos = 6
        if not token:
            QtWidgets.QMessageBox.warning(self, 'OAuth', 'Введите OAuth токен Яндекс.Диска')
            return

        # Disable controls while working
        for w in (self.scanBtn, self.startBtn, self.saveBtn, self.profileCombo):
            w.setEnabled(False)
        concurrency = int(self.concSlider.value())
        limit = int(self.limitSpin.value())
        self.worker = Worker(self.grouped, token, root, overwrite_mode, max_photos, concurrency=concurrency, limit=limit)
        self.worker.progress.connect(self.on_progress)
        self.worker.message.connect(self.on_message)
        self.worker.finished_ok.connect(self.on_finished)
        self.progress.setValue(0)
        self.worker.start()

    def on_progress(self, done, total):
        val = int(done * 100 / max(1, total))
        self.progress.setValue(val)
        self.statusBar().showMessage(f'Загружено {done}/{total}')

    def on_message(self, msg):
        # Append to log and status bar
        self.logEdit.appendPlainText(msg)
        self.statusBar().showMessage(msg, 5000)

    def on_finished(self, results):
        self.upload_results = results
        self.statusBar().showMessage('Загрузка завершена', 5000)
        self.progress.setValue(100)
        for w in (self.scanBtn, self.startBtn, self.saveBtn, self.profileCombo):
            w.setEnabled(True)
        QtWidgets.QMessageBox.information(self, 'Готово', 'Загрузка завершена')
        # Persist settings
        self.settings.setValue('photos_dir', self.photosEdit.text().strip())
        self.settings.setValue('profile_name', self.profileCombo.currentText())
        self.settings.setValue('overwrite_idx', self.overwriteMode.currentIndex())
        self.settings.setValue('concurrency', int(self.concSlider.value()))
        self.settings.setValue('limit', int(self.limitSpin.value()))

    def save_xlsx(self):
        if not self.grouped:
            QtWidgets.QMessageBox.warning(self, 'Ошибка', 'Нет данных для сохранения')
            return
        sep = ';'
        if self.profile:
            sep = self.profile.get('photo_sep') or ';'
        wb = create_wb_workbook()
        ws = wb.active

        for sku, files in self.grouped.by_sku.items():
            links = self.upload_results.get(sku, [])
            max_photos = 6
            if self.profile:
                try:
                    max_photos = int(self.profile.get('max_photos') or 6)
                except Exception:
                    max_photos = 6
            links = links[:max_photos]

            # Get user-entered data for this SKU
            sku_data = self.skuData.get(sku, {})
            user_name = sku_data.get('name', '').strip()
            user_price = sku_data.get('price', '').strip()
            user_color = sku_data.get('color', '').strip()
            user_volume = sku_data.get('volume', '').strip()
            user_material = sku_data.get('material', '').strip()
            user_gift = sku_data.get('gift', '').strip()
            user_pattern = sku_data.get('pattern', '').strip()
            user_complect = sku_data.get('complect', '').strip()

            # Use user data if available, otherwise fall back to profile/template
            title = user_name if user_name else sku
            if not user_name and self.profile:
                volume = (self.profile.get('defaults', {}) or {}).get('volume')
                data = {'sku': sku, 'volume': volume or ''}
                ttpl = self.profile.get('title_template')
                if ttpl:
                    try:
                        title = str(ttpl).format(**data)
                    except Exception:
                        title = str(ttpl)

            descr = ''
            if self.profile:
                volume = (self.profile.get('defaults', {}) or {}).get('volume')
                data = {'sku': sku, 'volume': volume or ''}
                dtpl = self.profile.get('description_template')
                if dtpl:
                    try:
                        descr = str(dtpl).format(**data)
                    except Exception:
                        descr = str(dtpl)

            # Determine final values (user input or profile default)
            final_color = user_color if user_color else (self.profile.get('color') if self.profile else '')
            final_price = user_price if user_price else str((self.profile.get('defaults', {}).get('price') if self.profile else '') or '')
            final_volume = user_volume if user_volume else str((self.profile.get('defaults', {}).get('volume') if self.profile else '') or '')
            final_material = user_material if user_material else (self.profile.get('composition') if self.profile else '')
            final_gift = user_gift if user_gift else ''
            final_pattern = user_pattern if user_pattern else ''
            final_complect = user_complect if user_complect else ''

            # Build row according to new WB template
            row = {
                'Группа': '',  # A - пустая, заполняется в WB
                'Артикул продавца': sku,  # B
                'Артикул WB': '',  # C - заполняется после создания
                'Наименование': title,  # D
                'Категория продавца': (self.profile.get('seller_category') if self.profile else 'Кружки'),  # E
                'Бренд': (self.profile.get('brand') if self.profile else ''),  # F
                'Описание': descr,  # G
                'Фото': sep.join(links),  # H
                'Вес с упаковкой (кг)': '',  # K - будет рассчитано из граммов
                'Цвет': final_color,  # M
                'Цена': final_price,  # O
                'Ставка НДС': (self.profile.get('vat') if self.profile else '20%'),  # P
                'Вес товара с упаковкой (г)': str((self.profile.get('package_weight_g') if self.profile else '') or ''),  # Q
                'Высота предмета': str((self.profile.get('dims', {}).get('item_H_cm') if self.profile else '') or ''),  # R
                'Высота упаковки': str((self.profile.get('dims', {}).get('H_cm') if self.profile else '') or ''),  # S
                'Длина упаковки': str((self.profile.get('dims', {}).get('L_cm') if self.profile else '') or ''),  # T
                'Ширина предмета': str((self.profile.get('dims', {}).get('item_W_cm') if self.profile else '') or ''),  # U
                'Ширина упаковки': str((self.profile.get('dims', {}).get('W_cm') if self.profile else '') or ''),  # V
                'Комплектация': final_complect,  # AD
                'Материал посуды': final_material,  # AE
                'Назначение подарка': final_gift,  # AG
                'Объем (мл)': final_volume,  # AI
                'Рисунок': final_pattern,  # AL
            }
            
            # Auto-calculate weight in kg from grams
            if self.profile and self.profile.get('calc_weight_kg_from_g') and self.profile.get('package_weight_g'):
                row['Вес с упаковкой (кг)'] = str(round(self.profile.get('package_weight_g') / 1000, 3))
            
            append_row(ws, row)

        # Ask for save path
        now = datetime.now().strftime('%Y%m%d-%H%M%S')
        default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'exports', f'wb_upload_{now}.xlsx'))
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Сохранить XLSX', default_path, 'Excel (*.xlsx)')
        save_path = path or default_path
        wb.save(save_path)
        QtWidgets.QMessageBox.information(self, 'Сохранено', save_path)
        # Persist settings
        self.settings.setValue('photos_dir', self.photosEdit.text().strip())
        self.settings.setValue('profile_name', self.profileCombo.currentText())

    def table_context_menu(self, pos):
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return
        row = idxs[0].row()
        sku = self.table.item(row, 0).text()
        m = QtWidgets.QMenu(self)
        actCopy = m.addAction('Копировать ссылки «Фото»')
        actOpen = m.addAction('Открыть папку SKU')
        action = m.exec_(self.table.viewport().mapToGlobal(pos))
        if action == actCopy:
            links = self.upload_results.get(sku, [])
            if links:
                QtWidgets.QApplication.clipboard().setText('\n'.join(links))
                self.statusBar().showMessage('Ссылки скопированы в буфер', 3000)
            else:
                self.statusBar().showMessage('Нет ссылок для копирования (выполните загрузку)', 5000)
        elif action == actOpen:
            self.open_folder_for_sku(sku)

    def open_current_folder(self):
        path = self.photosEdit.text().strip()
        if path and os.path.isdir(path):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def open_folder_for_sku(self, sku: str):
        if not self.grouped or sku not in self.grouped.by_sku:
            return
        files = self.grouped.by_sku[sku]
        if not files:
            return
        folder = os.path.dirname(files[0].path)
        if folder and os.path.isdir(folder):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    def check_for_updates(self):
        """Проверяет обновления вручную"""
        self.auto_updater.check_and_notify(silent=False)
    
    def show_settings(self):
        """Показывает окно настроек"""
        QtWidgets.QMessageBox.information(
            self,
            "Настройки",
            "Окно настроек будет добавлено в следующей версии.\n\n"
            "Пока что настройки можно изменить через Мастер настройки."
        )
    
    def show_about(self):
        """Показывает информацию о программе"""
        try:
            version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "version.txt")
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
            else:
                version = "1.0.0"
        except Exception:
            version = "1.0.0"
        
        QtWidgets.QMessageBox.about(
            self,
            "О программе WB Auto",
            f"""
<h3>WB Auto v{version}</h3>
<p>Автоматизация загрузки товаров на Wildberries</p>

<p><b>Возможности:</b></p>
<ul>
<li>Автоматическое распознавание фотографий товаров</li>
<li>Загрузка фото в Яндекс.Диск</li>
<li>Генерация Excel файлов для WB</li>
<li>Автоматическое обновление</li>
</ul>

<p><b>Разработчик:</b> baltabekpro</p>
<p><b>Репозиторий:</b> <a href="https://github.com/baltabekpro/wb_auto">GitHub</a></p>

<p><i>© 2025 WB Auto. Все права защищены.</i></p>
            """.strip()
        )
    
    def showEvent(self, event):
        """Переопределяем событие показа окна для проверки обновлений при запуске"""
        super().showEvent(event)
        
        # Проверяем обновления при первом показе окна (автоматически, без уведомления если нет обновлений)
        if not hasattr(self, '_updates_checked'):
            self._updates_checked = True
            QtCore.QTimer.singleShot(2000, lambda: self.auto_updater.check_and_notify(silent=True))


def main():
    app = QtWidgets.QApplication(sys.argv)
    
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
    
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
