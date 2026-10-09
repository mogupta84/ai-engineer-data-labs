"""
LAB 3: hybrid retrieval, reranking and the lift, measured with nDCG@10.

    python labs/lab03_hybrid.py            command-line track
    python labs/lab03_hybrid.py --azure    Azure AI Search hybrid + LLM reranker

Four stages, measured separately: dense, hybrid, +rerank, +recency filter.
Relevance judgements for 20 queries are in data/golden/retrieval_golden.json.

TRY THIS after the first run:
  1. Change K_EACH (candidates per retriever) from 50 to 10. What happens to hybrid?
  2. Add one query of your own to the golden file, with its rules.
  3. Find the query that got WORSE after reranking and explain why.
"""
import sys, pathlib, time, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from labenv import setup_track
AZURE = setup_track("Lab 3: hybrid retrieval and reranking", needs=("openai", "search"))

from freshcart import current_only
from retrieval import Hybrid, rerank, ndcg_at_k
from labkit import build_corpus, load_golden, relevance, table, banner, pmap

K = 10          # nDCG@10
K_EACH = 50     # candidates from each retriever before fusion
RERANK_TOP = 15 if AZURE else 50


def offline_stages(corpus, q):
    hyb = corpus._hybrid
    t = {}
    s = time.perf_counter(); dense = corpus.index.search(q, k=K_EACH); t["dense"] = time.perf_counter() - s
    s = time.perf_counter(); fused = hyb.search(q, k=K_EACH, k_each=K_EACH); t["hybrid"] = time.perf_counter() - s
    s = time.perf_counter(); rr = rerank(q, fused[:RERANK_TOP], k=K, idf=hyb.idf); t["rerank"] = time.perf_counter() - s
    s = time.perf_counter()
    filt = rerank(q, hyb.search(q, k=K_EACH, k_each=K_EACH, where=current_only)[:RERANK_TOP], k=K, idf=hyb.idf)
    t["filter"] = time.perf_counter() - s
    return {"dense": dense, "hybrid": fused, "rerank": rr, "filter": filt}, t


def azure_stages(corpus, q):
    from azure_backends import AzureSearchIndex, search_hits_to_chunks, llm_rerank
    ix = corpus._search
    by_id = corpus.by_id
    qv = corpus.index.embedder.encode([q])[0]
    t = {}
    s = time.perf_counter()
    dense = search_hits_to_chunks(ix.query(None, qv, k=K_EACH, mode="vector"), by_id)
    t["dense"] = time.perf_counter() - s
    s = time.perf_counter()
    fused = search_hits_to_chunks(ix.query(q, qv, k=K_EACH, mode="hybrid"), by_id)
    t["hybrid"] = time.perf_counter() - s
    s = time.perf_counter()
    rr = llm_rerank(q, fused[:RERANK_TOP], k=RERANK_TOP) + fused[RERANK_TOP:]
    t["rerank"] = time.perf_counter() - s
    s = time.perf_counter()
    cur = search_hits_to_chunks(ix.query(q, qv, k=K_EACH, mode="hybrid", flt="superseded eq false"), by_id)
    filt = llm_rerank(q, cur[:RERANK_TOP], k=RERANK_TOP) + cur[RERANK_TOP:]
    t["filter"] = time.perf_counter() - s
    return {"dense": dense, "hybrid": fused, "rerank": rr, "filter": filt}, t


def main():
    corpus = build_corpus(AZURE)
    if AZURE:
        from azure_backends import AzureSearchIndex, USAGE
        ix = AzureSearchIndex().create()
        if ix.sync(corpus.chunks, corpus.index.M):
            print(f"uploaded {len(corpus.chunks)} chunks to AI Search index '{ix.name}'")
        corpus._search = ix
    else:
        corpus._hybrid = Hybrid(corpus.index)

    golden = load_golden("retrieval_golden.json")["queries"]
    stages = ["dense", "hybrid", "rerank", "filter"]
    rows, lat = [], {s: [] for s in stages}
    runs = pmap(lambda item: (azure_stages if AZURE else offline_stages)(corpus, item["query"]),
                golden, AZURE)
    for item, (results, t) in zip(golden, runs):
        rel = relevance(item, corpus.chunks)
        row = {"id": item["id"], "query": item["query"][:44]}
        for s in stages:
            ids = [c.id for _, c in results[s]]
            row[s] = ndcg_at_k(ids, rel, k=K)
            row[s + "@3"] = ndcg_at_k(ids, rel, k=3)
            lat[s].append(t[s] * 1000)
        row["w1"] = "yes" if item.get("week1_failure") else ""
        rows.append(row)

    banner("nDCG@10 per query")
    print(table(rows, ["id", "query", "dense", "hybrid", "rerank", "filter", "w1"]))

    banner("summary: the lift, one stage at a time")
    summary = []
    for s in stages:
        summary.append({"stage": s, "mean_nDCG@10": round(statistics.mean(r[s] for r in rows), 3),
                        "mean_nDCG@3": round(statistics.mean(r[s + "@3"] for r in rows), 3),
                        "p50_ms": round(statistics.median(lat[s]), 1),
                        "p95_ms": round(sorted(lat[s])[int(0.95 * len(lat[s])) - 1], 1)})
    print(table(summary))

    banner("Week 1 failures")
    for r in rows:
        if r["w1"]:
            gain = r["filter"] - r["dense"]
            verdict = ("still failing" if r["filter"] < 0.5 else
                       "improved" if gain >= 0.1 else "no change" if abs(gain) < 0.1 else "worse")
            print(f"  {r['id']} {r['query']:44s} dense {r['dense']:.2f} -> final {r['filter']:.2f}  {verdict}")

    banner("queries that got WORSE after reranking (explain one in your debrief)")
    worse = [r for r in rows if r["rerank"] < r["hybrid"] - 1e-9]
    for r in worse:
        print(f"  {r['id']} {r['query']:44s} hybrid {r['hybrid']:.2f} -> rerank {r['rerank']:.2f}")
    if not worse:
        print("  none this run")
    if AZURE:
        from azure_backends import USAGE
        print("\n" + USAGE.line())


if __name__ == "__main__":
    main()
