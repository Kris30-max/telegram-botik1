import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_settings
from bot.db.base import create_engine
from bot.handlers import start
from bot.logging import setup_logging
from bot.middlewares.access import AccessMiddleware

logger = logging.getLogger(__name__)


def build_dispatcher(allowed_user_ids: frozenset[int]) -> Dispatcher:
    dp = Dispatcher()
    access = AccessMiddleware(allowed_user_ids)
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)
    dp.include_router(start.router)
    return dp


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(settings.allowed_user_ids)

    logger.info("allowed user ids: %s", sorted(settings.allowed_user_ids))
    logger.info("starting polling")
    try:
        # start_polling сам обрабатывает SIGTERM/SIGINT и закрывает HTTP-сессию бота.
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await engine.dispose()
        logger.info("stopped")


if __name__ == "__main__":
    asyncio.run(main())
