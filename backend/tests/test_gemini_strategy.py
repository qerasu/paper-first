from paperfirst.domain.strategy import sample_strategy
from paperfirst.services.gemini_strategy import build_gemini_payload, parse_strategy_response


def test_build_gemini_payload_accepts_text_and_file():
    payload = build_gemini_payload(text="buy when RSI is oversold", file_bytes=b"fake", mime_type="image/png")
    parts = payload["contents"][0]["parts"]

    assert any("RSI" in part.get("text", "") for part in parts)
    assert parts[-1]["inline_data"]["mime_type"] == "image/png"
    assert payload["generationConfig"]["responseFormat"]["text"]["mimeType"] == "application/json"


def test_parse_strategy_response_validates_strategy():
    strategy = sample_strategy()
    payload = {"candidates": [{"content": {"parts": [{"text": strategy.model_dump_json()}]}}]}

    assert parse_strategy_response(payload).name == strategy.name
