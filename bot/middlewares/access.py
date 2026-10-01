import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

logger = logging.getLogger(__name__)


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
            return None
        return await handler(event, data)
