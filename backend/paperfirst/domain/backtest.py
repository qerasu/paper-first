from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from pydantic import BaseModel, Field, model_validator

from paperfirst.domain.strategy import ComparisonOperator, SignalCondition, SignalGroup, StrategySpec, Verdict


class Candle(BaseModel):
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def ensure_ohlc_shape(self) -> "Candle":
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("candle high/low does not contain open/close")
        return self


class Trade(BaseModel):
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    net_pnl: float
    fees_paid: float
    return_pct: float
    exit_reason: str


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    drawdown_pct: float


class BacktestMetrics(BaseModel):
    total_candles: int
    trade_count: int
    net_profit: float
    net_profit_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float | None
    expectancy_pct: float
    fees_paid: float


class BacktestReport(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    verdict: Verdict
    verdict_reason: str
    metrics: BacktestMetrics
    trades: list[Trade]
    equity_curve: list[EquityPoint]
    warnings: list[str] = Field(default_factory=list)


class BacktestRunRequest(BaseModel):
    strategy: StrategySpec
    candles: list[Candle] = Field(default_factory=list)
    use_demo_data: bool = True


@dataclass
class OpenPosition:
    entry_time: datetime
    entry_price: float
    quantity: float
    notional: float
    entry_fee: float


class BacktestEngine:
    def run(self, strategy: StrategySpec, candles: list[Candle]) -> BacktestReport:
        ordered_candles = sorted(candles, key=lambda candle: candle.timestamp)
        if not ordered_candles:
            raise ValueError("at least one candle is required")

        indicator_cache = self._build_indicator_cache(strategy, ordered_candles)
        cash = strategy.risk.initial_capital
        position: OpenPosition | None = None
        trades = []
        equity_curve = []
        fees_paid = 0.0
        peak_equity = cash

        for index, candle in enumerate(ordered_candles):
            if position is None and self._matches(strategy.entry, strategy, ordered_candles, indicator_cache, index):
                position, entry_fee = self._open_position(strategy, candle, cash)
                cash -= position.notional + entry_fee
                fees_paid += entry_fee
            elif position is not None:
                exit_reason = self._exit_reason(strategy, position, candle, ordered_candles, indicator_cache, index)
                if exit_reason:
                    trade, cash_delta = self._close_position(strategy, position, candle, exit_reason)
                    cash += cash_delta
                    fees_paid += trade.fees_paid - position.entry_fee
                    trades.append(trade)
                    position = None

            mark_equity = cash
            if position is not None:
                mark_equity += position.quantity * candle.close
            peak_equity = max(peak_equity, mark_equity)
            drawdown_pct = 0.0 if peak_equity == 0 else (peak_equity - mark_equity) / peak_equity * 100
            equity_curve.append(EquityPoint(timestamp=candle.timestamp, equity=mark_equity, drawdown_pct=drawdown_pct))

        if position is not None:
            last_candle = ordered_candles[-1]
            trade, cash_delta = self._close_position(strategy, position, last_candle, "end_of_data")
            cash += cash_delta
            fees_paid += trade.fees_paid - position.entry_fee
            trades.append(trade)
            drawdown_pct = 0.0 if peak_equity == 0 else (peak_equity - cash) / peak_equity * 100
            equity_curve[-1] = EquityPoint(timestamp=last_candle.timestamp, equity=cash, drawdown_pct=drawdown_pct)

        metrics = self._build_metrics(strategy.risk.initial_capital, cash, ordered_candles, trades, equity_curve, fees_paid)
        verdict, reason, warnings = self._build_verdict(strategy, metrics)
        return BacktestReport(
            strategy_name=strategy.name,
            symbol=strategy.symbol,
            timeframe=strategy.timeframe,
            verdict=verdict,
            verdict_reason=reason,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            warnings=warnings,
        )


    def _open_position(self, strategy: StrategySpec, candle: Candle, cash: float) -> tuple[OpenPosition, float]:
        fee_rate = strategy.risk.fee_bps / 10_000
        slippage_rate = strategy.risk.slippage_bps / 10_000
        target_notional = cash * strategy.risk.position_size_pct / 100
        notional = min(target_notional, cash / (1 + fee_rate))
        entry_price = candle.close * (1 + slippage_rate)
        quantity = notional / entry_price
        entry_fee = notional * fee_rate
        return OpenPosition(candle.timestamp, entry_price, quantity, notional, entry_fee), entry_fee


    def _close_position(
        self,
        strategy: StrategySpec,
        position: OpenPosition,
        candle: Candle,
        exit_reason: str,
    ) -> tuple[Trade, float]:
        fee_rate = strategy.risk.fee_bps / 10_000
        slippage_rate = strategy.risk.slippage_bps / 10_000
        exit_price = candle.close * (1 - slippage_rate)
        gross_value = position.quantity * exit_price
        exit_fee = gross_value * fee_rate
        gross_pnl = gross_value - position.notional
        net_pnl = gross_pnl - position.entry_fee - exit_fee
        return_pct = 0.0 if position.notional == 0 else net_pnl / position.notional * 100
        trade = Trade(
            entry_time=position.entry_time,
            exit_time=candle.timestamp,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            fees_paid=position.entry_fee + exit_fee,
            return_pct=return_pct,
            exit_reason=exit_reason,
        )
        return trade, gross_value - exit_fee


    def _exit_reason(
        self,
        strategy: StrategySpec,
        position: OpenPosition,
        candle: Candle,
        candles: list[Candle],
        indicator_cache: dict[str, list[float | None]],
        index: int,
    ) -> str | None:
        stop_loss_pct = strategy.risk.stop_loss_pct
        if stop_loss_pct is not None and candle.close <= position.entry_price * (1 - stop_loss_pct / 100):
            return "stop_loss"

        take_profit_pct = strategy.risk.take_profit_pct
        if take_profit_pct is not None and candle.close >= position.entry_price * (1 + take_profit_pct / 100):
            return "take_profit"

        if self._matches(strategy.exit, strategy, candles, indicator_cache, index):
            return "signal"
        return None


    def _matches(
        self,
        group: SignalGroup,
        strategy: StrategySpec,
        candles: list[Candle],
        indicator_cache: dict[str, list[float | None]],
        index: int,
    ) -> bool:
        all_match = all(
            self._condition_matches(condition, strategy, candles, indicator_cache, index)
            for condition in group.all
        )
        any_match = not group.any or any(
            self._condition_matches(condition, strategy, candles, indicator_cache, index)
            for condition in group.any
        )
        return all_match and any_match


    def _condition_matches(
        self,
        condition: SignalCondition,
        strategy: StrategySpec,
        candles: list[Candle],
        indicator_cache: dict[str, list[float | None]],
        index: int,
    ) -> bool:
        left = self._resolve_value(condition.left, strategy, candles, indicator_cache, index)
        right = self._resolve_value(condition.right, strategy, candles, indicator_cache, index)
        if left is None or right is None:
            return False

        if condition.operator == ComparisonOperator.greater_than:
            return left > right
        if condition.operator == ComparisonOperator.greater_or_equal:
            return left >= right
        if condition.operator == ComparisonOperator.less_than:
            return left < right
        if condition.operator == ComparisonOperator.less_or_equal:
            return left <= right
        if condition.operator == ComparisonOperator.equal:
            return left == right
        return left != right


    def _resolve_value(
        self,
        token: float | str,
        strategy: StrategySpec,
        candles: list[Candle],
        indicator_cache: dict[str, list[float | None]],
        index: int,
    ) -> float | None:
        if isinstance(token, float | int):
            return float(token)

        candle = candles[index]
        fields = {
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "equity": strategy.risk.initial_capital,
        }
        if token in fields:
            return fields[token]
        if token in indicator_cache:
            return indicator_cache[token][index]
        return None


    def _build_indicator_cache(self, strategy: StrategySpec, candles: list[Candle]) -> dict[str, list[float | None]]:
        cache = {}
        close_values = [candle.close for candle in candles]
        for field in strategy.referenced_fields():
            if field.startswith("sma_"):
                cache[field] = _moving_average(close_values, _period_from_token(field))
            elif field.startswith("ema_"):
                cache[field] = _exponential_moving_average(close_values, _period_from_token(field))
            elif field.startswith("rsi_"):
                cache[field] = _relative_strength_index(close_values, _period_from_token(field))
        return cache


    def _build_metrics(
        self,
        initial_capital: float,
        final_equity: float,
        candles: list[Candle],
        trades: list[Trade],
        equity_curve: list[EquityPoint],
        fees_paid: float,
    ) -> BacktestMetrics:
        net_profit = final_equity - initial_capital
        winning = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
        losing = [trade.net_pnl for trade in trades if trade.net_pnl < 0]
        gross_win = sum(winning)
        gross_loss = abs(sum(losing))
        profit_factor = None if gross_loss == 0 and gross_win > 0 else 0.0 if gross_loss == 0 else gross_win / gross_loss
        win_rate_pct = 0.0 if not trades else len(winning) / len(trades) * 100
        expectancy_pct = 0.0 if not trades else sum(trade.return_pct for trade in trades) / len(trades)
        max_drawdown_pct = max((point.drawdown_pct for point in equity_curve), default=0.0)
        return BacktestMetrics(
            total_candles=len(candles),
            trade_count=len(trades),
            net_profit=round(net_profit, 6),
            net_profit_pct=round(net_profit / initial_capital * 100, 4),
            max_drawdown_pct=round(max_drawdown_pct, 4),
            win_rate_pct=round(win_rate_pct, 4),
            profit_factor=None if profit_factor is None else round(profit_factor, 4),
            expectancy_pct=round(expectancy_pct, 4),
            fees_paid=round(fees_paid, 6),
        )


    def _build_verdict(self, strategy: StrategySpec, metrics: BacktestMetrics) -> tuple[Verdict, str, list[str]]:
        warnings = []
        if metrics.trade_count < 5:
            warnings.append("too few trades for statistical confidence")
        if metrics.max_drawdown_pct > strategy.risk.max_drawdown_pct:
            return Verdict.reject, "drawdown limit exceeded", warnings
        if metrics.net_profit_pct <= 0:
            return Verdict.reject, "strategy lost money after fees and slippage", warnings
        if metrics.profit_factor is not None and metrics.profit_factor < 1.2:
            return Verdict.unstable, "profit factor is too weak", warnings
        if metrics.trade_count >= 20 and metrics.net_profit_pct > 5 and metrics.max_drawdown_pct < strategy.risk.max_drawdown_pct / 2:
            return Verdict.paper, "strategy is eligible for paper-forward testing", warnings
        return Verdict.research, "strategy needs more robustness checks", warnings


def _period_from_token(token: str) -> int:
    try:
        period = int(token.rsplit("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"invalid indicator token: {token}") from exc
    if period <= 1:
        raise ValueError(f"indicator period must be greater than 1: {token}")
    return period


def _moving_average(values: list[float], period: int) -> list[float | None]:
    result = []
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += value
        if index >= period:
            window_sum -= values[index - period]
        if index + 1 < period:
            result.append(None)
        else:
            result.append(window_sum / period)
    return result


def _exponential_moving_average(values: list[float], period: int) -> list[float | None]:
    result = []
    multiplier = 2 / (period + 1)
    ema: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period:
            result.append(None)
            continue
        if ema is None:
            ema = sum(values[index + 1 - period:index + 1]) / period
        else:
            ema = (value - ema) * multiplier + ema
        result.append(ema)
    return result


def _relative_strength_index(values: list[float], period: int) -> list[float | None]:
    if len(values) < period + 1:
        return [None for _ in values]

    result: list[float | None] = [None for _ in values]
    gains = []
    losses = []
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
        if index < period:
            continue
        if index == period:
            average_gain = sum(gains[-period:]) / period
            average_loss = sum(losses[-period:]) / period
        else:
            average_gain = (average_gain * (period - 1) + gains[-1]) / period
            average_loss = (average_loss * (period - 1) + losses[-1]) / period
        if average_loss == 0:
            result[index] = 100.0
            continue
        relative_strength = average_gain / average_loss
        rsi = 100 - 100 / (1 + relative_strength)
        result[index] = rsi if isfinite(rsi) else None
    return result
