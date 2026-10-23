import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str
    mode: str = "local"
    bot_token: str = ""
    init_data_max_age: int = 3600

    def __post_init__(self):
        if self.mode not in {"local", "telegram"}:
            raise ValueError("APP_MODE должен быть local или telegram")
        if self.mode == "telegram" and not self.bot_token:
            raise ValueError("Для APP_MODE=telegram задайте BOT_TOKEN в .env")
        if not self.database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL должен указывать на PostgreSQL")
        if self.init_data_max_age <= 0:
            raise ValueError("INIT_DATA_MAX_AGE_SECONDS должен быть положительным")

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.getenv("DATABASE_URL", "postgresql://teploe_zerno@127.0.0.1:5432/teploe_zerno"),
            mode=os.getenv("APP_MODE", "local"),
            bot_token=os.getenv("BOT_TOKEN", ""),
            init_data_max_age=int(os.getenv("INIT_DATA_MAX_AGE_SECONDS", "3600")),
        )
