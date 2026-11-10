from bot.storage import UserRow

PERIODS: dict[str, int | None] = {"all": None, "month": 30, "week": 7}
PERIOD_LABELS: dict[str, str] = {
    "all": "за всё время",
    "month": "за месяц",
    "week": "за неделю",
}


def period_keys() -> list[str]:
    return list(PERIODS)


def format_top(entries: list[tuple[UserRow, int]], period: str, role_name: str) -> str:
    label = PERIOD_LABELS[period]
    lines = [f"Топ по званию «{role_name}» {label}:"]
    for i, (u, count) in enumerate(entries, 1):
        lines.append(f"{i}. {u.display_name} — {count}")
    return "\n".join(lines)
