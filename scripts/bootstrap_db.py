"""Create the app role/database using an existing PostgreSQL administrator."""
import os
import sys
from urllib.parse import unquote, urlparse

import psycopg
from psycopg import sql

from app.config import Settings
from app.db import Database


def provision(admin_url: str, app_url: str):
    parsed = urlparse(app_url)
    role, password, database = unquote(parsed.username or ""), unquote(parsed.password or ""), unquote(parsed.path.lstrip("/"))
    if not role or not password or not database:
        raise ValueError("В DATABASE_URL нужны пользователь, пароль и имя базы")
    admin = urlparse(admin_url)
    if (admin.hostname, admin.port or 5432) != (parsed.hostname, parsed.port or 5432):
        raise ValueError("ADMIN_DATABASE_URL и DATABASE_URL должны указывать на один сервер")
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(role)))
    Database(app_url).initialize()


def main():
    try:
        admin_url = os.getenv("ADMIN_DATABASE_URL", "")
        if not admin_url:
            raise ValueError("Задайте ADMIN_DATABASE_URL в .env или используйте python -m scripts.local_postgres setup")
        provision(admin_url, Settings.from_env().database_url)
        print("Учебная БД и пользователь готовы. Существующие пароли и данные не изменены.")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    except psycopg.Error:
        print("Не удалось подключиться к PostgreSQL или создать БД. Проверьте адрес, пароль и права администратора.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
