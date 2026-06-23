import json
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from paperfirst.domain.backtest import BacktestRunRequest, Candle


COINBASE_API_BASE = "https://api.exchange.coinbase.com"
DEFAULT_CANDLE_LIMIT = 240
MAX_CANDLE_LIMIT = 300
REQUEST_TIMEOUT_SECONDS = 10
SUPPORTED_TIMEFRAMES = {
    "1m": 60,
    "1min": 60,
    "5m": 300,
    "5min": 300,
    "15m": 900,
    "15min": 900,
    "1h": 3_600,
    "6h": 21_600,
    "1d": 86_400,
    "1day": 86_400,
}
QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "EUR", "GBP", "BTC", "ETH")


class MarketDataError(ValueError):
    pass


def resolve_backtest_candles(request: BacktestRunRequest) -> list[Candle]:
    if request.candles:
        return request.candles
    if not request.use_demo_data:
        raise MarketDataError("candles are required when live market data is disabled")

    return fetch_market_candles(request.strategy.symbol, request.strategy.timeframe)


def fetch_market_candles(symbol: str, timeframe: str, limit: int = DEFAULT_CANDLE_LIMIT) -> list[Candle]:
    granularity = _coinbase_granularity(timeframe)
    product_id = _coinbase_product_id(symbol)
    clean_limit = min(max(limit, 1), MAX_CANDLE_LIMIT)
    end = datetime.now(UTC).replace(microsecond=0)
    lookback_limit = min(clean_limit + 1, MAX_CANDLE_LIMIT)
    start = end - timedelta(seconds=granularity * lookback_limit)
    query = urlencode(
        {
            "granularity": granularity,
            "start": _coinbase_timestamp(start),
            "end": _coinbase_timestamp(end),
        }
    )
    url = f"{COINBASE_API_BASE}/products/{quote(product_id, safe='')}/candles?{query}"

    try:
        rows = _request_json(url)
    except MarketDataError as exc:
        raise MarketDataError(f"could not load {product_id} {timeframe} candles: {exc}") from exc
    if not isinstance(rows, list):
        raise MarketDataError(f"unexpected Coinbase response for {product_id}")

    candles = [_coinbase_row_to_candle(row) for row in rows]
    candles.sort(key=lambda candle: candle.timestamp)
    if not candles:
        raise MarketDataError(f"Coinbase returned no candles for {product_id} {timeframe}")

    return candles[-clean_limit:]


def _coinbase_granularity(timeframe: str) -> int:
    normalized = timeframe.strip().lower()
    if normalized not in SUPPORTED_TIMEFRAMES:
        supported = ", ".join(["1m", "5m", "15m", "1h", "6h", "1d"])
        raise MarketDataError(f"unsupported timeframe {timeframe!r}; supported: {supported}")

    return SUPPORTED_TIMEFRAMES[normalized]


def _coinbase_product_id(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("/", "-").replace("_", "-").replace(" ", "")
    parts = [part for part in normalized.split("-") if part]
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1]}"

    for quote_currency in QUOTE_SUFFIXES:
        if normalized.endswith(quote_currency) and len(normalized) > len(quote_currency):
            return f"{normalized[:-len(quote_currency)]}-{quote_currency}"

    raise MarketDataError(f"unsupported symbol format {symbol!r}; use BASE/QUOTE, for example BTC/USDT")


def _coinbase_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _coinbase_row_to_candle(row: object) -> Candle:
    if not isinstance(row, list | tuple) or len(row) < 6:
        raise MarketDataError("unexpected Coinbase candle row")

    timestamp, low_price, high_price, open_price, close_price, volume = row[:6]
    try:
        return Candle(
            timestamp=datetime.fromtimestamp(float(timestamp), UTC),
            open=float(open_price),
            high=float(high_price),
            low=float(low_price),
            close=float(close_price),
            volume=float(volume),
        )
    except (TypeError, ValueError) as exc:
        raise MarketDataError("invalid Coinbase candle values") from exc


def _request_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "paper-first/0.1"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise MarketDataError(f"Coinbase HTTP {exc.code}") from exc
    except (TimeoutError, URLError) as exc:
        raise MarketDataError(f"Coinbase request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise MarketDataError("Coinbase returned invalid JSON") from exc
