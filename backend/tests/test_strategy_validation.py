import pytest
from pydantic import ValidationError

from paperfirst.domain.strategy import SignalGroup, StrategySpec, sample_strategy


def test_sample_strategy_is_valid():
    strategy = sample_strategy()

    assert strategy.name == "RSI trend filter"
    assert "sma_20" in strategy.referenced_fields()


def test_signal_group_requires_conditions():
    with pytest.raises(ValidationError):
        StrategySpec(
            name="broken strategy",
            entry=SignalGroup(all=[]),
            exit=SignalGroup(all=[]),
        )


def test_strategy_text_is_validated_after_strip():
    payload = sample_strategy().model_dump()
    payload["name"] = "  "

    with pytest.raises(ValidationError):
        StrategySpec.model_validate(payload)
