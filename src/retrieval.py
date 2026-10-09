"""Labs 3 and 4: hybrid retrieval, reranking, nDCG, grounding and citations."""
from __future__ import annotations
import math, re, hashlib
import numpy as np
from rank_bm25 import BM25Okapi

_tok = lambda t: re.findall(r"[a-z0-9\-]+", t.lower())

class Hybrid:
    """Dense + BM25, fused by reciprocal rank. They fail in opposite directions."""
    def __init__(self, index):
        self.index = index
        self.bm25 = BM25Okapi([_tok(c.text) for c in index.chunks])
        self.idf = {w: float(v) for w, v in self.bm25.idf.items()}
        self.idf = {_stem(w): v for w, v in self.idf.items()}

    def dense(self, q, k=50, where=None):
        return [(s, c) for s, c in self.index.search(q, k=k, where=where)]

    def sparse(self, q, k=50, where=None):
        scores = self.bm25.get_scores(_tok(q))
        order = np.argsort(-scores)
        out = []
        for i in order:
            c = self.index.chunks[i]
            if where and not where(c): continue
            out.append((float(scores[i]), c))
            if len(out) == k: break
        return out

    def search(self, q, k=10, k_each=50, where=None, kd=60):
        d = self.dense(q, k_each, where); s = self.sparse(q, k_each, where)
        fused = {}
        for rank, (_, c) in enumerate(d): fused[c.id] = fused.get(c.id, 0) + 1/(kd+rank+1)
        for rank, (_, c) in enumerate(s): fused[c.id] = fused.get(c.id, 0) + 1/(kd+rank+1)
        by_id = {c.id: c for _, c in d + s}
        ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [(sc, by_id[cid]) for cid, sc in ranked]

def _stem(w):
    for suf in ("ages", "age", "ing", "ies", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w

def rerank(query, candidates, k=5, idf=None):
    """Stand-in cross-encoder. Scores query and candidate TOGETHER, weighting rare
    terms, which is broadly what a real cross-encoder learns to do. Swap for a
    hosted reranker in production; the two-stage shape is what matters here."""
    qt = [_stem(w) for w in _tok(query)]
    qset = set(qt)
    out = []
    for _, c in candidates:
        ct = [_stem(w) for w in _tok(c.text)]
        cs = set(ct)
        matched = qset & cs
        if idf:
            num = sum(idf.get(w, 1.0) for w in matched)
            den = sum(idf.get(w, 1.0) for w in qset) or 1.0
            cover = num / den
        else:
            cover = len(matched) / max(1, len(qset))
        pos = [i for i, w in enumerate(ct) if w in qset]
        tight = 1.0 / (1 + (max(pos) - min(pos)) / 80) if len(pos) > 1 else 0.4
        out.append((0.8 * cover + 0.2 * tight, c))
    # blend with the incoming rank: first-stage order carries real signal, and a
    # reranker that ignores it entirely reorders catastrophically on short text
    prior = {c.id: 1.0 / (1 + i) for i, (_, c) in enumerate(candidates)}
    blended = [(0.7 * sc + 0.3 * prior.get(c.id, 0.0), c) for sc, c in out]
    return sorted(blended, key=lambda x: -x[0])[:k]

def ndcg_at_k(ranked_ids, relevance: dict, k=10):
    """Rewards putting relevant results higher. relevance maps chunk_id -> 0..3."""
    dcg = sum((2**relevance.get(cid, 0) - 1) / math.log2(i + 2)
              for i, cid in enumerate(ranked_ids[:k]))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ideal))
    return round(dcg / idcg, 4) if idcg else 0.0
