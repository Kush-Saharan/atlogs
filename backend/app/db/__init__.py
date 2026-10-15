"""Database package: async connection pool + health check, schema, and seeding.

`app.db` is a package (this file) so that `app.db.seed` and `app.db.schema.sql`
can live alongside the connection-pool helpers used by the API health check.
"""

from __future__ import annotations

import asyncpg

from ..config import get_settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the shared connection pool (idempotent)."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
            # Fail fast on an unreachable DB (e.g. wrong host / IPv6-only direct
            # connection) instead of hanging the whole startup for ~60s.
            timeout=10,
        )
    return _pool


async def close_pool() -> None:
    """Close the shared connection pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def check_database() -> dict[str, object]:
    """Query Postgres to confirm connectivity and pgvector availability."""
    pool = get_pool()
    async with pool.acquire() as conn:
        version: str = await conn.fetchval("SELECT version();")
        pgvector_installed: bool = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');"
        )
    return {
        "connected": True,
        "server_version": version.split(" ", 2)[1] if version else None,
        "pgvector_installed": bool(pgvector_installed),
    }
