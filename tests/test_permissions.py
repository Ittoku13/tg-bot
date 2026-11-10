import asyncio

import pytest

from bot.services.permissions import is_admin


class Member:
    def __init__(self, status):
        self.status = status


class Bot:
    def __init__(self, status):
        self.status = status

    async def get_chat_member(self, chat_id, user_id):
        if self.status == "raise":
            raise RuntimeError("telegram error")
        return Member(self.status)


def test_superadmin_always_admin():
    assert asyncio.run(is_admin(Bot("member"), 1, 7, 7)) is True


def test_admin_status():
    assert asyncio.run(is_admin(Bot("administrator"), 1, 42, 7)) is True
    assert asyncio.run(is_admin(Bot("creator"), 1, 42, 7)) is True


def test_member_not_admin():
    assert asyncio.run(is_admin(Bot("member"), 1, 42, 7)) is False


def test_api_error_is_not_admin():
    assert asyncio.run(is_admin(Bot("raise"), 1, 42, 7)) is False


def test_no_superadmin_configured():
    assert asyncio.run(is_admin(Bot("member"), 1, 42, None)) is False
