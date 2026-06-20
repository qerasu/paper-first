from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from paperfirst.domain.backtest import BacktestEngine, BacktestReport, BacktestRunRequest, build_demo_candles
from paperfirst.domain.strategy import StrategySpec, sample_strategy


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="paperfirst-api")


@router.get("/strategy/sample", response_model=StrategySpec)
async def get_sample_strategy() -> StrategySpec:
    return sample_strategy()


@router.post("/strategy/validate", response_model=StrategySpec)
async def validate_strategy(strategy: StrategySpec) -> StrategySpec:
    return strategy


@router.post("/backtests/run", response_model=BacktestReport)
async def run_backtest(request: BacktestRunRequest) -> BacktestReport:
    candles = request.candles
    if not candles and request.use_demo_data:
        candles = build_demo_candles()
    if not candles:
        raise HTTPException(status_code=400, detail="candles are required unless use_demo_data=true")

    engine = BacktestEngine()
    try:
        return engine.run(request.strategy, candles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
