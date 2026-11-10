import random

from bot.storage import UserRow


def pick_candidate(users: list[UserRow], last_user_id: int | None,
                   exclude_last: bool, rng: random.Random) -> UserRow | None:
    pool = list(users)
    if exclude_last and last_user_id is not None and len(pool) > 1:
        pool = [u for u in pool if u.user_id != last_user_id]
    if not pool:
        return None
    return rng.choice(pool)
