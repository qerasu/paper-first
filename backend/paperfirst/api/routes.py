from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from paperfirst.core.config import get_settings
from paperfirst.domain.backtest import BacktestReport, BacktestRunRequest
from paperfirst.domain.strategy import StrategySpec, sample_strategy
from paperfirst.services.jobs import enqueue_backtest
from paperfirst.storage.models import BacktestJob, BacktestStatus, Strategy
from paperfirst.storage.session import get_session


router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    service: str


class BacktestJobResponse(BaseModel):
    id: UUID
    status: str
    report: BacktestReport | None = None
    error: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", service="paperfirst-api")


@router.get("/strategy/sample", response_model=StrategySpec)
async def get_sample_strategy():
    return sample_strategy()


@router.post("/strategy/validate", response_model=StrategySpec)
async def validate_strategy(strategy: StrategySpec):
    return strategy


@router.post("/backtests/run", response_model=BacktestJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(request: BacktestRunRequest, session: AsyncSession = Depends(get_session)):
    if not request.candles and not request.use_demo_data:
        raise HTTPException(status_code=400, detail="candles are required unless use_demo_data=true")

    strategy = Strategy(
        name=request.strategy.name,
        symbol=request.strategy.symbol,
        timeframe=request.strategy.timeframe,
        spec=request.strategy.model_dump(mode="json"),
    )
    job = BacktestJob(strategy=strategy, status=BacktestStatus.queued.value)
    session.add_all([strategy, job])
    await session.commit()
    await session.refresh(job)

    try:
        enqueue_backtest(job.id, request, settings.redis_url)
    except Exception as exc:
        job.status = BacktestStatus.failed.value
        job.error = "queue unavailable"
        job.updated_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(status_code=503, detail="backtest queue is unavailable") from exc

    return _job_response(job)


@router.get("/backtests/{job_id}", response_model=BacktestJobResponse)
async def get_backtest(job_id: UUID, session: AsyncSession = Depends(get_session)):
    job = await session.get(BacktestJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="backtest job not found")

    return _job_response(job)


def _job_response(job: BacktestJob) -> BacktestJobResponse:
    report = BacktestReport.model_validate(job.report) if job.report else None

    return BacktestJobResponse(id=job.id, status=job.status, report=report, error=job.error)
