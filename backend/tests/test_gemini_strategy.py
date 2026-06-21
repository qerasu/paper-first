import asyncio
import base64
from io import BytesIO
from urllib.error import HTTPError

import pytest

from paperfirst.domain.strategy import sample_strategy
from paperfirst.services import gemini_strategy
from paperfirst.services.gemini_strategy import GeminiStrategyError, build_gemini_payload, import_strategy_with_gemini, parse_strategy_response


@pytest.mark.parametrize("mime_type,file_bytes", [("image/png", b"fake-png"), ("application/pdf", b"%PDF-1.7")])
def test_build_gemini_payload_accepts_text_and_file_templates(mime_type, file_bytes):
    payload = build_gemini_payload(text="buy when RSI is oversold", file_bytes=file_bytes, mime_type=mime_type)
    parts = payload["contents"][0]["parts"]

    assert any("RSI" in part.get("text", "") for part in parts)
    assert parts[-1]["inline_data"]["mime_type"] == mime_type
    assert parts[-1]["inline_data"]["data"] == base64.b64encode(file_bytes).decode("ascii")
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseSchema"]["properties"]["entry"]["required"] == ["all", "any"]
    assert "take_profit_pct" not in payload["generationConfig"]["responseSchema"]["properties"]["risk"]["required"]


def test_import_strategy_with_gemini_posts_payload_and_parses_response(monkeypatch):
    strategy = sample_strategy()
    calls = {}

    def fake_post_json(url, api_key, payload):
        calls["url"] = url
        calls["api_key"] = api_key
        calls["payload"] = payload

        return {"candidates": [{"content": {"parts": [{"text": strategy.model_dump_json()}]}}]}


    monkeypatch.setattr(gemini_strategy, "_post_json", fake_post_json)

    result = asyncio.run(
        import_strategy_with_gemini(
            api_key="test-key",
            model="models/gemini-test",
            text="entry: close > sma_20",
            file_bytes=b"chart",
            mime_type="image/png",
        )
    )

    parts = calls["payload"]["contents"][0]["parts"]

    assert result.name == strategy.name
    assert calls["api_key"] == "test-key"
    assert calls["url"].endswith("/models/gemini-test:generateContent")
    assert any("entry: close > sma_20" in part.get("text", "") for part in parts)
    assert parts[-1]["inline_data"]["mime_type"] == "image/png"


def test_parse_strategy_response_validates_strategy():
    strategy = sample_strategy()
    payload = {"candidates": [{"content": {"parts": [{"text": strategy.model_dump_json()}]}}]}

    assert parse_strategy_response(payload).name == strategy.name


def test_post_json_hides_http_error_body(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            BytesIO(b'{"error":{"message":"invalid model"}}'),
        )


    monkeypatch.setattr(gemini_strategy, "urlopen", fake_urlopen)

    with pytest.raises(GeminiStrategyError, match="400 Bad Request") as exc_info:
        gemini_strategy._post_json("https://example.test", "secret-key", {})

    assert "invalid model" not in str(exc_info.value)
