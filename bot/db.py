import asyncpg
from typing import Optional
from config import DATABASE_URL

_pool: Optional[asyncpg.pool.Pool] = None

async def init_db():
    """Initializes the database connection pool."""
    global _pool
    if not _pool:
        _pool = await asyncpg.create_pool(DATABASE_URL)
        print("Database pool created.")

async def close_db():
    """Closes the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        print("Database pool closed.")

async def fetchrow(query, *args):
    """Fetches a single row from the database."""
    async with _pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetch(query, *args):
    """Fetches multiple rows from the database."""
    async with _pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def execute(query, *args):
    """
    Executes a command (INSERT, UPDATE, DELETE) within a transaction.
    This ensures the data is properly saved (committed) to the database.
    """
    async with _pool.acquire() as conn:
        async with conn.transaction():
            return await conn.execute(query, *args)
