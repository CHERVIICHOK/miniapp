import json
from collections import defaultdict

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from app.config import ROOT
from app.models import OrderInput


class Database:
    def __init__(self, url: str):
        self.url = url

    def connect(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=3)

    def initialize(self):
        catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
        with self.connect() as conn:
            # Serialize schema/seed initialization when two backend instances start together.
            conn.execute("SELECT pg_advisory_xact_lock(76002401)")
            conn.execute((ROOT / "app/schema.sql").read_text(encoding="utf-8"))
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO products (code, category, name, variant, description, image, price) "
                    "VALUES (%(code)s, %(category)s, %(name)s, %(variant)s, %(description)s, %(image)s, %(price)s) "
                    "ON CONFLICT (code) DO NOTHING", catalog,
                )

    def products(self):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM products ORDER BY id").fetchall()

    @staticmethod
    def _order(conn, order_id: int, user_key: str):
        order = conn.execute("SELECT id, name, phone, total, status, created_at FROM orders WHERE id=%s AND user_key=%s", (order_id, user_key)).fetchone()
        if not order:
            raise HTTPException(404, "Заказ не найден.")
        order["items"] = conn.execute("SELECT product_id, name, variant, unit_price, quantity FROM order_items WHERE order_id=%s ORDER BY id", (order_id,)).fetchall()
        return order

    def create_order(self, user_key: str, payload: OrderInput):
        quantities = defaultdict(int)
        for item in payload.items:
            quantities[item.product_id] += item.quantity
        if any(q > 99 for q in quantities.values()):
            raise HTTPException(422, "Не более 99 единиц одного товара.")
        with self.connect() as conn:
            products = conn.execute("SELECT id, name, variant, price FROM products WHERE id = ANY(%s)", (list(quantities),)).fetchall()
            if len(products) != len(quantities):
                raise HTTPException(422, "Один из товаров больше не доступен. Обновите каталог.")
            total = sum(p["price"] * quantities[p["id"]] for p in products)
            order_id = conn.execute("INSERT INTO orders (user_key, name, phone, total) VALUES (%s, %s, %s, %s) RETURNING id", (user_key, payload.name, payload.phone, total)).fetchone()["id"]
            with conn.cursor() as cursor:
                cursor.executemany("INSERT INTO order_items (order_id, product_id, name, variant, unit_price, quantity) VALUES (%s,%s,%s,%s,%s,%s)", [(order_id, p["id"], p["name"], p["variant"], p["price"], quantities[p["id"]]) for p in products])
            return self._order(conn, order_id, user_key)

    def orders(self, user_key: str):
        with self.connect() as conn:
            rows = conn.execute("SELECT id, name, phone, total, status, created_at FROM orders WHERE user_key=%s ORDER BY created_at DESC, id DESC LIMIT 100", (user_key,)).fetchall()
            if rows:
                items = conn.execute("SELECT order_id, product_id, name, variant, unit_price, quantity FROM order_items WHERE order_id = ANY(%s) ORDER BY id", ([row["id"] for row in rows],)).fetchall()
                grouped = defaultdict(list)
                for item in items:
                    grouped[item.pop("order_id")].append(item)
                for row in rows:
                    row["items"] = grouped[row["id"]]
            return rows

    def order(self, order_id: int, user_key: str):
        with self.connect() as conn:
            return self._order(conn, order_id, user_key)
