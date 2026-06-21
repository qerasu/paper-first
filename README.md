# Paper First

Telegram Mini App и backend для аудита торговых стратегий до реального депозита.

Идея MVP: пользователь описывает стратегию в строгом JSON/DSL, запускает честный backtest с комиссиями и слиппеджем, получает отчет с вердиктом `reject`, `unstable`, `research` или `paper`.

Интерфейс Mini App и сообщения Telegram-бота отображаются на английском языке.

## Стек

- Backend API: FastAPI
- Bot: aiogram
- Worker: RQ + Redis
- DB: PostgreSQL
- Frontend: React + Vite + TypeScript
- Strategy format: JSON `StrategySpec`, без исполнения произвольного Python

## Локальный запуск

Сначала скопируйте пример переменных и заполните токен бота значением (только если нужен Telegram polling):

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

Telegram разрешает Web App кнопки только с публичным `https` URL. Если в `PAPERFIRST_TELEGRAM_WEB_APP_URL` стоит `http://localhost:5173`, бот ответит обычным сообщением и не будет открывать Mini App внутри Telegram. Для полноценной кнопки нужен tunnel или домен:

```env
PAPERFIRST_TELEGRAM_WEB_APP_URL=https://your-public-url.example
```

## Render URL для Telegram Mini App

Если нужен только стабильный `https` домен для Mini App, можно задеплоить frontend как Render Static Site.

1. Запушь репозиторий в GitHub.
2. В Render выбери `New` -> `Blueprint` и подключи репозиторий.
3. Render возьмет настройки из `render.yaml` и создаст `paper-first-tma`.
4. После деплоя скопируй URL вида `https://paper-first-tma.onrender.com`.
5. Поставь этот URL в BotFather и в локальный `.env`:

```env
PAPERFIRST_TELEGRAM_WEB_APP_URL=https://paper-first-tma.onrender.com
```

После этого локальный бот можно запускать без туннеля:

```bash
python3 start.py --all
```

Этот вариант хостит только frontend. Для рабочих API-запросов из Mini App понадобится публичный backend URL и `VITE_API_BASE_URL=https://your-api.example/api`.

Для локальной проверки внутри Telegram нужны публичные HTTPS URL для frontend и API. Например, через tunnel:

```env
PAPERFIRST_TELEGRAM_WEB_APP_URL=https://frontend-tunnel.example
PAPERFIRST_BACKEND_CORS_ORIGINS=["https://frontend-tunnel.example"]
VITE_API_BASE_URL=https://api-tunnel.example/api
```

После изменения URL перезапусти сервисы:

```bash
python3 start.py --all
```

## API

- `GET /api/health`
- `GET /api/strategy/sample`
- `POST /api/strategy/validate`
- `POST /api/backtests/run`
- `GET /api/backtests/{job_id}`

`POST /api/backtests/run` создает job в Postgres и кладет расчет в Redis/RQ. Отчет забирается через `GET /api/backtests/{job_id}`. Если `candles=[]` и `use_demo_data=true`, worker использует синтетическую историю свечей.

## StrategySpec

Минимальная стратегия:

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

Поддерживаемые поля на старте: `open`, `high`, `low`, `close`, `volume`, `sma_N`, `ema_N`, `rsi_N`.
