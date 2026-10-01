import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, User

logger = logging.getLogger(__name__)


def access_denied_text(user_id: int) -> str:
    return (
        "Это приватный бот, доступ закрыт.\n"
        f"Ваш Telegram ID: <code>{user_id}</code> — владелец может добавить его "
        "в ALLOWED_USER_IDS."
    )


class AccessMiddleware(BaseMiddleware):
    """Пропускает апдейты только от пользователей из белого списка."""

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self.allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.id not in self.allowed_user_ids:
            logger.warning("access denied for user_id=%s", user.id if user else None)
            if user is not None and isinstance(event, Message):
                await event.answer(access_denied_text(user.id))
            return None
        return await handler(event, data)
