from typing import Dict, List
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

WB_HEADERS = [
    "Артикул продавца","Наименование","Бренд","Описание","Фото","Видео","КИЗ","Пол","Состав","Цвет","Баркод","Размер","Рос. размер","Цена","Ставка НДС","Вес с упаковкой (г)","Высота упаковки (см)","Длина упаковки (см)","Ширина упаковки (см)","Дата окончания действия декларации","Дата регистрации декларации","Номер декларации соответствия","Номер сертификата соответствия","Возрастные ограничения (18+)","Группа","Артикул WB","Категория продавца","Вес с упаковкой (кг)"
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
