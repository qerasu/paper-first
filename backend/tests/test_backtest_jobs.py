import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from paperfirst.api import routes
from paperfirst.domain.backtest import BacktestRunRequest, Candle
from paperfirst.domain.strategy import sample_strategy
from paperfirst.storage.models import BacktestJob, BacktestStatus, Strategy


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0


    def add_all(self, items):
        self.added.extend(items)


    async def commit(self):
        self.commits += 1


    async def refresh(self, item):
        item.id = item.id or uuid4()


class FailingSession(FakeSession):
    async def commit(self):
        raise ConnectionRefusedError("database unavailable")


def test_run_backtest_creates_job_and_enqueues(monkeypatch):
    session = FakeSession()
    calls = {}

    def fake_enqueue_backtest(backtest_id, request, redis_url):
        calls["backtest_id"] = backtest_id
        calls["request"] = request
        calls["redis_url"] = redis_url
        return "rq-job-id"


    monkeypatch.setattr(routes, "enqueue_backtest", fake_enqueue_backtest)
    request = BacktestRunRequest(strategy=sample_strategy(), candles=[], use_demo_data=True)

    response = asyncio.run(routes.run_backtest(request, session))

    assert response.status == BacktestStatus.queued.value
    assert response.report is None
    assert response.error is None
    assert calls["backtest_id"] == response.id
    assert calls["request"] is request
    assert isinstance(session.added[0], Strategy)
    assert isinstance(session.added[1], BacktestJob)
    assert session.commits == 1


def test_run_backtest_runs_inline_without_database(monkeypatch):
    monkeypatch.setattr(routes, "resolve_backtest_candles", lambda request: _test_candles())
    request = BacktestRunRequest(strategy=sample_strategy(), candles=[], use_demo_data=True)

    response = asyncio.run(routes.run_backtest(request, FailingSession()))

    assert response.status == BacktestStatus.completed.value
    assert response.report is not None


def test_run_backtest_rejects_missing_candles_without_demo_data():
    request = BacktestRunRequest(strategy=sample_strategy(), candles=[], use_demo_data=False)

    with pytest.raises(routes.HTTPException) as exc_info:
        asyncio.run(routes.run_backtest(request, FakeSession()))

    assert exc_info.value.status_code == 400


def test_run_backtest_returns_400_when_market_data_is_unavailable(monkeypatch):
    def fail_market_data(request):
        raise routes.MarketDataError("unsupported timeframe '4h'; supported: 1m, 5m, 15m, 1h, 6h, 1d")

    monkeypatch.setattr(routes, "resolve_backtest_candles", fail_market_data)
    request = BacktestRunRequest(strategy=sample_strategy(), candles=[], use_demo_data=True)

    with pytest.raises(routes.HTTPException) as exc_info:
        asyncio.run(routes.run_backtest(request, FailingSession()))

    assert exc_info.value.status_code == 400
    assert "unsupported timeframe" in exc_info.value.detail


def _test_candles() -> list[Candle]:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Candle(
            timestamp=started_at + timedelta(hours=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=1_000,
        )
        for index in range(30)
    ]
