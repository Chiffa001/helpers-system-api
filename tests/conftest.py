from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.main as main_module
from app.core.config import get_settings
from app.core.database import get_db_session
from app.models import Base

settings = get_settings()
_test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_session_factory = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

app = main_module.app


@pytest.fixture(autouse=True)
def _set_test_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY")
    get_settings.cache_clear()


async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
    async with _session_factory() as session:
        yield session


app.dependency_overrides[get_db_session] = _override_get_db_session


async def _override_ping_database() -> None:
    async with _test_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


main_module.ping_database = _override_ping_database


@pytest.fixture(scope="session", autouse=True)
async def _ensure_test_schema() -> None:
    async with _test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session")
async def client() -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with _session_factory() as session:
        yield session
