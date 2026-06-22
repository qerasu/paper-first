from paperfirst.core.config import Settings, normalize_database_url, parse_cors_origins


def test_parse_cors_origins_accepts_json_and_plain_urls():
    assert parse_cors_origins('["https://app.example"]') == ["https://app.example"]
    assert parse_cors_origins("[https://app.example]") == ["https://app.example"]
    assert parse_cors_origins("https://app.example,http://localhost:5173") == [
        "https://app.example",
        "http://localhost:5173",
    ]


def test_normalize_database_url_uses_asyncpg_for_render_postgres_url():
    raw_url = "postgresql://paperfirst:secret@example.render.com:5432/paperfirst"

    assert (
        normalize_database_url(raw_url)
        == "postgresql+asyncpg://paperfirst:secret@example.render.com:5432/paperfirst"
    )


def test_settings_normalizes_database_url():
    settings = Settings(database_url="postgresql://paperfirst:secret@example.render.com:5432/paperfirst")

    assert settings.database_url.startswith("postgresql+asyncpg://")
