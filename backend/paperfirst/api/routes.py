from datetime import UTC, datetime
from mimetypes import guess_type
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from paperfirst.core.config import get_settings
from paperfirst.domain.backtest import BacktestEngine, BacktestReport, BacktestRunRequest, build_demo_candles
from paperfirst.domain.strategy import StrategySpec, sample_strategy
from paperfirst.services.gemini_strategy import (
    GeminiStrategyError,
    MAX_INLINE_FILE_BYTES,
    import_strategy_with_gemini,
)
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


@router.post("/strategy/import", response_model=StrategySpec)
async def import_strategy(text: str = Form(default=""), file: UploadFile | None = File(default=None)):
    clean_text = text.strip()
    file_bytes: bytes | None = None
    mime_type: str | None = None

    if file is not None:
        content = await file.read(MAX_INLINE_FILE_BYTES + 1)
        if len(content) > MAX_INLINE_FILE_BYTES:
            raise HTTPException(status_code=413, detail="file is too large for inline Gemini import")

        mime_type = _upload_mime_type(file)
        if mime_type.startswith("text/") or mime_type == "application/json":
            uploaded_text = content.decode("utf-8", errors="replace")
            clean_text = "\n\n".join(part for part in [clean_text, uploaded_text] if part)
            mime_type = None
        elif mime_type == "application/pdf" or mime_type.startswith("image/"):
            file_bytes = content
        else:
            raise HTTPException(status_code=415, detail="upload a PDF, image, or text file")

    if not clean_text and file_bytes is None:
        raise HTTPException(status_code=400, detail="text or file is required")
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini API key is not configured")

    try:
        return await import_strategy_with_gemini(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            text=clean_text,
            file_bytes=file_bytes,
            mime_type=mime_type,
        )
    except GeminiStrategyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/backtests/run", response_model=BacktestJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(request: BacktestRunRequest, session: AsyncSession = Depends(get_session)):
    if not request.candles and not request.use_demo_data:
        raise HTTPException(status_code=400, detail="candles are required unless use_demo_data=true")

    try:
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
    except Exception:
        return _run_backtest_now(request)

    try:
        enqueue_backtest(job.id, request, settings.redis_url)
    except Exception:
        report = _build_backtest_report(request)
        job.status = BacktestStatus.completed.value
        job.report = report.model_dump(mode="json")
        job.error = None
        job.updated_at = datetime.now(UTC)
        await session.commit()
        return _job_response(job)

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


def _run_backtest_now(request: BacktestRunRequest) -> BacktestJobResponse:
    return BacktestJobResponse(
        id=uuid4(),
        status=BacktestStatus.completed.value,
        report=_build_backtest_report(request),
    )


def _build_backtest_report(request: BacktestRunRequest) -> BacktestReport:
    candles = request.candles
    if not candles and request.use_demo_data:
        candles = build_demo_candles()

    return BacktestEngine().run(request.strategy, candles)


def _upload_mime_type(file: UploadFile) -> str:
    guessed_type = guess_type(file.filename or "")[0]
    if file.content_type and file.content_type != "application/octet-stream":
        return file.content_type

    return guessed_type or "application/octet-stream"
