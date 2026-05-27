# Logistics PDF Processor

Веб-приложение для загрузки PDF с предварительной информацией о грузах, извлечения полей и отправки результата в Google Sheets через Google Apps Script webhook.

## Возможности

- JWT-авторизация на 8 часов.
- SQLite база с пользователями и журналом обработок.
- Автоматическое создание первого администратора: `admin` / `admin123`.
- Загрузка PDF без постоянного хранения файла на сервере.
- Извлечение полей через `pdfplumber` и регулярные выражения.
- Редактирование всех извлечённых полей перед отправкой.
- Админка для пользователей и истории обработок.

## Запуск

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Откройте `http://localhost:8000`.

## Настройки

Переменные окружения:

```bash
export JWT_SECRET_KEY="replace-with-long-random-secret"
export GOOGLE_SHEETS_WEBHOOK_URL="https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
export CORS_ORIGINS="http://localhost:8000,https://your-name.github.io"
```

Если `GOOGLE_SHEETS_WEBHOOK_URL` не задан, приложение позволит извлекать и редактировать данные, но отправка в Google Sheets вернёт `success: false`.

## Google Apps Script

В Google Sheets откройте `Расширения -> Apps Script`, вставьте код и разверните как веб-приложение с доступом `Все`.

```javascript
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);

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

## Структура

```text
backend/
  main.py
  auth.py
  database.py
  pdf_parser.py
  sheets.py
  requirements.txt
frontend/
  index.html
  work.html
  admin.html
  app.js
  style.css
```
