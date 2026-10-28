"""Lab 9, D3: search the shared index in five ways and score each on Lab 3's 20 judged questions (Lab 3, in Azure).

    python d3_search.py              stages 1 to 3: meaning, keyword, both together
    python d3_search.py --rerank     also stages 4 and 5: Azure's reranker, then only current documents
    python d3_search.py --show R01   the top 3 pieces of one question in every stage

The reranker is the free tier's: 1,000 searches a month for the whole class, and --rerank uses 40. Run it once
per pair. The score is nDCG@10, from 0 to 1, as in Lab 3.
"""
import sys            # read the options
import time           # time each stage

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

from docs_common import INDEX, golden, ndcg_at_10, setting

FIELDS = ["id", "file", "content", "current"]


def stages(client):
    """Each stage is one way to ask the same index. The index turns the question into numbers itself."""
    meaning = lambda q: VectorizableTextQuery(text=q, k_nearest_neighbors=10, fields="vector")
    out = {
        "1 meaning": lambda q: client.search(search_text=None, vector_queries=[meaning(q)], top=10, select=FIELDS),
        "2 keyword": lambda q: client.search(search_text=q, top=10, select=FIELDS),
        "3 both": lambda q: client.search(search_text=q, vector_queries=[meaning(q)], top=10, select=FIELDS),
    }
    if "--rerank" in sys.argv:
        out["4 both + reranker"] = lambda q: client.search(search_text=q, vector_queries=[meaning(q)], top=10,
                                                           select=FIELDS, query_type="semantic",
                                                           semantic_configuration_name="rerank")
        out["5 + current only"] = lambda q: client.search(search_text=q, vector_queries=[meaning(q)], top=10,
                                                          select=FIELDS, query_type="semantic",
                                                          semantic_configuration_name="rerank", filter="current eq true")
    return out


def main():
    client = SearchClient(setting("SEARCH_ENDPOINT"), INDEX, AzureKeyCredential(setting("SEARCH_QUERY_KEY")))
    every_piece = list(client.search(search_text="*", top=100, select=FIELDS))        # for the best possible top 10
    questions = golden("retrieval_golden.json")["queries"]
    show = sys.argv[sys.argv.index("--show") + 1] if "--show" in sys.argv else None
    scores = {}
    for name, ask in stages(client).items():
        start, per_question = time.time(), {}
        for q in questions:
            ranked = list(ask(q["query"]))
            per_question[q["id"]] = ndcg_at_10(q["rules"], ranked, every_piece)
            if show == q["id"]:
                print(f"\n{name}, {q['id']} {q['query']!r}")
                for p in ranked[:3]:
                    score = p.get("@search.reranker_score") or p["@search.score"]
                    print(f"   {score:7.3f}  {p['file']:36} {p['content'][:70]!r}")
        scores[name] = per_question
        scored = [v for v in per_question.values() if v is not None]        # a question no piece answers is left out
        mean = sum(scored) / len(scored)
        print(f"{name:20} nDCG@10 {mean:.3f}   {(time.time() - start) / len(questions) * 1000:4.0f} ms a question")
    if "4 both + reranker" in scores:
        worse = [(i, scores["3 both"][i], scores["4 both + reranker"][i]) for i in scores["3 both"]
                 if None not in (scores["3 both"][i], scores["4 both + reranker"][i])
                 and scores["4 both + reranker"][i] < scores["3 both"][i] - 0.01]
        print(f"\nThe reranker made {len(worse)} questions worse:", ", ".join(f"{i} {a:.2f} to {b:.2f}" for i, a, b in worse))


main()
