import hashlib
import hmac
import time
import urllib.parse


class AuthError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str,
                       max_age_seconds: int = 86400) -> dict[str, str]:
    pairs = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise AuthError("no hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("bad hash")
    auth_date = int(pairs.get("auth_date", "0") or 0)
    if int(time.time()) - auth_date > max_age_seconds:
        raise AuthError("expired")
    return pairs
