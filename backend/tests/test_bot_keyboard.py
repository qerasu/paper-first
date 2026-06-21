from paperfirst.bot.main import build_bot_commands, build_start_keyboard


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


def test_bot_command_menu_starts_with_check_strategy():
    commands = build_bot_commands()

    assert len(commands) == 1
    assert commands[0].command == "check_strategy"
    assert commands[0].description == "Check strategy"
