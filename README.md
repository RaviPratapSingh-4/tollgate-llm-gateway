# Tollgate — Cost-Aware LLM Gateway

A backend gateway that sits in front of LLM API calls and cuts unnecessary cost and latency before they happen — by remembering semantically similar questions it's already answered, and by routing each new question to the cheapest model capable of answering it well.

Built as a systems/infrastructure project, not a chatbot wrapper: the interesting part is the routing, caching, and cost-accounting logic underneath, not the LLM call itself.

## Why this exists

Every LLM call costs money and time, regardless of whether the question actually needed a frontier-class model. Most real-world traffic is a mix of trivial lookups and genuinely hard questions — but naive integrations send everything to the same (usually most expensive) model, every time, even for repeats.

Tollgate asks two questions before spending anything on a call:
1. **Have we effectively seen this question before?** — semantic cache, not just exact-string matching.
2. **Does this question actually need the expensive model?** — a lightweight classifier decides.

Only after both checks fail does a real, paid LLM call happen.

## Architecture

```
                ┌──────────────────────┐
   Query  ───▶  │  Semantic Cache       │──▶ Hit? Return instantly, $0, no LLM call
                │  (pgvector + MiniLM)  │
                └───────────┬──────────┘
                            │ Miss
                            ▼
                ┌──────────────────────┐
                │  Complexity           │
                │  Classifier (rules)   │
                └───────────┬──────────┘
                      ┌──────┴──────┐
                      ▼             ▼
                ┌─────────┐   ┌───────────┐
                │  Groq    │   │  Gemini    │
                │ (cheap)  │   │(frontier)  │
                └────┬─────┘   └─────┬─────┘
                     └───────┬───────┘
                             ▼
                  Save to cache + log
                  (cost, latency, tier)
```

- **Cache hit** → instant response, $0 cost, no LLM call made
- **Cache miss** → heuristic classifier picks a tier → routed to the matching provider → response cached for next time → every outcome logged for cost/latency accounting

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI (async) | Native async fits a system doing concurrent I/O to two LLM providers + a database |
| Cheap tier | Groq — Llama 3.3 70B | Free tier, exceptionally fast inference hardware |
| Frontier tier | Google Gemini 2.5 Flash | Free tier, no card required, stronger reasoning on open-ended queries |
| Semantic cache | PostgreSQL + pgvector | Exact relational data and vector similarity search in one database — no separate vector store needed |
| Embeddings | `all-MiniLM-L6-v2` (local) | Runs on CPU, no API cost, 384-dim output matches the `vector(384)` cache column |
| Cost accounting | Published per-token pricing tables | Cost stays meaningful even when actual billing is $0 on free tiers |
| Dashboard | Streamlit | Live view of hit rate, cost, tier split, latency — no separate frontend stack |
| Dependency management | uv | Fast, reproducible installs and lockfile |

## Project Structure

```
tollgate-llm-gateway/
├── app/
│   ├── main.py                  # FastAPI app — thin, just wiring
│   ├── schemas.py                # Request/response models (API boundary)
│   ├── db.py                     # Shared asyncpg connection pool
│   ├── classifier.py             # Heuristic cheap/frontier classifier
│   ├── providers/                 # Vendor-specific LLM clients
│   │   ├── base.py                # LLMProvider contract (vendor-agnostic interface)
│   │   ├── groq_provider.py
│   │   └── gemini_provider.py
│   └── services/                   # Business logic, not tied to any vendor
│       ├── cache.py                # Semantic cache lookup/save (pgvector)
│       ├── embeddings.py           # MiniLM wrapper
│       ├── pricing.py              # Published cost-per-token calculation
│       └── logging_service.py      # Writes every request to request_logs
├── dashboard.py                   # Streamlit — standalone entry point
├── benchmark.py                   # A/B cost & latency benchmark harness
├── docker-compose.yml              # Postgres + pgvector
└── pyproject.toml
```

**Design principle:** `providers/` only knows vendor SDKs; `services/` only knows business logic; `main.py` only wires things together. Swapping or adding a provider never touches routing, caching, or logging code.

## Key Design Decisions

