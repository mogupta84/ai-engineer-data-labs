"""
Lab 2: three vector stores with genuinely different characteristics, all offline.

  FlatStore    exact search. 100% recall by definition. Your ground truth.
  IVFStore     clusters vectors, probes only the nearest few. Recall < 100%,
               tunable with n_probe. This is the approximate/exact trade, live.
  SqliteStore  vectors on disk in SQLite. Exact, but slower and filter-aware.

Deliberately small dependencies so a cohort can run it without pip trouble.
"""
from __future__ import annotations
import time, sqlite3, io, pathlib
import numpy as np


# ----------------------------------------------------------------------------
class FlatStore:
    name = "flat-exact"

    def __init__(self): self.M = None; self.meta = None

    def build(self, M, meta):
        t = time.perf_counter()
        self.M, self.meta = M.astype("float32"), meta
        return time.perf_counter() - t

    def search(self, q, k=10, where=None):
        sims = self.M @ q
        order = np.argsort(-sims)
        out = []
        for i in order:
            if where and not where(self.meta[i]):
                continue
            out.append((int(i), float(sims[i])))
            if len(out) == k:
                break
        return out

    def memory_bytes(self): return self.M.nbytes


# ----------------------------------------------------------------------------
class IVFStore:
    """Inverted file index: cluster once, then search only the nearest clusters.
    n_probe is the runtime dial: the offline analogue of efSearch."""
    name = "ivf"

    def __init__(self, n_lists=8, n_probe=2, seed=0):
        self.n_lists, self.n_probe, self.seed = n_lists, n_probe, seed
        self.centroids = None; self.lists = None; self.M = None; self.meta = None

    def build(self, M, meta):
        from sklearn.cluster import KMeans
        t = time.perf_counter()
        self.M, self.meta = M.astype("float32"), meta
        n_lists = max(1, min(self.n_lists, len(M) // 2 or 1))
        km = KMeans(n_clusters=n_lists, n_init=4, random_state=self.seed).fit(self.M)
        self.centroids = km.cluster_centers_.astype("float32")
        self.lists = {c: np.where(km.labels_ == c)[0] for c in range(n_lists)}
        return time.perf_counter() - t

    def search(self, q, k=10, where=None):
        cent_sims = self.centroids @ q
        probe = np.argsort(-cent_sims)[:max(1, self.n_probe)]
        cand = np.concatenate([self.lists[int(c)] for c in probe]) if len(probe) else np.array([], int)
        if cand.size == 0:
            return []
        sims = self.M[cand] @ q
        order = np.argsort(-sims)
        out = []
        for j in order:
            i = int(cand[j])
            if where and not where(self.meta[i]):
                continue
            out.append((i, float(sims[j])))
            if len(out) == k:
                break
        return out

    def memory_bytes(self): return self.M.nbytes + self.centroids.nbytes


# ----------------------------------------------------------------------------
class SqliteStore:
    """Vectors persisted in SQLite. Exact search, higher latency, and metadata
    filtering happens in SQL, which is the pre-filter case."""
    name = "sqlite"

    def __init__(self, path=":memory:"): self.path = path; self.con = None; self.dim = 0

    def build(self, M, meta):
        t = time.perf_counter()
        self.con = sqlite3.connect(self.path)
        self.con.execute("DROP TABLE IF EXISTS vecs")
        self.con.execute("CREATE TABLE vecs (i INTEGER PRIMARY KEY, superseded INT, v BLOB)")
        self.dim = M.shape[1]
        rows = [(i, int(bool(meta[i].get("superseded", False))), M[i].astype("float32").tobytes())
                for i in range(len(M))]
        self.con.executemany("INSERT INTO vecs VALUES (?,?,?)", rows)
        self.con.commit()
        self.meta = meta
        return time.perf_counter() - t

    def search(self, q, k=10, where=None, pre_filter_sql=None):
        sql = "SELECT i, v FROM vecs"
        if pre_filter_sql:
            sql += f" WHERE {pre_filter_sql}"
        rows = self.con.execute(sql).fetchall()
        if not rows:
            return []
        idx = np.array([r[0] for r in rows])
        M = np.frombuffer(b"".join(r[1] for r in rows), dtype="float32").reshape(len(rows), self.dim)
        sims = M @ q
        order = np.argsort(-sims)
        out = []
        for j in order:
            i = int(idx[j])
            if where and not where(self.meta[i]):
                continue
            out.append((i, float(sims[j])))
            if len(out) == k:
                break
        return out

    def memory_bytes(self):
        return self.con.execute("SELECT SUM(LENGTH(v)) FROM vecs").fetchone()[0] or 0


# ----------------------------------------------------------------------------
# Benchmark harness
# ----------------------------------------------------------------------------
def ground_truth(M, meta, queries, k=10):
    flat = FlatStore(); flat.build(M, meta)
    return {qi: [i for i, _ in flat.search(q, k=k)] for qi, q in enumerate(queries)}


def recall_at_k(truth, got, k=10):
    if not truth:
        return 0.0
    return len(set(truth[:k]) & set(got[:k])) / min(k, len(truth))


def benchmark(store, M, meta, queries, truth, k=10, warmup=3, where=None):
    build_s = store.build(M, meta)
    for _ in range(warmup):                      # discard cold runs
        store.search(queries[0], k=k)
    lats, recalls, counts = [], [], []
    for qi, q in enumerate(queries):
        t0 = time.perf_counter()
        res = store.search(q, k=k, where=where)
        lats.append((time.perf_counter() - t0) * 1000)
        recalls.append(recall_at_k(truth[qi], [i for i, _ in res], k))
        counts.append(len(res))
    lats = np.array(lats)
    return {
        "store": store.name,
        "recall@%d" % k: round(float(np.mean(recalls)), 3),
        "p50_ms": round(float(np.percentile(lats, 50)), 3),
        "p95_ms": round(float(np.percentile(lats, 95)), 3),
        "build_s": round(build_s, 3),
        "memory_kb": round(store.memory_bytes() / 1024, 1),
        "mean_results": round(float(np.mean(counts)), 2),
    }


# ----------------------------------------------------------------------------
# Filtering modes: the distinction that decides enterprise suitability
# ----------------------------------------------------------------------------
def search_pre_filter(store, q, k=10, keep=None):
    """Restrict the eligible set, then search inside it. Correct result counts."""
    return store.search(q, k=k, where=keep)


def search_post_filter(store, q, k=10, keep=None):
    """Search first, then discard what the user may not see.
    Ask for 10, drop 7, return 3, and nothing reports a problem."""
    hits = store.search(q, k=k)                      # filter not applied yet
    return [(i, s) for i, s in hits if keep is None or keep(store.meta[i])]


def scale_corpus(M, meta, factor: int, seed: int = 0):
    """Grow the corpus with perturbed copies so latency and recall differences
    are visible at a realistic size. Copies are marked synthetic=True."""
    if factor <= 1:
        return M, meta
    rng = np.random.default_rng(seed)
    blocks, metas = [M], list(meta)
    for f in range(1, factor):
        noise = rng.normal(0, 0.05, M.shape).astype("float32")
        V = M + noise
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        blocks.append(V.astype("float32"))
        for m in meta:
            mm = dict(m); mm["synthetic"] = True; metas.append(mm)
    return np.vstack(blocks), metas
