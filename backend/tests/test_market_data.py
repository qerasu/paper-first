from datetime import UTC, datetime

import pytest

from paperfirst.services import market_data
from paperfirst.services.market_data import MarketDataError, fetch_market_candles


def test_fetch_market_candles_parses_coinbase_rows(monkeypatch):
    captured = {}

    def fake_request_json(url):
        captured["url"] = url
        return [
            [1_700_003_600, 9, 11, 10, 10.5, 100],
            [1_700_000_000, 8, 10, 9, 9.5, 90],
        ]

    monkeypatch.setattr(market_data, "_request_json", fake_request_json)

    candles = fetch_market_candles("BTC/USDT", "1h", limit=2)

    assert "/products/BTC-USDT/candles" in captured["url"]
    assert "granularity=3600" in captured["url"]
    assert [candle.timestamp for candle in candles] == [
        datetime.fromtimestamp(1_700_000_000, UTC),
        datetime.fromtimestamp(1_700_003_600, UTC),
    ]
    assert candles[0].open == 9
    assert candles[1].close == 10.5


def test_fetch_market_candles_normalizes_compact_symbol(monkeypatch):
    captured = {}

    def fake_request_json(url):
        captured["url"] = url
        return [[1_700_000_000, 8, 10, 9, 9.5, 90]]

    monkeypatch.setattr(market_data, "_request_json", fake_request_json)

    fetch_market_candles("ETHUSDT", "15m", limit=1)

    assert "/products/ETH-USDT/candles" in captured["url"]
    assert "granularity=900" in captured["url"]


def test_fetch_market_candles_rejects_unsupported_timeframe():
    with pytest.raises(MarketDataError) as exc_info:
        fetch_market_candles("BTC/USDT", "4h")

    assert "unsupported timeframe" in str(exc_info.value)


def test_fetch_market_candles_rejects_bad_symbol():
    with pytest.raises(MarketDataError) as exc_info:
        fetch_market_candles("BTC", "1h")

    assert "unsupported symbol format" in str(exc_info.value)
