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
GEMINI_TIMEOUT_SECONDS = 45

PROMPT = """
Convert the user's trading strategy source into Paper First StrategySpec JSON.
Use only fields supported by the backtester: open, high, low, close, volume, sma_N, ema_N, rsi_N.
Use only these operators: >, >=, <, <=, ==, !=.
Map entry rules to opening a long position and exit rules to closing it.
If symbol, timeframe, or risk settings are missing, use conservative defaults.
Put short extraction assumptions in metadata.assumptions.
""".strip()


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
            "responseFormat": {
                "text": {
                    "mimeType": "application/json",
                    "schema": StrategySpec.model_json_schema(),
                }
            },
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
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GeminiStrategyError("Gemini request failed") from exc