- **Provider-agnostic interface (`LLMProvider` protocol):** every provider implements one `call(query) -> ProviderResponse` contract. Routing code never knows which SDK it's talking to — adding a third provider is a one-file change.
- **Cost via published pricing, not actual billing:** since development runs on free tiers, real billed cost is often $0. Cost is instead computed from each provider's published per-token rate, applied to real token counts — so the savings benchmark reflects real-world economics, not free-tier accounting artifacts.
- **Heuristic-first classifier:** a rule-based classifier ships first, deliberately, instead of a trained model. Training a classifier before measuring how often simple rules actually fail would be optimizing a problem that hasn't been proven to exist yet. A learned (LoRA) classifier remains a legitimate future step — conditional on benchmark evidence showing the heuristic genuinely under-performs, not on it being the more sophisticated-sounding option.
- **Float precision handled at the SQL boundary:** cost values are rounded via Postgres's `NUMERIC` cast (`ROUND($n::numeric, 8)`), not in Python — rounding a float in Python still returns an imprecise float; only casting to an exact decimal type at the database layer produces a clean stored value.
- **No cache invalidation/TTL (stated limitation, not an oversight):** acceptable for demo-scale, largely time-insensitive queries; a real deployment would need this.

## Running Locally

```bash
uv sync
docker compose up -d                          # Postgres + pgvector
uv run uvicorn app.main:app --reload
```

Create a `.env` file with:
```
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
DATABASE_URL=postgresql://tollgate:tollgate_dev_password@localhost:5433/tollgate
```

Then send a query:
```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'
```

## Dashboard

```bash
uv run streamlit run dashboard.py
```

Shows total requests, cache hit rate, actual cost incurred, estimated cost avoided by caching, tier breakdown, and per-tier latency — all pulled live from `request_logs`.

## Benchmark

`benchmark.py` runs a fixed, repeat-inclusive query set through two paths and compares them:
1. **The real gateway** — cache + classifier + routing, exactly as it behaves in production.
2. **A naive baseline** — every query forced through the frontier model directly, no cache, no routing (simulating "no gateway at all").

```bash
uv run python benchmark.py
```

Results are saved incrementally to `benchmark_results.json` (gitignored), so an interrupted run — e.g. from a free-tier rate limit — resumes without re-spending API quota on already-completed queries.

### Results

| Metric | Gateway | Naive Baseline | Difference |
|---|---|---|---|
| Total latency | 13.8s | 24.2s | **42.9% faster** |
| Total cost | $0.000333 | $0.000319 | ~breakeven on this sample |

**Honest interpretation:** latency improves consistently and substantially — caching skips the LLM call entirely on repeats, and cheap-tier inference is inherently faster than frontier-tier. Cost savings depend on query complexity: on genuinely complex queries, the cheap tier's lower per-token rate holds a clear, measurable advantage; on trivial one-line factual queries, a fixed per-call overhead (e.g. system-prompt tokens) dominates at small sample sizes, narrowing the gap to roughly breakeven. A larger, more realistic traffic sample — with the higher proportion of non-trivial queries typical of real usage — would be expected to show a clearer net cost advantage. This result is reported as measured, not adjusted to look better.

## Known Limitations

- **Classifier is heuristic** (keyword/length-based), not learned — an explicit, evidence-driven MVP decision, not an oversight.
- **No cache invalidation/TTL** — fine for demo-scale, time-insensitive queries; would need addressing for production use with time-sensitive data.
- **No retry/fallback on provider failure** beyond Gemini's built-in retry-with-backoff — a single unrecoverable provider error currently surfaces as a 500.
- **Gemini free tier is rate-limited** (both per-minute and per-day quotas), which the benchmark harness explicitly paces around and resumes across.
- **No authentication** on the API — acceptable for a local/demo deployment, would be required before any public exposure.

## What This Project Demonstrates

- Designing a clean vendor-agnostic interface so infrastructure decisions (which LLM, which tier) stay decoupled from business logic.
- Building and reasoning about a real semantic cache (embeddings + vector similarity search), not just a keyword lookup.
- Honest cost modeling independent of what a free tier happens to bill.
- Debugging a multi-stage benchmark harness through real, distinct failure modes (state-tracking bugs, response verbosity, prompt-overhead cost) and reporting the resulting numbers as measured, including where they complicate a clean narrative.