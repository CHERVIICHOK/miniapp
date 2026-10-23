import sys

import psycopg

from app.config import Settings
from app.db import Database


def main():
    try:
        database = Database(Settings.from_env().database_url)
        database.initialize()
        print(f"База готова. Товаров: {len(database.products())}. Существующие заказы сохранены.")
    except (psycopg.Error, ValueError):
        print("Не удалось инициализировать PostgreSQL. Проверьте сервер и DATABASE_URL в .env.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
