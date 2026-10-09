"""
The Week 2 retrieval-and-answer stack, packaged once so Labs 4, 8, 10 and 12
exercise the same code:

    hybrid retrieval -> recency filter -> rerank -> top 5 -> grounded answer
                                                         -> citation check

Command-line track: BM25 + TF-IDF/SVD vectors, lexical reranker, echo generator.
Azure track: Azure AI Search hybrid query, LLM reranker, Azure OpenAI answer.
"""
from __future__ import annotations
import time, threading

import rag
from freshcart import current_only
from retrieval import Hybrid, rerank
from labkit import build_corpus


class RagStack:
    def __init__(self, azure: bool, threshold: float = 0.15, top_k: int = 5,
                 generate=None, corpus=None, ocr: bool = True, where=current_only,
                 search_filter: str | None = "superseded eq false"):
        """where: offline pre-filter, a function of a chunk.
        search_filter: the same rule as an OData filter for Azure AI Search."""
        self.azure, self.threshold, self.top_k, self.where = azure, threshold, top_k, where
        self.search_filter = search_filter
        self.corpus = corpus or build_corpus(azure, ocr=ocr)
        if azure:
            from azure_backends import AzureSearchIndex, azure_generator
            self.search = AzureSearchIndex().create()
            self.search.sync(self.corpus.chunks, self.corpus.index.M)
            self.generate = generate or azure_generator
        else:
            self.hybrid = Hybrid(self.corpus.index)
            self.generate = generate or rag.echo_generator
        self._local = threading.local()

    @property
    def last_timings(self):
        """Timings of the last call made by THIS thread (labs run questions in parallel)."""
        return getattr(self._local, "timings", {})

    def retrieve(self, question: str, k: int | None = None):
        k = k or self.top_k
        t0 = time.perf_counter()
        if self.azure:
            from azure_backends import search_hits_to_chunks, llm_rerank
            qv = self.corpus.index.embedder.encode([question])[0]
            rows = self.search.query(question, qv, k=20, mode="hybrid", flt=self.search_filter)
            cands = search_hits_to_chunks(rows, self.corpus.by_id)
            t1 = time.perf_counter()
            hits = llm_rerank(question, cands[:12], k=k)
        else:
            cands = self.hybrid.search(question, k=50, where=self.where)
            t1 = time.perf_counter()
            hits = rerank(question, cands, k=k, idf=self.hybrid.idf)
        t2 = time.perf_counter()
        self._local.timings = {"retrieval_ms": (t1 - t0) * 1000, "rerank_ms": (t2 - t1) * 1000}
        # Drift watches a score that moves when the index degrades. Offline that is
        # the best dense similarity; on Azure, the reranker's relevance grade (0 to 1).
        if self.azure:
            self._local.timings["first_stage_top"] = hits[0][0] if hits else 0.0
        else:
            dense = self.corpus.index.search(question, k=1)
            self._local.timings["first_stage_top"] = dense[0][0] if dense else 0.0
        return hits

    def ask(self, question: str, threshold: float | None = None):
        hits = self.retrieve(question)
        t0 = time.perf_counter()
        ans = rag.answer_question(question, hits, self.generate,
                                  threshold=self.threshold if threshold is None else threshold)
        self._local.timings["generation_ms"] = (time.perf_counter() - t0) * 1000
        return ans, hits
