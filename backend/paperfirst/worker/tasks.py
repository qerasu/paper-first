from paperfirst.domain.backtest import BacktestEngine, BacktestRunRequest, build_demo_candles


def run_backtest_job(payload: dict) -> dict:
    request = BacktestRunRequest.model_validate(payload)
    candles = request.candles or build_demo_candles()
    report = BacktestEngine().run(request.strategy, candles)
    return report.model_dump(mode="json")
