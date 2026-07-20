# Tollgate — Cost-Aware LLM Gateway

A backend gateway that reduces LLM API costs by routing queries between a cheap, fast model and a stronger frontier model based on query complexity, and by caching semantically similar queries to avoid redundant LLM calls entirely.

## Why this exists

Every LLM call costs money and time, regardless of whether the question actually needs a frontier-class model. Tollgate sits in front of your LLM calls and asks two questions before spending anything: *have we effectively seen this before?* and *does this actually need the expensive model?* — cutting cost and latency without sacrificing answer quality.

## Architecture

```
Query → Semantic Cache Check (pgvector) → Complexity Classifier → Route (Groq / Gemini) → Log
```

- **Cache hit** → instant response, $0 cost, no LLM call
- **Cache miss** → heuristic classifier picks a tier → routed to the matching provider → response cached for next time

## Tech Stack

- **API:** FastAPI (async)
- **Cheap tier:** Groq (Llama 3.3 70B) — fast, low-cost inference
- **Frontier tier:** Google Gemini 2.5 Flash
- **Semantic cache:** PostgreSQL + pgvector, embeddings via `all-MiniLM-L6-v2` (local, no API cost)
- **Cost accounting:** published per-token pricing tables (not billing-dependent)
- **Dashboard:** Streamlit — cache hit rate, cost incurred, tier breakdown, latency
- **Dependency management:** uv

## Key Design Decisions

- **Provider-agnostic interface:** a single `LLMProvider` protocol means adding/swapping providers never touches routing logic.
- **Cost via published pricing, not actual billing:** ensures the cost-savings benchmark is meaningful even when running on free-tier API access.
- **Heuristic-first classifier:** a rule-based classifier ships first; a learned classifier is a deliberate, evidence-driven future step rather than a premature optimization.

## Running Locally

```bash
uv sync
docker compose up -d          # Postgres + pgvector
uv run uvicorn app.main:app --reload
```

Set `GROQ_API_KEY`, `GEMINI_API_KEY`, and `DATABASE_URL` in a `.env` file (see `.env.example`).

## Benchmark

`benchmark.py` runs a fixed query set through the real gateway and a naive frontier-only baseline, comparing total cost and latency to quantify actual savings.

```bash
uv run python benchmark.py
```

## Dashboard

```bash
uv run streamlit run dashboard.py
```

## Known Limitations

- Classifier is heuristic (keyword/length-based), not learned — an intentional, stated MVP tradeoff.
- No cache invalidation/TTL — acceptable for demo-scale, time-insensitive queries.
- Gemini free tier is rate-limited (RPM and daily quota), which the benchmark harness paces around.
