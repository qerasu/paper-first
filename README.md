# Paper First

Telegram Mini App и backend для аудита торговых стратегий до реального депозита.

Идея MVP: пользователь загружает или описывает торговую стратегию, Paper First приводит ее к `StrategySpec`, запускает честный backtest с комиссиями и слиппеджем и показывает отчет с вердиктом `reject`, `unstable`, `research` или `paper`.

Интерфейс Mini App и сообщения Telegram-бота отображаются на английском языке.

## Стек

- Backend API: FastAPI
- Bot: aiogram
- Worker: RQ + Redis
- DB: PostgreSQL
- Frontend: React + Vite + TypeScript
- Strategy format: JSON `StrategySpec`, без исполнения произвольного Python

## Локальный запуск

Сначала скопируйте пример переменных. Заполните токен бота, если нужен Telegram polling, и `PAPERFIRST_GEMINI_API_KEY`, если нужен импорт стратегии через Gemini:

```bash
cp .env.example .env
```

Инфраструктура и приложение:

```bash
docker compose up postgres redis api worker frontend
```

То же самое через helper:

```bash
python3 start.py
```

Запуск приложения вместе с Telegram-ботом:

```bash
python3 start.py --bot
```

Запуск всех сервисов, включая Telegram-бота:

```bash
python3 start.py --all
```

Bot запускается отдельным профилем:

```bash
docker compose --profile bot up bot
```

Backend будет на `http://localhost:8000`, Mini App на `http://localhost:5173`.

В Telegram бот отвечает на `/start`, показывает reply-кнопку `Check strategy` и регистрирует команду `/check_strategy` в меню бота. Кнопка Mini App появляется только для публичного `https` URL.

Telegram разрешает Web App кнопки только с публичным `https` URL. Если в `PAPERFIRST_TELEGRAM_WEB_APP_URL` стоит `http://localhost:5173`, бот ответит обычным сообщением и не будет открывать Mini App внутри Telegram. Для полноценной кнопки нужен tunnel или домен:

```env
PAPERFIRST_TELEGRAM_WEB_APP_URL=https://your-public-url.example
```

Проект остается local-first: backend, worker, Redis и Postgres живут локально во время разработки. Render нужен как простой стабильный `https`-адрес для frontend, чтобы один раз поставить его в BotFather и `PAPERFIRST_TELEGRAM_WEB_APP_URL`, а не поднимать новый tunnel только для UI.

Мини-гайд для Render Static Site:

1. Запушьте репозиторий в GitHub.
2. В Render выберите `New` -> `Blueprint` и подключите репозиторий.
3. Render возьмет настройки из `render.yaml` и создаст `paper-first-tma`.
4. После деплоя скопируйте URL вида `https://paper-first-tma.onrender.com`.
5. Поставьте этот URL в BotFather и в локальный `.env`:

```env
PAPERFIRST_TELEGRAM_WEB_APP_URL=https://paper-first-tma.onrender.com
```

После этого локальный бот можно запускать без frontend-туннеля:

```bash
python3 start.py --all
```

Render-хостинг в этом варианте отдает только frontend. Для рабочих API-запросов из Mini App backend тоже должен быть доступен по публичному `https` URL: через tunnel, отдельный deploy или другой временный адрес. Укажите его через `VITE_API_BASE_URL=https://your-api.example/api`.

Для локальной проверки внутри Telegram нужны публичные HTTPS URL для frontend и API. Например, через tunnel:

```env
PAPERFIRST_TELEGRAM_WEB_APP_URL=https://frontend-tunnel.example
PAPERFIRST_BACKEND_CORS_ORIGINS=["https://frontend-tunnel.example"]
VITE_API_BASE_URL=https://api-tunnel.example/api
```

После изменения URL перезапустите сервисы:

```bash
python3 start.py --all
```

## Mini App

Mini App принимает источник стратегии файлом: текст, JSON, PDF или изображение. Кнопка `Load strategy` вызывает `POST /api/strategy/import` и загружает извлеченный `StrategySpec`.

Кнопка `Run audit` запускает `POST /api/backtests/run` с `use_demo_data=true` после успешной загрузки стратегии, затем опрашивает статус job и показывает verdict, метрики, equity curve, предупреждения и последние сделки.

## API

- `GET /api/health`
- `GET /api/strategy/sample`
- `POST /api/strategy/validate`
- `POST /api/strategy/import`
- `POST /api/backtests/run`
- `GET /api/backtests/{job_id}`

`POST /api/strategy/import` принимает `multipart/form-data` с полями `text` и/или `file` и требует `PAPERFIRST_GEMINI_API_KEY`. Текстовые файлы и JSON объединяются с `text`; PDF и изображения передаются в Gemini inline. Лимит inline-файла: 12 MB. Gemini должен вернуть JSON со всеми группами сигналов `entry.all`, `entry.any`, `exit.all`, `exit.any` и всеми risk-полями.

`POST /api/backtests/run` создает job в Postgres и кладет расчет в Redis/RQ. Отчет забирается через `GET /api/backtests/{job_id}`. Если `candles=[]` и `use_demo_data=true`, worker использует синтетическую историю свечей.

## Проверки

После установки зависимостей из `requirements.txt` backend-тесты запускаются так:

```bash
python3 -m pytest backend/tests
```

Live-проверки Gemini лежат отдельно и по умолчанию пропускаются:

```bash
RUN_LIVE_LLM_TESTS=1 PAPERFIRST_GEMINI_API_KEY=... python3 -m pytest backend/tests/llm_test
```

Frontend production-сборка:

```bash
cd frontend
npm run build
```

## StrategySpec

Пример стратегии:

```json
{
  "name": "RSI trend filter",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "entry": {
    "all": [
      { "left": "close", "operator": ">", "right": "sma_20" },
      { "left": "rsi_14", "operator": "<", "right": 62 }
    ]
  },
  "exit": {
    "any": [
      { "left": "close", "operator": "<", "right": "sma_20" },
      { "left": "rsi_14", "operator": ">", "right": 72 }
    ]
  },
  "risk": {
    "initial_capital": 1000,
    "position_size_pct": 25,
    "stop_loss_pct": 4,
    "take_profit_pct": 9,
    "fee_bps": 8,
    "slippage_bps": 5,
    "max_drawdown_pct": 20
  }
}
```

`entry` и `exit` используют группы условий: все условия из `all` должны выполниться, а из `any` достаточно одного. Если `any` пустой, проверяются только условия из `all`.

Поддерживаемые поля условий: `open`, `high`, `low`, `close`, `volume`, `equity`, `sma_N`, `ema_N`, `rsi_N`. Поддерживаемые операторы: `>`, `>=`, `<`, `<=`, `==`, `!=`.

Backtest учитывает `position_size_pct`, `stop_loss_pct`, `take_profit_pct`, `fee_bps`, `slippage_bps` и `max_drawdown_pct`. Вердикт строится по прибыльности, drawdown, profit factor и числу сделок.
