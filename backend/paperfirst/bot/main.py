import asyncio
import logging
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from paperfirst.core.config import get_settings


logger = logging.getLogger(__name__)


def is_https_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def build_start_keyboard(web_app_url: str) -> InlineKeyboardMarkup | None:
    if not is_https_url(web_app_url):
        return None

    button = InlineKeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=web_app_url))

    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def build_start_text(web_app_url: str) -> str:
    text = "Paper First проверяет стратегию до депозита: комиссии, слиппедж, просадка и базовый вердикт."
    if is_https_url(web_app_url):
        return text
    return f"{text}\n\nЛокальный Mini App открыт отдельно: {web_app_url}\nДля кнопки внутри Telegram нужен публичный HTTPS URL."


async def start(message: Message) -> None:
    settings = get_settings()
    await message.answer(
        build_start_text(settings.telegram_web_app_url),
        reply_markup=build_start_keyboard(settings.telegram_web_app_url),
    )


async def open_strategy(message: Message) -> None:
    settings = get_settings()
    await message.answer(
        build_start_text(settings.telegram_web_app_url),
        reply_markup=build_start_keyboard(settings.telegram_web_app_url),
    )


async def echo_document(message: Message) -> None:
    await message.answer("Пока MVP принимает стратегию в Mini App как JSON. Загрузка файлов будет следующим шагом.")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("PAPERFIRST_TELEGRAM_BOT_TOKEN is required")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.message.register(start, CommandStart())
    dispatcher.message.register(open_strategy, F.text == "Проверить стратегию")
    dispatcher.message.register(echo_document, F.document)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
