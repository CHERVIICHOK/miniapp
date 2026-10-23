import httpx
import pytest

from scripts.configure_telegram import configure
from tests.test_auth import TOKEN


def test_menu_button_is_saved_and_verified():
    menu = {}

    def handle(request):
        nonlocal menu
        if request.url.path == "/api/config": result = {"mode": "telegram"}
        elif request.url.path == "/api/health": result = {"status": "ok"}
        elif request.url.path.endswith("getMe"): result = {"ok": True, "result": {"username": "new_test_shop_bot"}}
        elif request.url.path.endswith("setChatMenuButton"):
            import json
            menu = json.loads(request.content)["menu_button"]
            result = {"ok": True, "result": True}
        elif request.url.path.endswith("getChatMenuButton"): result = {"ok": True, "result": menu}
        else: raise AssertionError("Unexpected request")
        return httpx.Response(200, json=result)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert configure(TOKEN, "https://test.example", client) == "new_test_shop_bot"
    assert menu["web_app"]["url"] == "https://test.example"


def test_demo_cannot_be_exposed_as_telegram_app():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"mode": "local"}))) as client:
        with pytest.raises(ValueError, match="APP_MODE=telegram"):
            configure(TOKEN, "https://test.example", client)


def test_plain_http_url_is_rejected():
    with pytest.raises(ValueError):
        configure(TOKEN, "http://localhost:8000")
