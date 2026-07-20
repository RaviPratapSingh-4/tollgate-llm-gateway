from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import time
from pathlib import Path
import httpx
from app.providers.gemini_provider import GeminiProvider
from app.services.pricing import calculate_cost

GATEWAY_URL = "http://127.0.0.1:8000/v1/chat"
RESULTS_FILE = Path("benchmark_results.json")

UNIQUE_QUERIES = [
    "What is the capital of France?",
    "What is the capital of Germany?",
    "Who wrote Romeo and Juliet?",
    "Define recursion in programming.",
    "What is photosynthesis?",
    "Explain in depth how neural networks learn through backpropagation.",
    "Compare and contrast SQL and NoSQL databases.",
    "Walk me through how a hash table works internally.",
    "Analyze the trade-offs between REST and GraphQL APIs.",
    "Design a rate limiter for a public API.",
]

REPEATS = UNIQUE_QUERIES[:1] + UNIQUE_QUERIES[5:6]
BENCHMARK_QUERIES = UNIQUE_QUERIES + REPEATS


def load_results() -> dict:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return {"gateway": {}, "baseline": {}}


def save_result(results: dict, pass_name: str, query: str, cost: float, latency: int) -> None:
    results[pass_name][query] = {"cost": cost, "latency": latency}
    RESULTS_FILE.write_text(json.dumps(results, indent=2))


async def run_gateway_pass(results: dict) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        for query in BENCHMARK_QUERIES:
            if query in results["gateway"]:
                print(f"  Already done, skipping: {query[:40]}...")
                continue

            try:
                response = await client.post(GATEWAY_URL, json={"query": query})
                data = response.json()
            except Exception as e:
                print(f"  Failed, will retry next run: {query[:40]}... ({e})")
                await asyncio.sleep(4)
                continue

            model = data["model_used"].replace(" (cached)", "")
            if data["input_tokens"] == 0 and data["output_tokens"] == 0:
                cost = 0.0
            else:
                cost = calculate_cost(model, data["input_tokens"], data["output_tokens"])

            save_result(results, "gateway", query, cost, data["latency_ms"])
            await asyncio.sleep(4)


async def run_naive_baseline_pass(results: dict) -> None:
    gemini = GeminiProvider()

    for query in BENCHMARK_QUERIES:
        if query in results["baseline"]:
            print(f"  Already done, skipping: {query[:40]}...")
            continue

        try:
            start = time.perf_counter()
            result = await gemini.call(query)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
        except Exception as e:
            print(f"  Failed, will retry next run: {query[:40]}... ({e})")
            await asyncio.sleep(15)
            continue

        cost = calculate_cost("gemini/gemini-2.5-flash", result.input_tokens, result.output_tokens)
        save_result(results, "baseline", query, cost, elapsed_ms)
        await asyncio.sleep(15)


async def main():
    results = load_results()

    print(f"Running benchmark with {len(BENCHMARK_QUERIES)} queries "
          f"({len(UNIQUE_QUERIES)} unique + {len(REPEATS)} repeats)...\n")

    print("Pass 1: real gateway (cache + routing)...")
    await run_gateway_pass(results)

    print("Pass 2: naive baseline (frontier-only, no cache)...")
    await run_naive_baseline_pass(results)

    gateway_done = len(results["gateway"])
    baseline_done = len(results["baseline"])
    total = len(BENCHMARK_QUERIES)

    if gateway_done < total or baseline_done < total:
        print(f"\nIncomplete: gateway {gateway_done}/{total}, baseline {baseline_done}/{total}.")
        print("Run the script again later to fill in the rest — already-completed queries won't be repeated.")
        return

    gateway_cost = sum(r["cost"] for r in results["gateway"].values())
    gateway_latency = sum(r["latency"] for r in results["gateway"].values())
    baseline_cost = sum(r["cost"] for r in results["baseline"].values())
    baseline_latency = sum(r["latency"] for r in results["baseline"].values())

    cost_savings_pct = (1 - gateway_cost / baseline_cost) * 100 if baseline_cost else 0
    latency_savings_pct = (1 - gateway_latency / baseline_latency) * 100 if baseline_latency else 0

    print("\n=== RESULTS ===")
    print(f"{'Metric':<25}{'Gateway':<15}{'Naive Baseline':<15}{'Savings'}")
    print(f"{'Total cost ($)':<25}{gateway_cost:<15.6f}{baseline_cost:<15.6f}{cost_savings_pct:.1f}%")
    print(f"{'Total latency (ms)':<25}{gateway_latency:<15}{baseline_latency:<15}{latency_savings_pct:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())