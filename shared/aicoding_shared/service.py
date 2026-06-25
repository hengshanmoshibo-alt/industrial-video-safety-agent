from contextlib import asynccontextmanager
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aicoding_shared.config import get_settings
from aicoding_shared.db import init_db


def create_service_app(name: str, bootstrap: Callable[[], None] | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        if bootstrap:
            bootstrap()
        yield

    app = FastAPI(title=name, version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "service": name}

    return app

