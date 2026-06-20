from datetime import UTC, datetime, timedelta

from paperfirst.domain.backtest import BacktestEngine, Candle, build_demo_candles
from paperfirst.domain.strategy import ComparisonOperator, RiskSpec, SignalCondition, SignalGroup, StrategySpec, sample_strategy


def test_backtest_runs_on_demo_data() -> None:
    strategy = sample_strategy()
    candles = build_demo_candles(points=120)
    report = BacktestEngine().run(strategy, candles)

    assert report.metrics.total_candles == 120
    assert report.metrics.fees_paid >= 0
    assert report.verdict.value in {"reject", "unstable", "research", "paper", "live-ready"}


def test_forced_close_updates_final_drawdown_after_exit_costs() -> None:
    strategy = StrategySpec(
        name="forced close",
        entry=SignalGroup(all=[SignalCondition(left="close", operator=ComparisonOperator.greater_than, right=0)]),
        exit=SignalGroup(all=[SignalCondition(left="close", operator=ComparisonOperator.less_than, right=0)]),
        risk=RiskSpec(
            initial_capital=1_000,
            position_size_pct=100,
            stop_loss_pct=None,
            take_profit_pct=None,
            fee_bps=100,
            slippage_bps=0,
            max_drawdown_pct=100,
        ),
    )
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle(timestamp=started_at, open=100, high=100, low=100, close=100, volume=1),
        Candle(timestamp=started_at + timedelta(hours=1), open=50, high=50, low=50, close=50, volume=1),
    ]

    report = BacktestEngine().run(strategy, candles)
    expected_drawdown = (strategy.risk.initial_capital - report.equity_curve[-1].equity) / strategy.risk.initial_capital * 100

    assert report.metrics.max_drawdown_pct == round(expected_drawdown, 4)
