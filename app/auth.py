import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request

from app.config import Settings


def validate_init_data(raw: str, token: str, max_age: int, now: int | None = None) -> int:
    """Validate Telegram's bot-token HMAC before trusting any user fields."""
    try:
        if not raw or len(raw) > 8192:
            raise ValueError
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=30)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError
        received_hash = data.pop("hash")
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            raise ValueError
        timestamp = int(data["auth_date"])
        current = int(time.time()) if now is None else now
        if timestamp > current + 30 or current - timestamp > max_age:
            raise ValueError
        user_id = json.loads(data["user"])["id"]
        if type(user_id) is not int or not 0 < user_id < 2**63:
            raise ValueError
        return user_id
    except (ValueError, KeyError, TypeError, OverflowError):
        raise HTTPException(401, "Откройте приложение заново через меню Telegram-бота.") from None


def current_user(request: Request) -> str:
    settings: Settings = request.app.state.settings
    if settings.mode == "telegram":
        user_id = validate_init_data(
            request.headers.get("X-Telegram-Init-Data", ""),
            settings.bot_token,
            settings.init_data_max_age,
        )
        return f"telegram:{user_id}"
    # Local demo must not silently turn into a shared public account via a tunnel.
    host = request.url.hostname
    peer = request.client.host if request.client else ""
    proxy_headers = {"forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "cf-connecting-ip"}
    if host not in {"localhost", "127.0.0.1", "::1", "testserver"} or peer not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "Локальный режим доступен только на этом компьютере.")
    if any(header in request.headers for header in proxy_headers):
        raise HTTPException(403, "Для HTTPS-туннеля используйте APP_MODE=telegram.")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Недопустимый источник запроса.")
    return "local:demo"
