from typing import Dict, List
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

# Новый шаблон WB с правильным маппингом колонок
WB_HEADERS = [
    "Группа",                           # A
    "Артикул продавца",                 # B
    "Артикул WB",                       # C
    "Наименование",                     # D
    "Категория продавца",               # E
    "Бренд",                           # F
    "Описание",                        # G
    "Фото",                            # H
    "",                                # I - пустая
    "",                                # J - пустая
    "Вес с упаковкой (кг)",            # K
    "",                                # L - пустая
    "Цвет",                            # M
    "",                                # N - пустая
    "Цена",                            # O
    "Ставка НДС",                      # P
    "Вес товара с упаковкой (г)",      # Q
    "Высота предмета",                 # R
    "Высота упаковки",                 # S
    "Длина упаковки",                  # T
    "Ширина предмета",                 # U
    "Ширина упаковки",                 # V
    "",                                # W - пустая
    "",                                # X - пустая
    "",                                # Y - пустая
    "",                                # Z - пустая
    "",                                # AA - пустая
    "",                                # AB - пустая
    "",                                # AC - пустая
    "Комплектация",                    # AD
    "Материал посуды",                 # AE
    "",                                # AF - пустая
    "Назначение подарка",              # AG
    "",                                # AH - пустая
    "Объем (мл)",                      # AI
    "",                                # AJ - пустая
    "",                                # AK - пустая
    "Рисунок",                         # AL
]


def create_wb_workbook() -> Workbook:
    wb = Workbook()
    ws: Worksheet = wb.active
    ws.title = "WB Upload"
    ws.append(WB_HEADERS)
    return wb


def append_row(ws: Worksheet, row: Dict[str, str]):
    vals: List[str] = []
    for h in WB_HEADERS:
        vals.append(row.get(h, ""))
    ws.append(vals)
