from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, ping_database
from app.modules.auth.router import router as auth_router
from app.modules.auth.service import seed_super_admin
from app.modules.workspaces.router import router as workspaces_router

settings = get_settings()
tags_metadata = [
    {
        "name": "auth",
        "description": "Telegram authentication, current user profile, and user workspace access.",
    },
    {
        "name": "workspaces",
        "description": "Workspace management and member administration for authorized users.",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await ping_database()
    await seed_super_admin()
    yield
    await engine.dispose()


app = FastAPI(
    title="Helpers System API",
    description="Backend API for Telegram Mini App authorization and workspace management.",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple application marker."""
    return {"message": "Helpers System API"}


@app.get(
    "/health/db",
    summary="Check database connectivity",
    description="Runs a lightweight database ping and returns API health status.",
)
async def database_health() -> dict[str, str]:
    """Verify that PostgreSQL is reachable."""
    await ping_database()
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(workspaces_router)
