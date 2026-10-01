"""
Lab 2 tool step: the dial you tuned, on a service that does not offer it.

In Lab 2 you swept ef on Chroma, Qdrant and Milvus and chose an operating point.
A managed vector service picks that setting for you. Databricks AI Search (called
Vector Search until 2026) exposes an index and a query, and no accuracy dial.

This module does two things:
  - ai_search_measure() asks the trainer's shared Databricks AI Search index the
    same 200 questions, so its recall is a measurement against your own answer
    key, not the vendor's claim. It only runs on Databricks while the trainer's
    index is up; anywhere else it says so and returns None.
  - cost_of_their_default() reads your own sweep: what recall you would have
    shipped if somebody else had picked ef for you.

The shared index is created before class and deleted after it by the trainer
notebooks in databricks/trainer/. Students only query it. Never create an
endpoint from this module: an endpoint bills by the hour while any index exists.
"""
from __future__ import annotations

import json, os, time

import numpy as np

# The one shared endpoint and index. The trainer notebooks use the same names.
AI_SEARCH_ENDPOINT = "freshcart-lab2"
AI_SEARCH_INDEX = "aieng_dbx_itc.freshcart.lab2_bench"

# Which controls each option actually gives you. Written from each product's own
# documentation in September 2026. Check it again on the day you buy: this table
# is the first thing that goes stale.
DIALS = [
    {"option": "Chroma, Qdrant, Milvus (Lab 2)", "index type": "you choose",
     "accuracy dial at query time": "yes, ef", "pre-filter": "yes",
     "you can measure recall": "yes"},
    {"option": "Databricks AI Search", "index type": "chosen for you",
     "accuracy dial at query time": "no", "pre-filter": "yes, on columns (standard endpoint)",
     "you can measure recall": "only against your own answer key"},
    {"option": "Azure AI Search", "index type": "HNSW or exhaustive",
     "accuracy dial at query time": "partly, efSearch is set in the index",
     "pre-filter": "yes", "you can measure recall": "only against your own answer key"},
    {"option": "pgvector", "index type": "HNSW or IVFFlat",
     "accuracy dial at query time": "yes, ef_search or probes",
     "pre-filter": "no, after the scan; version 0.8 can keep scanning",
     "you can measure recall": "yes"},
    {"option": "Pinecone", "index type": "chosen for you",
     "accuracy dial at query time": "no", "pre-filter": "yes",
     "you can measure recall": "only against your own answer key"},
]


def cost_of_their_default(sweep_rows: list[dict], you_chose: int = 80,
                          their_defaults=(10, 20)) -> list[dict]:
    """Recall at a setting you can pick yourself, and at settings a vendor might
    have picked instead, read from your own sweep. Same questions, same answer key.
    Students commit to their own setting only later, in Step 8, so the label does
    not claim they chose it."""
    out = []
    for row in sweep_rows:
        if row["ef"] == you_chose or row["ef"] in their_defaults:
            who = "if you set it yourself" if row["ef"] == you_chose else "a vendor default"
            out.append({"database": row["database"], "setting": f"ef {row['ef']} ({who})",
                        "recall@10": row["recall@10"],
                        # text, so the table prints 1.9 rather than 1.900
                        "answers you lose in 10": f"{(1 - row['recall@10']) * 10:.1f}"})
    return out


def what_you_still_owe() -> list[str]:
    """The jobs that do not move to the vendor, whichever one you pick."""
    return [
        "An answer key. Without questions and their right answers you cannot "
        "tell a good index from a bad one on any platform.",
        "A filter that runs before the search, not after it. Lab 2 measured what "
        "filtering after the search costs: under 1 result returned when 10 were asked for.",
        "A number you check on every release. A managed index degrades quietly "
        "when the corpus changes, and nothing in the service will tell you.",
    ]


# ----------------------------------------------------------------------------
# Databricks AI Search: the trainer's shared index
# ----------------------------------------------------------------------------
def on_databricks() -> bool:
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


def _client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()        # inside a Databricks notebook this signs in as you, no token needed


def ai_search_status() -> tuple[bool, str]:
    """Is the trainer's shared index there and ready? Returns (ready, reason)."""
    if not on_databricks():
        return False, "skipped: Databricks AI Search only runs inside Databricks"
    try:
        w = _client()
        ep = w.vector_search_endpoints.get_endpoint(AI_SEARCH_ENDPOINT)
        state = str(getattr(getattr(ep, "endpoint_status", None), "state", "")).split(".")[-1]
        if state != "ONLINE":
            return False, f"skipped: the trainer's endpoint {AI_SEARCH_ENDPOINT} is {state or 'not running'}"
        idx = w.vector_search_indexes.get_index(AI_SEARCH_INDEX)
        if not getattr(getattr(idx, "status", None), "ready", False):
            return False, f"skipped: the trainer's index {AI_SEARCH_INDEX} is not ready yet"
        return True, "ready"
    except Exception as e:
        text = str(e)
        if "does not exist" in text or "NOT_FOUND" in text or "not found" in text.lower():
            return False, "skipped: the trainer's shared index is not running (it is only up during class)"
        if "PERMISSION" in text.upper() or "403" in text:
            return False, "skipped: you do not have permission to read the trainer's index; tell your trainer"
        return False, f"skipped: {type(e).__name__}: {text[:160]}"


def _query(w, q, k=10, label=None, tries=5):
    """One question to the shared index. Retries a few times if the service is busy,
    since twenty pairs share one endpoint."""
    for attempt in range(tries):
        try:
            res = w.vector_search_indexes.query_index(
                index_name=AI_SEARCH_INDEX, columns=["id"], query_vector=[float(x) for x in q],
                num_results=k, filters_json=json.dumps({"label": int(label)}) if label is not None else None)
            rows = (res.result.data_array or []) if res.result else []
            return [int(float(r[0])) for r in rows]
        except Exception as e:
            if attempt == tries - 1 or not any(s in str(e) for s in ("429", "RESOURCE_EXHAUSTED", "Too Many", "503")):
                raise
            time.sleep(0.5 * (2 ** attempt))


def ai_search_measure(bench, k=10, filter_label=3, n_filter_questions=10) -> dict | None:
    """Ask the shared index the same questions, one at a time, and score it against
    your own answer key. Also runs the filter test on it. Returns None when skipped."""
    ready, reason = ai_search_status()
    if not ready:
        print(reason)
        return None
    from vector_dbs import recall, exact_top_k
    w = _client()
    for q in bench.Q[:3]:                      # warm-up, not timed
        _query(w, q, k)
    got, lat = [], []
    for q in bench.Q:
        t0 = time.perf_counter()
        got.append(_query(w, q, k))
        lat.append((time.perf_counter() - t0) * 1000)
    allowed = bench.labels == filter_label
    counts, fgot, ftruth = [], [], []
    for q in bench.Q[:n_filter_questions]:
        rows = _query(w, q, k, label=filter_label)
        counts.append(len(rows)); fgot.append(rows); ftruth.append(exact_top_k(bench.X, q, k, allowed))
    lat = np.array(lat)
    return {"database": "databricks ai search", "ef": "not yours to set",
            "recall@10": recall(bench.truth, got, k),
            "p50_ms": round(float(np.percentile(lat, 50)), 1),
            "p95_ms": round(float(np.percentile(lat, 95)), 1),
            "filter returned (of 10)": round(float(np.mean(counts)), 1),
            "recall inside the filter": recall(ftruth, fgot, k)}
