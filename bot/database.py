import logging

import asyncpg

import config

log = logging.getLogger("db")
_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=config.DATABASE_URL,
        min_size=1,
        max_size=5,
        timeout=20.0,
        statement_cache_size=0,  # required for the Supabase pooler
    )
    log.info("connected to Supabase Postgres")


async def close_db() -> None:
    if _pool:
        await _pool.close()


def _p() -> asyncpg.Pool:
    assert _pool is not None, "init_db() was not called"
    return _pool


async def get_user_config(user_id: int) -> dict:
    """Returns the user's settings, creating the row (with default stop words) if needed."""
    async with _p().acquire() as conn:
        await conn.execute(
            "INSERT INTO user_settings (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id
        )
        row = await conn.fetchrow(
            "SELECT queries, stop_words, search_limit FROM user_settings WHERE user_id=$1",
            user_id,
        )
    return {
        "queries": list(row["queries"] or []),
        "stop_words": list(row["stop_words"] or []),
        "search_limit": row["search_limit"] or 3,
    }


async def set_queries(user_id: int, queries: list[str]) -> None:
    async with _p().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, queries) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET queries = EXCLUDED.queries, updated_at = now()
            """,
            user_id, queries,
        )


async def get_all_users_with_queries() -> list[dict]:
    async with _p().acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, queries, stop_words FROM user_settings "
            "WHERE cardinality(queries) > 0"
        )
    return [
        {"user_id": r["user_id"], "queries": list(r["queries"]), "stop_words": list(r["stop_words"] or [])}
        for r in rows
    ]


# ---------- seen ads ----------

async def filter_unseen(user_id: int, ad_ids: list[str]) -> set[str]:
    if not ad_ids:
        return set()
    async with _p().acquire() as conn:
        rows = await conn.fetch(
            "SELECT ad_id FROM seen_ads WHERE user_id=$1 AND ad_id = ANY($2::varchar[])",
            user_id, [str(a) for a in ad_ids],
        )
    return {str(a) for a in ad_ids} - {r["ad_id"] for r in rows}


async def add_seen_ads(user_id: int, ad_ids: list[str]) -> None:
    if not ad_ids:
        return
    async with _p().acquire() as conn:
        await conn.executemany(
            "INSERT INTO seen_ads (user_id, ad_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            [(user_id, str(a)) for a in ad_ids],
        )


async def cleanup_old_seen(days: int = 60) -> None:
    async with _p().acquire() as conn:
        await conn.execute(
            "DELETE FROM seen_ads WHERE created_at < now() - make_interval(days => $1)", days
        )


# ---------- seeded queries ----------

async def get_seeded(user_id: int) -> set[str]:
    async with _p().acquire() as conn:
        rows = await conn.fetch("SELECT query FROM seeded_queries WHERE user_id=$1", user_id)
    return {r["query"] for r in rows}


async def mark_seeded(user_id: int, query: str) -> None:
    async with _p().acquire() as conn:
        await conn.execute(
            "INSERT INTO seeded_queries (user_id, query) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id, query,
        )


async def prune_seeded(user_id: int, current_queries: list[str]) -> None:
    """Forget queries the user removed, so re-adding them later starts clean."""
    async with _p().acquire() as conn:
        await conn.execute(
            "DELETE FROM seeded_queries WHERE user_id=$1 AND NOT (query = ANY($2::text[]))",
            user_id, current_queries,
        )
