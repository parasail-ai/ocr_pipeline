from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import make_url
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()


def _build_async_url_and_args() -> tuple[URL, dict[str, Any]]:
    url = make_url(settings.database_url)
    query = dict(url.query)
    connect_args: dict[str, Any] = {}

    if url.get_backend_name() == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    ssl_mode = query.pop("sslmode", None)
    if ssl_mode:
        connect_args["ssl"] = ssl.create_default_context()

    if query != url.query:
        url = url.set(query=query)

    return url, connect_args


async_url, async_connect_args = _build_async_url_and_args()

engine = create_async_engine(async_url, connect_args=async_connect_args, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
