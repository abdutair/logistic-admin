# SKILL.md — Логистическая система обработки PDF

## Что нужно построить

Веб-приложение для логистической компании. Сотрудники загружают PDF-документы (предварительная информация о грузах), система автоматически извлекает данные и отправляет в Google Sheets.

---

## Стек технологий

### Бэкенд
- **Python 3.11+**
- **FastAPI** — основной сервер
- **pdfplumber** — извлечение текста из PDF
- **python-multipart** — приём файлов
- **httpx** — отправка данных в Google Apps Script
- **python-jose** — JWT токены для авторизации
- **passlib** — хэширование паролей
- **sqlite3** — база данных (встроена в Python, ничего не надо устанавливать)

### Фронтенд
- **Vanilla HTML + CSS + JavaScript** (без фреймворков)
- Размещается на **GitHub Pages** или как статика через FastAPI

### Интеграции
- **Google Sheets** — через Google Apps Script webhook (POST запрос)

---

## Структура проекта

```
logistics-app/
├── backend/
│   ├── main.py              # FastAPI приложение
│   ├── auth.py              # Авторизация, JWT
│   ├── database.py          # SQLite, работа с пользователями
│   ├── pdf_parser.py        # Извлечение данных из PDF
│   ├── sheets.py            # Отправка в Google Sheets
│   └── requirements.txt     # Зависимости
├── frontend/
│   ├── index.html           # Логин
│   ├── work.html            # Рабочий экран исполнителя
│   ├── admin.html           # Админка
│   └── style.css            # Стили
└── README.md
```

---

## База данных (SQLite)

### Таблица users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    login TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',  -- 'admin' или 'user'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Таблица logs (история обработки)
```sql
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    filename TEXT,
    extracted_data TEXT,  -- JSON строка
    sent_to_sheets BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## API эндпоинты (FastAPI)

### Авторизация
```
POST /auth/login
  body: { login, password }
  return: { access_token, role, name }

POST /auth/logout
  headers: Bearer token
```

### Работа с PDF
```
POST /pdf/upload
  headers: Bearer token
  body: multipart/form-data, file=<PDF файл>
  return: {
    doc_number, doc_date,
    sender, sender_address,
    receiver, receiver_address,
    cargo_description, weight_kg,
    quantity, route,
    carrier, notes
  }

POST /pdf/send-to-sheets
  headers: Bearer token
  body: { extracted_data: {...}, filename }
  return: { success: true }
```

### Администрирование (только role=admin)
```
GET  /admin/users
  return: [{ id, name, login, role, created_at }]

POST /admin/users
  body: { name, login, password, role }
  return: { id, name, login, role }

DELETE /admin/users/{id}
  return: { success: true }

GET  /admin/logs
  return: [{ id, user_name, filename, sent_to_sheets, created_at }]
```

---

## Логика извлечения PDF (pdf_parser.py)

Использовать **pdfplumber** для извлечения всего текста. Затем через **регулярные выражения (regex)** искать поля.

```python
import pdfplumber
import re

def extract_fields(pdf_path: str) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() or ""

    return {
        "doc_number": find_field(full_text, [
            r"(?:№|No|Number|Номер)[:\s#]+([A-Z0-9\-/]+)",
            r"(?:AWB|B/L|CMR|Invoice)[:\s#]*([A-Z0-9\-/]+)"
        ]),
        "doc_date": find_field(full_text, [
            r"(?:Date|Дата)[:\s]+(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})",
            r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})"
        ]),
        "sender": find_field(full_text, [
            r"(?:Shipper|Sender|Отправитель|От кого)[:\s]+([^\n]+)",
            r"(?:From|Грузоотправитель)[:\s]+([^\n]+)"
        ]),
        "sender_address": find_field(full_text, [
            r"(?:Shipper address|Адрес отправителя)[:\s]+([^\n]+)"
        ]),
        "receiver": find_field(full_text, [
            r"(?:Consignee|Receiver|Получатель|Кому)[:\s]+([^\n]+)",
            r"(?:To|Грузополучатель)[:\s]+([^\n]+)"
        ]),
        "receiver_address": find_field(full_text, [
            r"(?:Consignee address|Адрес получателя)[:\s]+([^\n]+)"
        ]),
        "cargo_description": find_field(full_text, [
            r"(?:Description|Описание|Товар|Goods)[:\s]+([^\n]+)"
        ]),
        "weight_kg": find_field(full_text, [
            r"(?:Weight|Вес)[:\s]+([\d.,]+)\s*(?:kg|кг)",
            r"([\d.,]+)\s*(?:kg|кг)"
        ]),
        "quantity": find_field(full_text, [
            r"(?:Quantity|Количество|Pcs|Мест)[:\s]+([\d]+)"
        ]),
        "route": find_field(full_text, [
            r"(?:From|Откуда)[:\s]+([^\n]+).*?(?:To|Куда)[:\s]+([^\n]+)",
            r"(?:Route|Маршрут)[:\s]+([^\n]+)"
        ]),
        "carrier": find_field(full_text, [
            r"(?:Carrier|Перевозчик)[:\s]+([^\n]+)"
        ]),
        "notes": find_field(full_text, [
            r"(?:Remarks|Notes|Примечания|Особые отметки)[:\s]+([^\n]+)"
        ]),
        "raw_text": full_text  # сырой текст на случай если regex не сработал
    }

