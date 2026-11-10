import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Config:
    bot_token: str
    superadmin_id: int | None
    webapp_domain: str
    chat_id: int | None
    data_dir: Path
    timezone: str

    @property
    def webapp_url(self) -> str:
        return f"https://{self.webapp_domain}"


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    token = env.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is required")
    return Config(
        bot_token=token,
        superadmin_id=int(env["SUPERADMIN_ID"]) if env.get("SUPERADMIN_ID") else None,
        webapp_domain=env.get("WEBAPP_DOMAIN", "localhost"),
        chat_id=int(env["CHAT_ID"]) if env.get("CHAT_ID") else None,
        data_dir=Path(env.get("DATA_DIR", "data")),
        timezone=env.get("TZ", "Europe/Moscow"),
    )
