from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from paperfirst.domain.strategy import StrategySpec


MAX_INLINE_FILE_BYTES = 12 * 1024 * 1024
GEMINI_TIMEOUT_SECONDS = 100

PROMPT = """
Convert the user's trading strategy source into Paper First StrategySpec JSON.
Use only fields supported by the backtester: open, high, low, close, volume, sma_N, ema_N, rsi_N.
Use only these operators: >, >=, <, <=, ==, !=.
Map entry rules to opening a long position and exit rules to closing it.
If symbol, timeframe, or risk settings are missing, use conservative defaults.
Always include entry.all, entry.any, exit.all, exit.any, and required risk fields.
Put short extraction assumptions in metadata.assumptions.
""".strip()
CONDITION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "left": {"type": "STRING"},
        "operator": {"type": "STRING", "enum": [">", ">=", "<", "<=", "==", "!="]},
        "right": {"anyOf": [{"type": "NUMBER"}, {"type": "STRING"}]},
    },
    "required": ["left", "operator", "right"],
}
SIGNAL_GROUP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "all": {"type": "ARRAY", "items": CONDITION_SCHEMA},
        "any": {"type": "ARRAY", "items": CONDITION_SCHEMA},
    },
    "required": ["all", "any"],
}
STRATEGY_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "symbol": {"type": "STRING"},
        "timeframe": {"type": "STRING"},
        "entry": SIGNAL_GROUP_SCHEMA,
        "exit": SIGNAL_GROUP_SCHEMA,
        "risk": {
            "type": "OBJECT",
            "properties": {
                "initial_capital": {"type": "NUMBER"},
                "position_size_pct": {"type": "NUMBER"},
                "stop_loss_pct": {"type": "NUMBER"},
                "take_profit_pct": {"type": "NUMBER"},
                "fee_bps": {"type": "NUMBER"},
                "slippage_bps": {"type": "NUMBER"},
                "max_drawdown_pct": {"type": "NUMBER"},
            },
            "required": [
                "initial_capital",
                "position_size_pct",
                "stop_loss_pct",
                "fee_bps",
                "slippage_bps",
                "max_drawdown_pct",
            ],
        },
        "metadata": {
            "type": "OBJECT",
            "properties": {
                "assumptions": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        },
    },
    "required": ["name", "symbol", "timeframe", "entry", "exit", "risk"],
}


class GeminiStrategyError(RuntimeError):
    pass


async def import_strategy_with_gemini(
    *,
    api_key: str,
    model: str,
    text: str,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
) -> StrategySpec:
    payload = build_gemini_payload(text=text, file_bytes=file_bytes, mime_type=mime_type)
    model_name = quote(model.removeprefix("models/"))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    response = await asyncio.to_thread(_post_json, url, api_key, payload)

    return parse_strategy_response(response)


def build_gemini_payload(*, text: str, file_bytes: bytes | None = None, mime_type: str | None = None) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"text": PROMPT}]
    if text.strip():
        parts.append({"text": f"User text:\n{text.strip()}"})
    if file_bytes is not None and mime_type:
        parts.append(
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(file_bytes).decode("ascii"),
                }
            }
        )

    return {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": STRATEGY_RESPONSE_SCHEMA,
        },
    }


def parse_strategy_response(payload: dict[str, Any]) -> StrategySpec:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiStrategyError("Gemini did not return a strategy") from exc

    try:
        return StrategySpec.model_validate_json(text)
    except ValueError as exc:
        raise GeminiStrategyError("Gemini returned invalid StrategySpec") from exc


def _post_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GeminiStrategyError(f"Gemini request failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise GeminiStrategyError(f"Gemini request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise GeminiStrategyError("Gemini request failed: request timed out") from exc
    except json.JSONDecodeError as exc:
        raise GeminiStrategyError("Gemini request failed: invalid JSON response") from exc
