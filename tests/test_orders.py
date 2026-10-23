import os
import time
import uuid
from urllib.parse import quote

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.models import OrderInput
from tests.test_auth import TOKEN, signed_data


@pytest.fixture
def database():
    base = os.getenv("TEST_DATABASE_URL", Settings.from_env().database_url)
    schema = "miniapp_test_" + uuid.uuid4().hex
    with psycopg.connect(base, connect_timeout=3, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    url = base + ("&" if "?" in base else "?") + "options=" + quote("-csearch_path=" + schema)
    db = Database(url)
    try:
        db.initialize()
        yield db
    finally:
        with psycopg.connect(base, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def client(database):
    with TestClient(create_app(Settings(database.url))) as session:
        yield session


def payload(product_id=1):
    return {"name": "Учебный покупатель", "phone": "+7 (999) 000-00-00", "items": [{"product_id": product_id, "quantity": 2}]}


def test_checkout_and_persistence_after_new_app(client, database):
    products = client.get("/api/products").json()
    assert len(products) == 12
    order = client.post("/api/orders", json=payload(products[0]["id"]))
    assert order.status_code == 201
    saved = order.json()
    assert saved["total"] == 2 * products[0]["price"]
    assert saved["phone"] == "+79990000000"
    with TestClient(create_app(Settings(database.url))) as restarted:
        assert restarted.get("/api/orders").json()[0] == saved
        assert restarted.get(f"/api/orders/{saved['id']}").json() == saved
    database.initialize()
    assert len(database.products()) == 12
    assert len(database.orders("local:demo")) == 1


@pytest.mark.parametrize("change", ["empty", "phone", "name", "zero", "negative", "too_many", "float", "boolean", "unknown", "price", "total"])
def test_rejects_invalid_orders_without_writes(client, database, change):
    data = payload()
    if change == "empty": data["items"] = []
    elif change == "phone": data["phone"] = "invalid1234567890"
    elif change == "name": data["name"] = " "
    elif change in {"zero", "negative", "too_many", "float", "boolean"}:
        data["items"][0]["quantity"] = {"zero": 0, "negative": -1, "too_many": 100, "float": 1.5, "boolean": True}[change]
    elif change == "unknown": data["items"][0]["product_id"] = 99999999
    elif change == "price": data["items"][0]["price"] = 1
    elif change == "total": data["total"] = 1
    assert client.post("/api/orders", json=data).status_code == 422
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM orders").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM order_items").fetchone()["n"] == 0


def test_transaction_rolls_back_if_line_insert_fails(client, database):
    with database.connect() as conn:
        conn.execute("CREATE FUNCTION reject_test_item() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test failure'; END $$")
        conn.execute("CREATE TRIGGER reject_item BEFORE INSERT ON order_items FOR EACH ROW EXECUTE FUNCTION reject_test_item()")
    assert client.post("/api/orders", json=payload()).status_code == 503
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM orders").fetchone()["n"] == 0


def test_order_snapshots_survive_catalog_changes(client, database):
    order = client.post("/api/orders", json=payload()).json()
    with database.connect() as conn:
        conn.execute("UPDATE products SET name='Новое название', price=1 WHERE id=1")
    assert client.get(f"/api/orders/{order['id']}").json() == order


def test_telegram_users_cannot_read_each_others_orders(database):
    app = create_app(Settings(database.url, mode="telegram", bot_token=TOKEN))
    a = {"X-Telegram-Init-Data": signed_data(user=101, timestamp=int(time.time()))}
    b = {"X-Telegram-Init-Data": signed_data(user=202, timestamp=int(time.time()))}
    with TestClient(app) as client:
        created = client.post("/api/orders", json=payload(), headers=a)
        assert created.status_code == 201
        assert len(client.get("/api/orders", headers=a).json()) == 1
        assert client.get("/api/orders", headers=b).json() == []
        assert client.get(f"/api/orders/{created.json()['id']}", headers=b).status_code == 404


def test_duplicate_products_are_merged(client):
    data = payload()
    data["items"].append({"product_id": 1, "quantity": 3})
    order = client.post("/api/orders", json=data).json()
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 5


def test_database_unavailable_has_clear_error():
    app = create_app(Settings("postgresql://missing@127.0.0.1:1/missing"), initialize=False)
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 503
        assert "PostgreSQL" in response.json()["detail"]
        assert "missing@" not in response.text
