# Демо-магазин

Стек:
- FastAPI: POST `/api/orders` записывает и возвращает заказ, GET `/api/orders` читает историю
- HTML/CSS/JS: каталог, корзина, имя и телефон, список заказов
- PostgreSQL 17, TCP-подключение через `psycopg`

Заказ и его позиции хранятся в PostgreSQL и остаются после перезапуска приложения


Фронтенд получает каталог через HTTP API. Корзина временно хранится в `localStorage`; оформленные заказы – только в PostgreSQL. Сервер пересчитывает цену, сохраняет снимки названия и цены товара и записывает заказ одной транзакцией. Приложение не хранит серверные сессии в памяти.

## Быстрый запуск на Windows

Нужны **Windows CPython 3.12 x64**. Выполняйте команды в PowerShell из папки этого README.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -c "import sysconfig; print(sysconfig.get_platform())"
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.local_postgres setup
.\start.ps1
```

Если PowerShell блокирует запуск `.ps1`, можно запускать сервер напрямую:

```powershell
$env:APP_MODE = 'local'
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Откройте **http://127.0.0.1:8000**. Документация API: http://127.0.0.1:8000/docs. Проверка подключения: http://127.0.0.1:8000/api/health.

Помощник `scripts.local_postgres setup` загружает официальный архив EDB PostgreSQL 17.11 (~363 МБ), проверяет опубликованную SHA-256, распаковывает сервер в `.tools` и создает **отдельный кластер** в `.runtime/pgdata`. Он слушает только `127.0.0.1:55432`, использует SCRAM-пароли и не меняет существующий PostgreSQL в `Program Files`. Создаются администратор кластера `miniapp_admin`, пользователь приложения `teploe_zerno` без прав суперпользователя и БД `teploe_zerno`. Пароли генерируются автоматически; строка приложения записывается в `.env`, данные администратора – в игнорируемый `.runtime/postgres.json`.

Повторный `setup` сохраняет данные и пароли. После перезагрузки компьютера:

```powershell
.\.venv\Scripts\python.exe -m scripts.local_postgres start
.\start.ps1
```

Остановка сервера приложения: `Ctrl+C`. Остановка и проверка отдельного PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m scripts.local_postgres status
.\.venv\Scripts\python.exe -m scripts.local_postgres stop
```

Логи БД: `.runtime/postgres.log`. Не удаляйте `.runtime/pgdata`: там сохраненные заказы. Не публикуйте `.env`, `.runtime` и `.tools`.

## Открытие в Telegram

1. Создайте **нового** бота у [@BotFather](https://t.me/BotFather) командой `/newbot`. Сохраните токен в локальный `.env` как `BOT_TOKEN=...`. Токен на фронтенд не передается.
2. Остановите сервер приложения и запустите режим Telegram:

   ```powershell
   .\start.ps1 -Mode telegram
   ```

3. В другом PowerShell установите официальный клиент туннеля:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.install_cloudflared
   .\start-tunnel.ps1
   ```

4. Скопируйте выданный адрес `https://....trycloudflare.com` и выполните в третьем терминале:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.configure_telegram --url https://YOUR-ADDRESS.trycloudflare.com
   ```

5. Откройте нового бота в Telegram, нажмите **Start**, затем кнопку меню **«Открыть магазин»**.  


## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/products` | Каталог; `price` в копейках |
| POST | `/api/orders` | Сохранить заказ и вернуть его, HTTP 201 |
| GET | `/api/orders` | До 100 последних собственных заказов |
| GET | `/api/orders/{id}` | Собственный заказ с позициями, чужой возвращает 404 |
| GET | `/api/health` | Проверка БД; HTTP 503 при недоступности |
| GET | `/api/config` | Только текущий режим, без секретов |

Пример тела заказа:

```json
{"name":"Учебный покупатель","phone":"+7 999 000-00-00","items":[{"product_id":1,"quantity":2}]}
```

Сумму и цены передавать нельзя. Количество: целое 1–99; пустой заказ отклоняется. При ошибке валидации – 422, авторизации – 401, недопустимом доступе в локальном режиме – 403. Все даты хранятся с часовым поясом, интерфейс показывает их в местном времени пользователя.
