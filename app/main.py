import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import current_user
from app.config import ROOT, Settings
from app.db import Database
from app.models import OrderInput

logger = logging.getLogger(__name__)
DATABASE_ERROR = "PostgreSQL недоступен или не настроен. Проверьте запуск сервера, DATABASE_URL и выполните python -m scripts.init_db."


def create_app(settings: Settings | None = None, initialize: bool = True):
    settings = settings or Settings.from_env()
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        if initialize:
            try:
                database.initialize()
            except psycopg.Error:
                logger.error(DATABASE_ERROR)
        yield

    app = FastAPI(title="Тёплое зерно", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Request, exc: psycopg.Error):
        logger.error("Ошибка операции PostgreSQL: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": DATABASE_ERROR})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Проверьте имя, телефон и состав заказа. Количество товара — от 1 до 99."})

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        with database.connect() as conn:
            conn.execute("SELECT 1 FROM products LIMIT 1")
        return {"status": "ok", "database": "postgresql", "mode": settings.mode}

    @app.get("/api/config")
    def public_config():
        return {"mode": settings.mode}

    @app.get("/api/products")
    def products(user: str = Depends(current_user)):
        return database.products()

    @app.post("/api/orders", status_code=201)
    def create_order(payload: OrderInput, user: str = Depends(current_user)):
        return database.create_order(user, payload)

    @app.get("/api/orders")
    def orders(user: str = Depends(current_user)):
        return database.orders(user)

    @app.get("/api/orders/{order_id}")
    def order(order_id: int, user: str = Depends(current_user)):
        return database.order(order_id, user)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "static/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
