import asyncio
from uuid import uuid4

import pytest

from paperfirst.api import routes
from paperfirst.domain.backtest import BacktestRunRequest
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


def test_run_backtest_rejects_missing_candles_without_demo_data():
    request = BacktestRunRequest(strategy=sample_strategy(), candles=[], use_demo_data=False)

    with pytest.raises(routes.HTTPException) as exc_info:
        asyncio.run(routes.run_backtest(request, FakeSession()))

    assert exc_info.value.status_code == 400
