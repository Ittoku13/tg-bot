import json
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from bot.config import Config
from bot.personality import Personality
from bot.services.rating import format_top
from bot.storage import Storage
from bot.webapp.auth import AuthError, validate_init_data

MAX_KNOWN_USERS = 200


class CharacterPayload(BaseModel):
    character: str


class RolePayload(BaseModel):
    role_name: str = Field(min_length=1, max_length=64)


class PickTimePayload(BaseModel):
    pick_time: str


class EnabledPayload(BaseModel):
    enabled: bool


class MockPayload(BaseModel):
    mock_chance: int = Field(ge=0, le=100)
    mock_cooldown_min: int = Field(ge=0)
    mock_mode: str


class MockTargetsPayload(BaseModel):
    user_ids: list[int]


def create_app(bot, storage: Storage, personality: Personality,
               config: Config) -> FastAPI:
    app = FastAPI(title="tg-bot admin")

    async def require_admin(request: Request) -> int:
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        try:
            pairs = validate_init_data(init_data, config.bot_token)
        except AuthError:
            raise HTTPException(401, "invalid init data")
        user = json.loads(pairs.get("user", "{}"))
        user_id = int(user.get("id", 0))
        if user_id == config.superadmin_id:
            return user_id
        if config.chat_id is None:
            raise HTTPException(403, "no chat configured")
        try:
            member = await bot.get_chat_member(config.chat_id, user_id)
        except Exception:
            raise HTTPException(403, "admin check failed")
        if member.status not in {"creator", "administrator"}:
            raise HTTPException(403, "not an admin")
        return user_id

    def current_settings():
        return storage.settings(config.chat_id)

    def ok(settings):
        return {"settings": asdict(settings)}

    @app.get("/api/state")
    async def state(_: int = Depends(require_admin)):
        s = current_settings()
        users = storage.list_users(config.chat_id)[:MAX_KNOWN_USERS]
        top_rows = [(u, c) for uid, c in storage.top(config.chat_id, None)
                    for u in users if u.user_id == uid]
        return {
            "settings": asdict(s),
            "rating_top": format_top(top_rows, "all", s.role_name) if top_rows else "",
            "known_users": [
                {"user_id": u.user_id, "display_name": u.display_name,
                 "username": u.username} for u in users
            ],
            "mock_targets": sorted(storage.mock_targets(config.chat_id)),
        }

    @app.post("/api/character")
    async def character(payload: CharacterPayload, _: int = Depends(require_admin)):
        return _update(character=payload.character)

    @app.post("/api/role")
    async def role(payload: RolePayload, _: int = Depends(require_admin)):
        return _update(role_name=payload.role_name.strip())

    @app.post("/api/pick_time")
    async def pick_time(payload: PickTimePayload, _: int = Depends(require_admin)):
        return _update(pick_time=payload.pick_time)

    @app.post("/api/auto_pick")
    async def auto_pick(payload: EnabledPayload, _: int = Depends(require_admin)):
        return _update(auto_pick_enabled=payload.enabled)

    @app.post("/api/exclude_last")
    async def exclude_last(payload: EnabledPayload, _: int = Depends(require_admin)):
        return _update(exclude_last=payload.enabled)

    @app.post("/api/mock")
    async def mock(payload: MockPayload, _: int = Depends(require_admin)):
        return _update(mock_chance=payload.mock_chance,
                       mock_cooldown_min=payload.mock_cooldown_min,
                       mock_mode=payload.mock_mode)

    @app.post("/api/mock_targets")
    async def mock_targets(payload: MockTargetsPayload, _: int = Depends(require_admin)):
        storage.replace_mock_targets(config.chat_id, payload.user_ids)
        return ok(current_settings())

    @app.post("/api/reset_rating")
    async def reset_rating(_: int = Depends(require_admin)):
        storage.clear_picks(config.chat_id)
        return {"ok": True}

    def _update(**fields):
        try:
            settings = storage.update_settings(config.chat_id, **fields)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return ok(settings)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
