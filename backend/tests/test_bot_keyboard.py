from paperfirst.bot.main import build_reply_keyboard, build_start_keyboard


def test_start_keyboard_uses_inline_web_app_button_for_https_url():
    keyboard = build_start_keyboard("https://app.example")

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Open Mini App"
    assert button.web_app is not None
    assert button.web_app.url == "https://app.example?v=ui-3"


def test_start_keyboard_keeps_existing_web_app_query_params():
    keyboard = build_start_keyboard("https://app.example/path?ref=bot")

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://app.example/path?ref=bot&v=ui-3"


def test_start_keyboard_is_hidden_without_https_url():
    assert build_start_keyboard("http://localhost:5173") is None


def test_reply_keyboard_uses_english_check_strategy_button():
    keyboard = build_reply_keyboard()

    assert keyboard.keyboard[0][0].text == "Check strategy"
