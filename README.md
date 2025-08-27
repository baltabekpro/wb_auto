# Модуль подготовки карточек «Кружки» для Wildberries

Этот прототип:
- группирует фото из плоской папки по SKU по паттерну `^(?P<sku>.+)\.(?P<n>\d+)\.(?P<ext>jpe?g|png)$`;
- загружает их в Яндекс.Диск, публикует и получает прямые ссылки;
- генерирует XLSX по колонкам шаблона.

## Установка и запуск (Windows)
1) Установите Python 3.10+.
2) Установите зависимости:
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -U pip
pip install -r requirements.txt
```
3) Запустите приложение:
```bash
python src/app.py
```

## Сборка .exe
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --name wb_kruzhki --add-data "src/templates;templates" src/app.py
```

## Профили
См. пример `profiles/sample_profile.json`. Выберите профиль в GUI.

## Импорт
Файл CSV/XLSX вида: `sku,price,barcode,color,name` (пока импорт не подключён в GUI — задел на следующую итерацию).

## Ограничения прототипа
- Импорт индивидуальных полей и предпросмотр порядка/drag&drop — в следующей версии.
- Идемпотентность: пропуск совпавших по имени и размеру, либо перезапись.
- Хранение токена — через Windows Credential Manager (keyring).
