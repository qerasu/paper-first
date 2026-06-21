import asyncio
import os
import re
from pathlib import Path

import pytest

from paperfirst.domain.strategy import StrategySpec
from paperfirst.services.gemini_strategy import MAX_INLINE_FILE_BYTES, import_strategy_with_gemini


API_KEY = os.getenv("PAPERFIRST_GEMINI_API_KEY")
MODEL = os.getenv("PAPERFIRST_GEMINI_MODEL", "gemini-3.5-flash")
RUN_LIVE_TESTS = os.getenv("RUN_LIVE_LLM_TESTS") == "1"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "strategy_sources"
TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt"}
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
}
BASE_FIELDS = {"open", "high", "low", "close", "volume"}
INDICATOR_PATTERN = re.compile(r"^(ema|sma|rsi)_\d+$")


def strategy_source_paths() -> list[Path]:
    return sorted(path for path in FIXTURES_DIR.iterdir() if path.is_file())


def load_strategy_source(path: Path) -> tuple[str, bytes | None, str | None]:
    if path.suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8"), None, None

    return f"Extract Paper First StrategySpec from uploaded file: {path.name}", path.read_bytes(), MIME_TYPES[path.suffix]


def assert_supported_strategy(strategy: StrategySpec) -> None:
    assert strategy.name.strip()
    assert strategy.entry.all or strategy.entry.any
    assert strategy.exit.all or strategy.exit.any
    assert strategy.risk.initial_capital > 0

    for field in strategy.referenced_fields():
        assert field in BASE_FIELDS or INDICATOR_PATTERN.match(field), field


@pytest.mark.skipif(not RUN_LIVE_TESTS, reason="set RUN_LIVE_LLM_TESTS=1 to run live LLM API tests")
@pytest.mark.skipif(not API_KEY, reason="set PAPERFIRST_GEMINI_API_KEY to run live LLM API tests")
@pytest.mark.parametrize("source_path", strategy_source_paths(), ids=lambda path: path.name)
def test_live_gemini_imports_strategy_source(source_path: Path) -> None:
    assert source_path.stat().st_size <= MAX_INLINE_FILE_BYTES

    text, file_bytes, mime_type = load_strategy_source(source_path)
    strategy = asyncio.run(
        import_strategy_with_gemini(
            api_key=API_KEY or "",
            model=MODEL,
            text=text,
            file_bytes=file_bytes,
            mime_type=mime_type,
        )
    )

    assert_supported_strategy(strategy)
