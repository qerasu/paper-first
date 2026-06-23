import asyncio
from datetime import UTC, datetime
from uuid import UUID

from paperfirst.domain.backtest import BacktestEngine, BacktestRunRequest
from paperfirst.services.market_data import resolve_backtest_candles
from paperfirst.storage.models import BacktestJob, BacktestStatus
from paperfirst.storage.session import SessionLocal


def run_backtest_job(payload):
    return asyncio.run(_run_backtest_job(payload))


async def _run_backtest_job(payload):
    backtest_id = UUID(payload["backtest_id"])
    request = BacktestRunRequest.model_validate(payload["request"])

    async with SessionLocal() as session:
        job = await session.get(BacktestJob, backtest_id)
        if job is None:
            raise ValueError(f"backtest job not found: {backtest_id}")

        job.status = BacktestStatus.running.value
        job.error = None
        job.updated_at = datetime.now(UTC)
        await session.commit()

        try:
            report = BacktestEngine().run(request.strategy, resolve_backtest_candles(request))
        except Exception as exc:
            job.status = BacktestStatus.failed.value
            job.error = str(exc)
            job.updated_at = datetime.now(UTC)
            await session.commit()
            raise

        job.status = BacktestStatus.completed.value
        job.report = report.model_dump(mode="json")
        job.updated_at = datetime.now(UTC)
        await session.commit()
        return job.report
