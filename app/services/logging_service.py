from app.db import get_pool

async def log_request(
    query_text: str,
    model_used: str,
    tier: str,
    cache_hit: bool,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO request_logs
            (query_text, model_used, tier, cache_hit, input_tokens, output_tokens, cost_usd, latency_ms)
        VALUES ($1, $2, $3, $4, $5, $6, ROUND($7::numeric, 8), $8)
        """,
        query_text, model_used, tier, cache_hit, input_tokens, output_tokens, cost_usd, latency_ms,
    )