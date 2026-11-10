import hashlib
import hmac
import time
import urllib.parse

import pytest

from bot.webapp.auth import AuthError, validate_init_data

TOKEN = "123:fake"


def make_init_data(pairs: dict[str, str], token: str = TOKEN) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    pairs = dict(pairs, hash=signature)
    return urllib.parse.urlencode(pairs)


def test_valid_init_data():
    pairs = {"query_id": "AA", "user": '{"id":42}', "auth_date": str(int(time.time()))}
    result = validate_init_data(make_init_data(pairs), TOKEN)
    assert result["query_id"] == "AA"
    assert "hash" not in result


def test_tampered_data_raises():
    pairs = {"query_id": "AA", "auth_date": str(int(time.time()))}
    good = make_init_data(pairs)
    tampered = good.replace("AA", "BB")
    with pytest.raises(AuthError):
        validate_init_data(tampered, TOKEN)


def test_wrong_token_raises():
    pairs = {"auth_date": str(int(time.time()))}
    with pytest.raises(AuthError):
        validate_init_data(make_init_data(pairs), "999:other")


def test_expired_raises():
    pairs = {"auth_date": str(int(time.time()) - 90000)}
    with pytest.raises(AuthError, match="expired"):
        validate_init_data(make_init_data(pairs), TOKEN)


def test_missing_hash_raises():
    with pytest.raises(AuthError):
        validate_init_data("auth_date=123", TOKEN)
