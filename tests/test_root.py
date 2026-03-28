import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Helpers System API"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_db(client: AsyncClient) -> None:
    response = await client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
