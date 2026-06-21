import asyncio
from datetime import UTC, datetime
from uuid import UUID

from paperfirst.domain.backtest import BacktestEngine, BacktestRunRequest, build_demo_candles
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
            candles = request.candles
            if not candles and request.use_demo_data:
                candles = build_demo_candles()
            if not candles:
                raise ValueError("candles are required unless use_demo_data=true")

            report = BacktestEngine().run(request.strategy, candles)
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
