from dotenv import load_dotenv
load_dotenv()

import asyncio
import streamlit as st
import pandas as pd
from app.db import get_pool


async def fetch_logs() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM request_logs ORDER BY created_at")
    return [dict(r) for r in rows]


def load_data() -> pd.DataFrame:
    rows = asyncio.run(fetch_logs())
    return pd.DataFrame(rows)


st.set_page_config(page_title="Tollgate Dashboard", layout="wide")
st.title("Tollgate — Cost-Aware LLM Gateway")

df = load_data()

if df.empty:
    st.info("No requests logged yet. Send some queries to /v1/chat first.")
else:
    total_requests = len(df)
    cache_hits = int(df["cache_hit"].sum())
    hit_rate = (cache_hits / total_requests) * 100

    misses = df[~df["cache_hit"]]
    avg_miss_cost = misses["cost_usd"].mean() if not misses.empty else 0
    actual_cost = df["cost_usd"].sum()
    estimated_cost_avoided = cache_hits * avg_miss_cost

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests", total_requests)
    col2.metric("Cache Hit Rate", f"{hit_rate:.1f}%")
    col3.metric("Actual Cost Incurred", f"${actual_cost:.6f}")
    col4.metric("Est. Cost Avoided (cache)", f"${estimated_cost_avoided:.6f}")

    st.caption(
        "Cost avoided is an estimate: cache hits are logged at $0 (no LLM call made), "
        "so avoided cost is approximated using the average cost of non-cached requests."
    )

    st.subheader("Requests by Tier")
    st.bar_chart(df["tier"].value_counts())

    st.subheader("Latency by Tier (ms)")
    st.bar_chart(df.groupby("tier")["latency_ms"].mean())

    st.subheader("Raw Log")
    st.dataframe(df, width="stretch")