import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from paperfirst.api import routes
from paperfirst.domain.strategy import sample_strategy


def upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


async def fake_import_strategy(**kwargs):
    fake_import_strategy.calls.append(kwargs)

    return sample_strategy()


fake_import_strategy.calls = []


def enable_fake_gemini(monkeypatch):
    fake_import_strategy.calls = []
    monkeypatch.setattr(routes.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(routes.settings, "gemini_model", "gemini-test")
    monkeypatch.setattr(routes, "import_strategy_with_gemini", fake_import_strategy)


def test_import_strategy_sends_text_to_model(monkeypatch):
    enable_fake_gemini(monkeypatch)

    strategy = asyncio.run(routes.import_strategy(text="  buy when close > sma_20  ", file=None))

    assert strategy.name == sample_strategy().name
    assert fake_import_strategy.calls == [
        {
            "api_key": "test-key",
            "model": "gemini-test",
            "text": "buy when close > sma_20",
            "file_bytes": None,
            "mime_type": None,
        }
    ]


@pytest.mark.parametrize(
    "filename,content_type,content",
    [
        ("strategy.txt", "text/plain", b"exit when rsi_14 > 72"),
        ("strategy.json", "application/json", b'{"entry":"close > sma_20"}'),
    ],
)
def test_import_strategy_merges_text_uploads_into_model_text(monkeypatch, filename, content_type, content):
    enable_fake_gemini(monkeypatch)
    file = upload_file(filename, content, content_type)

    asyncio.run(routes.import_strategy(text="entry when rsi_14 < 30", file=file))

    call = fake_import_strategy.calls[0]

    assert call["text"] == f"entry when rsi_14 < 30\n\n{content.decode()}"
    assert call["file_bytes"] is None
    assert call["mime_type"] is None


@pytest.mark.parametrize(
    "filename,content_type,content",
    [
        ("chart.png", "image/png", b"\x89PNG\r\nstrategy screenshot"),
        ("rules.pdf", "application/pdf", b"%PDF-1.7 strategy rules"),
    ],
)
def test_import_strategy_sends_binary_uploads_to_model(monkeypatch, filename, content_type, content):
    enable_fake_gemini(monkeypatch)
    file = upload_file(filename, content, content_type)

    asyncio.run(routes.import_strategy(text="extract this strategy", file=file))

    call = fake_import_strategy.calls[0]

    assert call["text"] == "extract this strategy"
    assert call["file_bytes"] == content
    assert call["mime_type"] == content_type


def test_import_strategy_rejects_empty_input(monkeypatch):
    enable_fake_gemini(monkeypatch)

    with pytest.raises(routes.HTTPException) as exc_info:
        asyncio.run(routes.import_strategy(text="", file=None))

    assert exc_info.value.status_code == 400
    assert fake_import_strategy.calls == []


def test_import_strategy_rejects_unsupported_upload(monkeypatch):
    enable_fake_gemini(monkeypatch)
    file = upload_file("strategy.zip", b"zip", "application/zip")

    with pytest.raises(routes.HTTPException) as exc_info:
        asyncio.run(routes.import_strategy(text="", file=file))

    assert exc_info.value.status_code == 415
    assert fake_import_strategy.calls == []