def find_field(text: str, patterns: list) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""
```

---

## Отправка в Google Sheets (sheets.py)

```python
import httpx

WEBHOOK_URL = "https://script.google.com/macros/s/ВАШ_СКРИПТ_ID/exec"

async def send_to_sheets(data: dict, user_name: str, filename: str):
    payload = {
        "timestamp": data.get("timestamp"),
        "user": user_name,
        "filename": filename,
        "doc_number": data.get("doc_number"),
        "doc_date": data.get("doc_date"),
        "sender": data.get("sender"),
        "sender_address": data.get("sender_address"),
        "receiver": data.get("receiver"),
        "receiver_address": data.get("receiver_address"),
        "cargo_description": data.get("cargo_description"),
        "weight_kg": data.get("weight_kg"),
        "quantity": data.get("quantity"),
        "route": data.get("route"),
        "carrier": data.get("carrier"),
        "notes": data.get("notes"),
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(WEBHOOK_URL, json=payload)
        return response.status_code == 200
```

---

## Google Apps Script (вставить в Google Sheets)

Открыть Google Sheets → Расширения → Apps Script → вставить этот код:

```javascript
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);

  // Заголовки (только если таблица пустая)
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "Дата/время", "Исполнитель", "Файл",
      "№ документа", "Дата документа",
      "Отправитель", "Адрес отправителя",
      "Получатель", "Адрес получателя",
      "Описание груза", "Вес (кг)", "Количество",
      "Маршрут", "Перевозчик", "Примечания"
    ]);
  }

  sheet.appendRow([
    data.timestamp, data.user, data.filename,
    data.doc_number, data.doc_date,
    data.sender, data.sender_address,
    data.receiver, data.receiver_address,
    data.cargo_description, data.weight_kg, data.quantity,
    data.route, data.carrier, data.notes
  ]);

  return ContentService
    .createTextOutput(JSON.stringify({ result: "success" }))
    .setMimeType(ContentService.MimeType.JSON);
}
```

После вставки: **Развернуть → Новое развёртывание → Веб-приложение → Доступ: Все** → скопировать URL и вставить в WEBHOOK_URL в sheets.py

---

## Фронтенд — рабочий экран (work.html)

### Логика JavaScript:
1. При загрузке страницы проверить JWT токен (если нет — редирект на login)
2. Drag & drop зона для PDF слева
3. При сбросе файла — отправить на `POST /pdf/upload`
4. Показать извлечённые поля справа (все редактируемые)
5. Кнопка "Отправить в Google Sheets" → `POST /pdf/send-to-sheets`
6. Показать статус отправки

---

## Фронтенд — админка (admin.html)

### Логика:
1. Проверить что role === 'admin', иначе редирект
2. Таблица пользователей с кнопками удаления
3. Форма добавления нового пользователя
4. Таблица логов (кто, когда, какой файл обработал)

---

## Авторизация

- JWT токен, срок жизни 8 часов
- Хранить в localStorage браузера
- При каждом запросе передавать в заголовке: `Authorization: Bearer <token>`
- Эндпоинты с пометкой "только admin" проверять роль из токена

---

## Запуск локально

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Фронтенд открывать через `http://localhost:8000`

---

## requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.0
pdfplumber==0.11.0
python-multipart==0.0.9
httpx==0.27.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

---

## Важные детали

- PDF файлы НЕ хранить на сервере — читать и сразу удалять
- Пароли хранить только в виде bcrypt хэша, никогда в открытом виде
- CORS настроить для домена GitHub Pages
- Первый пользователь admin создаётся при первом запуске автоматически (login: admin, password: admin123 — сменить сразу)
- Все поля после извлечения должны быть редактируемыми на фронтенде

---

## Что НЕ нужно делать

- Не использовать Claude API или любой другой внешний ИИ
- Не использовать React, Vue или другие фреймворки
- Не использовать PostgreSQL или другие тяжёлые базы данных — только SQLite
- Не хранить PDF файлы — только читать и удалять