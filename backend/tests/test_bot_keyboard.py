from paperfirst.bot.main import build_start_keyboard


def test_start_keyboard_uses_inline_web_app_button_for_https_url() -> None:
    keyboard = build_start_keyboard("https://app.example")

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Открыть Mini App"
    assert button.web_app is not None
    assert button.web_app.url == "https://app.example"


def test_start_keyboard_is_hidden_without_https_url() -> None:
    assert build_start_keyboard("http://localhost:5173") is None
