import asyncio
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from paperfirst.core.config import get_settings


logger = logging.getLogger(__name__)
WEB_APP_CACHE_BUSTER = "ui-3"
CHECK_STRATEGY_BUTTON = "Check strategy"


def is_https_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def versioned_web_app_url(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["v"] = WEB_APP_CACHE_BUSTER

    return urlunparse(parsed._replace(query=urlencode(query)))


def build_start_keyboard(web_app_url: str) -> InlineKeyboardMarkup | None:
    if not is_https_url(web_app_url):
        return None

    button = InlineKeyboardButton(text="Open Mini App", web_app=WebAppInfo(url=versioned_web_app_url(web_app_url)))

    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def build_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CHECK_STRATEGY_BUTTON)]],
        resize_keyboard=True,
    )


def build_start_text(web_app_url: str) -> str:
    text = "Paper First checks a strategy before deposit: fees, slippage, drawdown, and a basic verdict."
    if is_https_url(web_app_url):
        return text
    return f"{text}\n\nThe local Mini App is available separately: {web_app_url}\nA public HTTPS URL is required for the Telegram button."


async def start(message: Message):
    settings = get_settings()
    await message.answer(
        build_start_text(settings.telegram_web_app_url),
        reply_markup=build_reply_keyboard(),
    )


async def open_strategy(message: Message):
    settings = get_settings()
    await message.answer(
        build_start_text(settings.telegram_web_app_url),
        reply_markup=build_start_keyboard(settings.telegram_web_app_url),
    )


async def echo_document(message: Message):
    await message.answer("Open the Mini App to import a strategy from JSON, text, PDF, or image.")


async def fallback(message: Message):
    settings = get_settings()
    await message.answer(
        build_start_text(settings.telegram_web_app_url),
        reply_markup=build_start_keyboard(settings.telegram_web_app_url),
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("PAPERFIRST_TELEGRAM_BOT_TOKEN is required")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.message.register(start, CommandStart())
    dispatcher.message.register(open_strategy, F.text == CHECK_STRATEGY_BUTTON)
    dispatcher.message.register(echo_document, F.document)
    dispatcher.message.register(fallback)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
