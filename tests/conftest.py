from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db_session
from app.main import app


def _make_null_pool_session() -> async_sessionmaker[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


_session_factory = _make_null_pool_session()


async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
    async with _session_factory() as session:
        yield session


app.dependency_overrides[get_db_session] = _override_get_db_session


@pytest.fixture(scope="session")
async def client() -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
