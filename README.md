# Paper First

Telegram Mini App для проведения бэктеста торговых систем.

## Стек

- Backend API: FastAPI
- Bot: aiogram
- Worker: RQ + Redis
- DB: PostgreSQL
- Frontend: React + Vite + TypeScript
- Market data: Coinbase Exchange candles
- Strategy format: JSON `StrategySpec`

## Окружение

Для Python команд нужен Python 3.12+. Создайте виртуальное окружение и установите backend зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Frontend зависимости установите по lock файлу:

```bash
npm --prefix frontend ci
```

## Локальный запуск

```bash
cp .env.example .env
```

Нужно заполнить токен Telegram бота и api ключ Gemini

Запуск приложения:

```bash
python3 start.py --all
```

Backend будет доступен на `http://localhost:8000`, Mini App на `http://localhost:5173`.

Для кнопки в Mini App нужен публичный HTTPS адрес frontend. Запустите Cloudflare Quick Tunnel:

```bash
cloudflared tunnel --url http://localhost:5173
```

Укажите адрес в `.env` как `PAPERFIRST_TELEGRAM_WEB_APP_URL`. Команда `/start` отправит inline-кнопку `Open Mini App` с этим адресом.

Чтобы применить URL, пересоздайте контейнер бота:

```bash
docker compose --profile bot up --detach --force-recreate bot
```

## Mini App

Mini App принимает источник стратегии файлом: текст, JSON, PDF или изображение. Кнопка `Load strategy` вызывает `POST /api/strategy/import` и загружает извлеченный `StrategySpec`.

Кнопка `Run audit` запускает `POST /api/backtests/run`, затем опрашивает статус job и показывает verdict, метрики, equity curve, предупреждения и последние сделки.

## API

- `GET /api/health`
- `POST /api/strategy/validate`
- `POST /api/strategy/import`
- `POST /api/backtests/run`
- `GET /api/backtests/{job_id}`

`POST /api/strategy/import` принимает `multipart/form-data` с полями `text` и/или `file` и требует `PAPERFIRST_GEMINI_API_KEY`. Текстовые файлы и JSON объединяются с `text`; PDF и изображения передаются в Gemini inline. Лимит inline файла: 12 MB. Gemini должен вернуть JSON со всеми группами сигналов `entry.all`, `entry.any`, `exit.all`, `exit.any` и обязательными risk полями; `take_profit_pct` опционален.

`POST /api/backtests/run` создает job в Postgres и кладет расчет в Redis. Отчет забирается через `GET /api/backtests/{job_id}`. Если `candles=[]` и `use_demo_data=true`, worker загружает последние live свечи с Coinbase. Поддерживаются таймфреймы `1m`, `5m`, `15m`, `1h`, `6h`, `1d`; для остальных нужно передать `candles` явно.

## Проверки

Backend тесты:

```bash
python3 -m pytest backend/tests
```

Тесты Gemini лежат отдельно и по умолчанию пропускаются:

```bash
RUN_LIVE_LLM_TESTS=1 PAPERFIRST_GEMINI_API_KEY=... python3 -m pytest backend/tests/llm_test
```

Frontend сборка:

```bash
cd frontend
npm run build
```