from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.personality import Personality
from bot.services.rating import PERIODS, format_top, period_keys
from bot.storage import Storage, UserRow


def mystats_text(user: UserRow, role_name: str, count: int, last: datetime | None) -> str:
    last_str = last.date().isoformat() if last else "—"
    return (f"{user.display_name}, звание «{role_name}» получено раз: {count}.\n"
            f"Последний раз: {last_str}")


def _period_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Всё время", callback_data="rating:all"),
         InlineKeyboardButton(text="Месяц", callback_data="rating:month"),
         InlineKeyboardButton(text="Неделя", callback_data="rating:week")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_game_router(storage: Storage, personality: Personality) -> Router:
    router = Router()

    async def send_rating(target, period: str) -> None:
        is_callback = isinstance(target, CallbackQuery)
        chat_id = target.message.chat.id if is_callback else target.chat.id
        settings = storage.settings(chat_id)
        users = {u.user_id: u for u in storage.list_users(chat_id)}
        entries = [(users[uid], c) for uid, c in storage.top(chat_id, PERIODS[period])
                   if uid in users]
        if not entries:
            text = personality.phrase(settings.character, "rating_empty",
                                      role=settings.role_name)
        else:
            text = format_top(entries, period, settings.role_name)
        if is_callback:
            await target.message.edit_text(text, reply_markup=_period_kb())
        else:
            await target.answer(text, reply_markup=_period_kb())

    @router.message(Command("rating"))
    async def cmd_rating(message: Message) -> None:
        await send_rating(message, "all")

    @router.callback_query(F.data.startswith("rating:"))
    async def cb_rating(query: CallbackQuery) -> None:
        period = query.data.split(":", 1)[1]
        if period not in PERIODS:
            await query.answer("Неизвестный период")
            return
        await send_rating(query, period)
        await query.answer()

    @router.message(Command("mystats"))
    async def cmd_mystats(message: Message) -> None:
        chat_id = message.chat.id
        settings = storage.settings(chat_id)
        user_id = message.from_user.id
        users = {u.user_id: u for u in storage.list_users(chat_id)}
        user = users.get(user_id) or UserRow(user_id, message.from_user.username,
                                             message.from_user.first_name, None)
        count = storage.count_for(chat_id, user_id, None)
        last = storage.last_pick_for(chat_id, user_id)
        await message.answer(mystats_text(user, settings.role_name, count, last))

    return router
