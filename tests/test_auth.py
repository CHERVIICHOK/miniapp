import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import validate_init_data
from app.config import Settings
from app.main import create_app

TOKEN = "123456789:test-token-only"


def signed_data(user=101, timestamp=1_800_000_000):
    values = {"auth_date": str(timestamp), "query_id": "test-query", "user": json.dumps({"id": user, "first_name": "Тест"}, ensure_ascii=False, separators=(",", ":"))}
    key = hmac.digest(b"WebAppData", TOKEN.encode(), "sha256")
    values["hash"] = hmac.new(key, "\n".join(f"{k}={values[k]}" for k in sorted(values)).encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_telegram_signature():
    assert validate_init_data(signed_data(), TOKEN, 3600, now=1_800_000_001) == 101


@pytest.mark.parametrize("raw", ["", "hash=x", "not-query-data", signed_data()+"&auth_date=1", signed_data().replace("auth_date=1800000000", "auth_date=1800000001"), signed_data(user="101"), signed_data(user=True), signed_data(user=0), signed_data(user=2**63)])
def test_invalid_telegram_data(raw):
    with pytest.raises(HTTPException) as error:
        validate_init_data(raw, TOKEN, 3600, now=1_800_000_001)
    assert error.value.status_code == 401


@pytest.mark.parametrize("now", [1_800_003_601, 1_799_999_900])
def test_expired_or_future_signature(now):
    with pytest.raises(HTTPException):
        validate_init_data(signed_data(), TOKEN, 3600, now=now)


def test_local_mode_cannot_be_used_through_tunnel():
    app = create_app(Settings("postgresql://test@localhost/test"), initialize=False)
    with TestClient(app) as client:
        for headers in [{"Host": "public.trycloudflare.com"}, {"X-Forwarded-For": "1.2.3.4"}, {"Origin": "https://other.example"}]:
            assert client.get("/api/products", headers=headers).status_code == 403


def test_telegram_mode_never_falls_back_to_demo():
    app = create_app(Settings("postgresql://test@localhost/test", mode="telegram", bot_token=TOKEN), initialize=False)
    with TestClient(app) as client:
        assert client.get("/api/orders").status_code == 401
        assert client.get("/api/products").status_code == 401


def test_telegram_requires_token():
    with pytest.raises(ValueError):
        Settings("postgresql://test@localhost/test", mode="telegram")
