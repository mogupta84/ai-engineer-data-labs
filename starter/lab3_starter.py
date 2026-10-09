"""
LAB 3 STARTER: keyword search, reranking and the recency filter, each measured.

    python3 starter/lab3_starter.py

Reference: labs/lab03_hybrid.py     Guided version: the lab03_hybrid notebook in your workspace
"""
import sys, pathlib, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from labkit import build_corpus, load_golden, relevance, table, banner
from retrieval import Hybrid, rerank, ndcg_at_k
from freshcart import current_only

K_EACH = 50          # TODO 1: candidates from each search before the merge. Try 10 and 50.


def main():
    corpus = build_corpus(False)
    golden = load_golden("retrieval_golden.json")["queries"]
    hyb = Hybrid(corpus.index)

    def scores(search_fn):
        out = []
        for item in golden:
            rel = relevance(item, corpus.chunks)
            ids = [ch.id for _, ch in search_fn(item["query"])]
            out.append(ndcg_at_k(ids, rel, k=10))
        return out

    # TODO 2: before you run anything, write your prediction for each stage.
    PREDICT = {"dense": 0.80, "hybrid": 0.00, "rerank": 0.00, "filter": 0.00}

    dense = scores(lambda q: corpus.index.search(q, k=50))
    print(f"meaning search only : {statistics.mean(dense):.3f}")

    # TODO 3: add keyword search fused with meaning search, and measure it.
    hybrid = scores(lambda q: hyb.search(q, k=50, k_each=K_EACH))
    print(f"with keyword search : {statistics.mean(hybrid):.3f}")

    # TODO 4: rerank the shortlist, measure, then list every question that got WORSE.
    #         Pick one and write down why it got worse.
    reranked = scores(lambda q: rerank(q, hyb.search(q, k=50, k_each=K_EACH)[:50], k=10, idf=hyb.idf))
    print(f"after reranking     : {statistics.mean(reranked):.3f}")

    # TODO 5: add the recency filter, which drops withdrawn documents using the
    #         'superseded' label you attached in Lab 1. Measure again.
    filtered = scores(lambda q: rerank(q, hyb.search(q, k=50, k_each=K_EACH, where=current_only)[:50],
                                       k=10, idf=hyb.idf))
    print(f"after recency filter: {statistics.mean(filtered):.3f}")

    banner("the five Week 1 failures")
    for item, d, f in zip(golden, dense, filtered):
        if item.get("week1_failure"):
            print(f"  {item['id']}  {item['query'][:46]:46s} {d:.2f} -> {f:.2f}")

    # TODO 6: time each stage as well as scoring it, then fill in handouts/lab3_answers.md.
    #         One question decides the lab: which of the three additions would you ship?


if __name__ == "__main__":
    main()
