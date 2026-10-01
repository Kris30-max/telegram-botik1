from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")

DISCLAIMER = (
    "⚠️ Я не заменяю врача. При болях, хронических заболеваниях или беременности "
    "проконсультируйтесь со специалистом."
)


def greeting(first_name: str | None) -> str:
    name = first_name or "друг"
    return f"Привет, {name}! Я FitCoach — твой помощник по питанию и тренировкам.\n\n{DISCLAIMER}"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    first_name = message.from_user.first_name if message.from_user else None
    await message.answer(greeting(first_name))
