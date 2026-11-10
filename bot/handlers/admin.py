from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message, WebAppInfo)

from bot.config import Config
from bot.personality import Personality
from bot.services.permissions import is_admin
from bot.storage import Storage


def _char_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Цензурный", callback_data="char:clean"),
        InlineKeyboardButton(text="18+", callback_data="char:adult"),
    ]])


def build_admin_router(bot, storage: Storage, personality: Personality,
                       config: Config) -> Router:
    router = Router()

    async def admin_only(message: Message) -> bool:
        return await is_admin(bot, message.chat.id, message.from_user.id,
                              config.superadmin_id)

    @router.message(Command("start", "help"))
    async def cmd_help(message: Message) -> None:
        settings = storage.settings(message.chat.id)
        await message.answer(personality.phrase(settings.character, "help"))

    @router.message(Command("character"))
    async def cmd_character(message: Message) -> None:
        settings = storage.settings(message.chat.id)
        if not await admin_only(message):
            await message.answer(personality.phrase(settings.character, "error"))
            return
        await message.answer("Характер бота:", reply_markup=_char_kb())

    @router.callback_query(F.data.startswith("char:"))
    async def cb_character(query: CallbackQuery) -> None:
        character = query.data.split(":", 1)[1]
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        if not await is_admin(bot, chat_id, user_id, config.superadmin_id):
            await query.answer("Только для админов", show_alert=True)
            return
        try:
            storage.update_settings(chat_id, character=character)
        except ValueError:
            await query.answer("Неизвестный характер", show_alert=True)
            return
        await query.answer("Характер: " + character)

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        settings = storage.settings(message.chat.id)
        if not await admin_only(message):
            await message.answer(personality.phrase(settings.character, "error"))
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Открыть админку",
                                 web_app=WebAppInfo(url=config.webapp_url)),
        ]])
        await message.answer("Админка:", reply_markup=kb)

    return router
