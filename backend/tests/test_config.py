from paperfirst.core.config import parse_cors_origins


def test_parse_cors_origins_accepts_json_and_plain_urls():
    assert parse_cors_origins('["https://app.example"]') == ["https://app.example"]
    assert parse_cors_origins("[https://app.example]") == ["https://app.example"]
    assert parse_cors_origins("https://app.example,http://localhost:5173") == [
        "https://app.example",
        "http://localhost:5173",
    ]
