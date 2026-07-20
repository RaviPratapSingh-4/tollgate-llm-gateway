from app.db import get_pool
from app.services.embeddings import embed

SIMILARITY_THRESHOLD = 0.85


async def find_cached_response(query: str) -> dict | None:
    vector = embed(query)
    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT response_text, model_used, 1 - (query_embedding <=> $1) AS similarity
        FROM cache_entries
        ORDER BY query_embedding <=> $1
        LIMIT 1
        """,
        vector,
    )

    if row and row["similarity"] >= SIMILARITY_THRESHOLD:
        return {"response_text": row["response_text"], "model_used": row["model_used"]}

    return None


async def save_to_cache(query: str, response_text: str, model_used: str) -> None:
    vector = embed(query)
    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO cache_entries (query_text, query_embedding, response_text, model_used)
        VALUES ($1, $2, $3, $4)
        """,
        query, vector, response_text, model_used,
    )