from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.handlers.start import DISCLAIMER, cmd_start, greeting
from bot.middlewares.access import AccessMiddleware


def test_greeting_contains_name_and_disclaimer() -> None:
    text = greeting("Женя")
    assert "Привет, Женя!" in text
    assert DISCLAIMER in text


def test_greeting_without_name() -> None:
    assert "Привет, друг!" in greeting(None)


async def test_cmd_start_answers() -> None:
    message = SimpleNamespace(from_user=SimpleNamespace(first_name="Женя"), answer=AsyncMock())
    await cmd_start(message)  # type: ignore[arg-type]
    message.answer.assert_awaited_once()
    assert "Привет, Женя!" in message.answer.await_args.args[0]


async def test_access_allows_whitelisted_user() -> None:
    handler = AsyncMock(return_value="ok")
    mw = AccessMiddleware(frozenset({1}))
    result = await mw(handler, object(), {"event_from_user": SimpleNamespace(id=1)})  # type: ignore[arg-type]
    assert result == "ok"
    handler.assert_awaited_once()


async def test_access_blocks_other_users() -> None:
    handler = AsyncMock()
    mw = AccessMiddleware(frozenset({1}))
    assert await mw(handler, object(), {"event_from_user": SimpleNamespace(id=2)}) is None  # type: ignore[arg-type]
    assert await mw(handler, object(), {}) is None  # type: ignore[arg-type]
    handler.assert_not_awaited()


async def test_access_denied_message_shows_user_id() -> None:
    from aiogram.types import Chat, Message

    handler = AsyncMock()
    mw = AccessMiddleware(frozenset({1}))
    message = Message.model_construct(chat=Chat.model_construct(id=2, type="private"))
    answer = AsyncMock()
    object.__setattr__(message, "answer", answer)
    await mw(handler, message, {"event_from_user": SimpleNamespace(id=2)})  # type: ignore[arg-type]
    handler.assert_not_awaited()
    answer.assert_awaited_once()
    assert "2" in answer.await_args.args[0]
