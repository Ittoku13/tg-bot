async def is_admin(bot, chat_id: int, user_id: int,
                   superadmin_id: int | None) -> bool:
    if superadmin_id is not None and user_id == superadmin_id:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception:
        return False
    return member.status in {"creator", "administrator"}
