from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ComparisonOperator(StrEnum):
    greater_than = ">"
    greater_or_equal = ">="
    less_than = "<"
    less_or_equal = "<="
    equal = "=="
    not_equal = "!="


class Verdict(StrEnum):
    reject = "reject"
    unstable = "unstable"
    research = "research"
    paper = "paper"
    live_ready = "live-ready"


class SignalCondition(BaseModel):
    left: str = Field(min_length=1)
    operator: ComparisonOperator
    right: float | str

    @field_validator("left", mode="before")
    @classmethod
    def normalize_left(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


    @field_validator("right", mode="before")
    @classmethod
    def normalize_right(cls, value: float | str) -> float | str:
        if isinstance(value, str):
            value = value.strip().lower()
            if not value:
                raise ValueError("right must not be blank")
        return value


class SignalGroup(BaseModel):
    all: list[SignalCondition] = Field(default_factory=list)
    any: list[SignalCondition] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_has_conditions(self) -> "SignalGroup":
        if not self.all and not self.any:
            raise ValueError("signal group must contain at least one condition")
        return self


class RiskSpec(BaseModel):
    initial_capital: float = Field(default=1_000.0, gt=0)
    position_size_pct: float = Field(default=10.0, gt=0, le=100)
    stop_loss_pct: float | None = Field(default=3.0, gt=0, le=100)
    take_profit_pct: float | None = Field(default=None, gt=0, le=1_000)
    fee_bps: float = Field(default=8.0, ge=0, le=1_000)
    slippage_bps: float = Field(default=5.0, ge=0, le=1_000)
    max_drawdown_pct: float = Field(default=25.0, gt=0, le=100)


class StrategySpec(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="1h", min_length=1, max_length=8)
    entry: SignalGroup
    exit: SignalGroup
    risk: RiskSpec = Field(default_factory=RiskSpec)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "symbol", "timeframe", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


    def referenced_fields(self) -> set[str]:
        fields: set[str] = set()
        for condition in self.conditions:
            fields.add(condition.left)
            if isinstance(condition.right, str):
                fields.add(condition.right)
        return fields


    @property
    def conditions(self) -> list[SignalCondition]:
        return [
            *self.entry.all,
            *self.entry.any,
            *self.exit.all,
            *self.exit.any,
        ]


def sample_strategy() -> StrategySpec:
    return StrategySpec(
        name="RSI trend filter",
        symbol="BTC/USDT",
        timeframe="1h",
        entry=SignalGroup(
            all=[
                SignalCondition(left="close", operator=ComparisonOperator.greater_than, right="sma_20"),
                SignalCondition(left="rsi_14", operator=ComparisonOperator.less_than, right=62),
            ],
        ),
        exit=SignalGroup(
            any=[
                SignalCondition(left="close", operator=ComparisonOperator.less_than, right="sma_20"),
                SignalCondition(left="rsi_14", operator=ComparisonOperator.greater_than, right=72),
            ],
        ),
        risk=RiskSpec(
            initial_capital=1_000,
            position_size_pct=25,
            stop_loss_pct=4,
            take_profit_pct=9,
            fee_bps=8,
            slippage_bps=5,
            max_drawdown_pct=20,
        ),
    )
