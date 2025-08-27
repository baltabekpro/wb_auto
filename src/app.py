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
        self._build_ui()
        self._load_profiles()
        self._apply_styles()

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
        self.photosEdit = DropLineEdit()
        self.photosEdit.setPlaceholderText('Путь к папке с фото')
        btnChoose = QtWidgets.QPushButton('Обзор…')
        btnChoose.clicked.connect(self.choose_folder)
        hPhotos = QtWidgets.QHBoxLayout()
        hPhotos.addWidget(self.photosEdit)
        hPhotos.addWidget(btnChoose)
        self.patternEdit = QtWidgets.QLineEdit(r"^(?P<sku>.+)\.(?P<n>\d+)\.(?P<ext>jpe?g|png)$")
        self.patternEdit.setClearButtonEnabled(True)
        f1.addRow('Профиль:', self.profileCombo)
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

        btns = QtWidgets.QHBoxLayout()
        self.scanBtn = QtWidgets.QPushButton('Сканировать')
        self.startBtn = QtWidgets.QPushButton('Загрузить в Яндекс.Диск')
        self.saveBtn = QtWidgets.QPushButton('Сформировать XLSX')
        self.openFolderBtn = QtWidgets.QPushButton('Открыть папку')
        btns.addWidget(self.scanBtn)
        btns.addWidget(self.startBtn)
        btns.addWidget(self.saveBtn)
        btns.addWidget(self.openFolderBtn)

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

        # Right — preview thumbnails in a scroll area
        right = QtWidgets.QWidget()
        rightLayout = QtWidgets.QVBoxLayout(right)
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
        tb.addAction(actScan)
        tb.addAction(actStart)
        tb.addAction(actSave)
        tb.addSeparator()
        tb.addAction(actOpen)
        actLog = QtWidgets.QAction('Лог', self)
        actLog.setCheckable(True)
        actLog.toggled.connect(self.logDock.setVisible)
        tb.addSeparator()
        tb.addAction(actLog)

        # Signals
        self.scanBtn.clicked.connect(self.scan)
        self.startBtn.clicked.connect(self.start_upload)
        self.saveBtn.clicked.connect(self.save_xlsx)
        self.openFolderBtn.clicked.connect(self.open_current_folder)
        self.profileCombo.currentIndexChanged.connect(self.profile_changed)
        self.searchEdit.textChanged.connect(self.apply_filter)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        actScan.triggered.connect(self.scan)
        actStart.triggered.connect(self.start_upload)
        actSave.triggered.connect(self.save_xlsx)
        actOpen.triggered.connect(self.open_current_folder)
        # Context menu for table
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_context_menu)
        btnEye.toggled.connect(self._toggle_token_visibility)
        btnClearToken.clicked.connect(lambda: self.tokenEdit.clear())
        btnCopyLog.clicked.connect(self._copy_log)

        # Restore last settings
        self.settings = QtCore.QSettings('wb_auto', 'kruzhki')
        last_folder = self.settings.value('photos_dir', '')
        self.photosEdit.setText(last_folder)
        last_profile = self.settings.value('profile_name', '')
        idx = self.profileCombo.findText(last_profile)
        if idx >= 0:
            self.profileCombo.setCurrentIndex(idx)
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
            QPushButton { background-color: #4a90e2; color: white; border: none; padding: 8px 14px; border-radius: 6px; }
            QPushButton:hover { background-color: #5aa0f2; }
            QPushButton:disabled { background-color: #666; }
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

    def _load_profiles(self):
        profiles_path = os.path.join(os.path.dirname(__file__), '..', 'profiles')
        self.profile_files = list_profiles(profiles_path)
        self.profileCombo.clear()
        for name in self.profile_files.keys():
            self.profileCombo.addItem(name)
        if self.profileCombo.count() > 0:
            self.profileCombo.setCurrentIndex(0)
            self.profile_changed(0)

    def profile_changed(self, idx):
        name = self.profileCombo.currentText()
        if name and name in self.profile_files:
            self.profile = load_profile(self.profile_files[name])
            root = self.profile.get('yadisk_root') or '/WB/Kruzhki'
            self.rootEdit.setText(root)

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
            return
        sku = self.table.item(items[0].row(), 0).text()
        self.update_preview_for_sku(sku)

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

            title = sku
            descr = ''
            if self.profile:
                volume = (self.profile.get('defaults', {}) or {}).get('volume')
                data = {'sku': sku, 'volume': volume or ''}
                ttpl = self.profile.get('title_template')
                dtpl = self.profile.get('description_template')
                if ttpl:
                    try:
                        title = str(ttpl).format(**data)
                    except Exception:
                        title = str(ttpl)
                if dtpl:
                    try:
                        descr = str(dtpl).format(**data)
                    except Exception:
                        descr = str(dtpl)

            row = {
                'Артикул продавца': sku,
                'Наименование': title,
                'Бренд': (self.profile.get('brand') if self.profile else ''),
                'Описание': descr,
                'Фото': sep.join(links),
                'Видео': '',
                'КИЗ': '',
                'Пол': (self.profile.get('gender') if self.profile else ''),
                'Состав': (self.profile.get('composition') if self.profile else ''),
                'Цвет': (self.profile.get('color') if self.profile else ''),
                'Баркод': '',
                'Размер': (self.profile.get('defaults', {}).get('size') if self.profile else ''),
                'Рос. размер': (self.profile.get('defaults', {}).get('rus_size') if self.profile else ''),
                'Цена': str((self.profile.get('defaults', {}).get('price') if self.profile else '') or ''),
                'Ставка НДС': (self.profile.get('vat') if self.profile else ''),
                'Вес с упаковкой (г)': str((self.profile.get('package_weight_g') if self.profile else '') or ''),
                'Высота упаковки (см)': str((self.profile.get('dims', {}).get('H_cm') if self.profile else '') or ''),
                'Длина упаковки (см)': str((self.profile.get('dims', {}).get('L_cm') if self.profile else '') or ''),
                'Ширина упаковки (см)': str((self.profile.get('dims', {}).get('W_cm') if self.profile else '') or ''),
                'Возрастные ограничения (18+)': (self.profile.get('age18') if self.profile else ''),
                'Категория продавца': (self.profile.get('seller_category') if self.profile else ''),
            }
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


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
