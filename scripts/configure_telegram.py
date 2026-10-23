import argparse
import os
import sys
from urllib.parse import urlparse

import httpx
from dotenv import set_key

from app.config import ROOT


def configure(token: str, url: str, client=None):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("Нужен HTTPS-адрес MiniApp без параметров, секретов и фрагмента")
    if not token or ":" not in token:
        raise ValueError("Добавьте BOT_TOKEN нового бота в .env")
    owns_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        # The URL must serve the Telegram mode, never the shared local demo.
        config_response = client.get(url.rstrip("/") + "/api/config")
        config_response.raise_for_status()
        if config_response.json().get("mode") != "telegram":
            raise ValueError("Перед настройкой кнопки перезапустите сервер с APP_MODE=telegram")
        health_response = client.get(url.rstrip("/") + "/api/health")
        health_response.raise_for_status()
        bot_url = f"https://api.telegram.org/bot{token}/"
        response = client.get(bot_url + "getMe")
        response.raise_for_status()
        identity = response.json()
        if not identity.get("ok"):
            raise ValueError("Telegram отклонил токен")
        menu = {"type": "web_app", "text": "Открыть магазин", "web_app": {"url": url.rstrip("/")}}
        result = client.post(bot_url + "setChatMenuButton", json={"menu_button": menu})
        result.raise_for_status()
        if not result.json().get("ok"):
            raise ValueError("Telegram не сохранил кнопку меню")
        check = client.get(bot_url + "getChatMenuButton")
        check.raise_for_status()
        if check.json().get("result") != menu:
            raise ValueError("Кнопка меню не прошла проверку")
        return identity["result"]["username"]
    finally:
        if owns_client: client.close()


def main():
    parser = argparse.ArgumentParser(description="Настройка кнопки MiniApp без polling")
    parser.add_argument("--url", default=os.getenv("MINIAPP_URL", ""))
    args = parser.parse_args()
    try:
        username = configure(os.getenv("BOT_TOKEN", ""), args.url)
        set_key(str(ROOT / ".env"), "MINIAPP_URL", args.url.rstrip("/"))
        print(f"Кнопка проверена. Откройте https://t.me/{username}, нажмите Start, затем «Открыть магазин».")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    except (httpx.HTTPError, KeyError, TypeError):
        print("Не удалось настроить Telegram. Проверьте токен, HTTPS-туннель и доступ к api.telegram.org.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
