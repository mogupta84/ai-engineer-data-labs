"""
Lab 2: three real vector databases behind one small interface.

  Chroma   chromadb 1.5.9, the vector database most developers named in Stack
           Overflow's 2025 survey. Graph index (HNSW).
  Qdrant   qdrant-edge-py 0.8.0, Qdrant's in-process edition (marked beta).
           Graph index (HNSW), plus compression.
  Milvus   Milvus Lite 3.2.1 through pymilvus, the vector database with the most
           GitHub stars. Graph index (HNSW), plus grouped (IVF) indexes.

All three run inside this Python process: no server, no Docker, no account. Each
one builds a real index and exposes the same query-time dial, called ef: how many
candidates the search keeps while it hops through the graph. More ef, more recall,
more time.

Three things this module does on purpose, each measured on 30 September 2026:
  - Chroma only applies a new ef after the collection is opened again, so
    set_effort() reopens it. Changing the setting on an open collection silently
    does nothing (recall stayed at 0.809 before and after the change).
  - Milvus Lite checks every stored row in Python before each search, so one
    question at a time costs about 30 ms at 100,000 rows. measure() therefore also
    times 200 questions sent in one call, where that check is paid once.
  - Every database is loaded the same way, 5,000 rows per call, so the loading
    pattern cannot tilt the result.

The database folders go in a temporary folder on the machine's own disk. On
Databricks that is /tmp, never a Unity Catalog volume: volumes reject the small
in-place writes these databases make.
"""
from __future__ import annotations

import os, time, shutil, tempfile, pathlib, importlib.metadata
from dataclasses import dataclass

import numpy as np

# Milvus Lite speaks gRPC to itself inside this process. Without this line gRPC
# prints harmless keep-alive messages into the notebook output.
os.environ.setdefault("GRPC_VERBOSITY", "NONE")
os.environ.setdefault("GLOG_minloglevel", "2")

DATABASES = ("chroma", "qdrant", "milvus")
PACKAGES = {"chroma": "chromadb", "qdrant": "qdrant-edge-py", "milvus": "milvus-lite"}
LOAD_BATCH = 5_000
EFFORTS = (10, 20, 40, 80, 160)
MIDDLE_EFFORT = 40


def versions() -> dict:
    """The installed version of each database package, or 'missing'."""
    out = {}
    for name, pkg in PACKAGES.items():
        try:
            out[name] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "missing"
    return out


# ----------------------------------------------------------------------------
# The benchmark set: vectors grouped in clusters, the way real embeddings are
# ----------------------------------------------------------------------------
@dataclass
class BenchSet:
    X: np.ndarray            # the stored vectors, one row each, unit length
    Q: np.ndarray            # the questions, unit length
    labels: np.ndarray       # one label per stored vector, 0 to n_labels-1, for the filter test
    truth: np.ndarray        # exact top 10 per question: the answer key
    exact_ms: float          # time exact search took per question, the "check every row" baseline


def make_benchmark_set(n: int = 100_000, dim: int = 128, n_questions: int = 200,
                       n_groups: int = 1_000, n_labels: int = 10, k: int = 10,
                       seed: int = 7) -> BenchSet:
    """n vectors in n_groups clusters, plus questions that sit near stored vectors.
    The answer key comes from exact search: every question against every vector."""
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(n_groups, dim)).astype("float32")
    X = centres[rng.integers(0, n_groups, n)] + 0.35 * rng.normal(size=(n, dim)).astype("float32")
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    Q = X[rng.choice(n, n_questions, replace=False)] + 0.05 * rng.normal(size=(n_questions, dim)).astype("float32")
    Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    labels = rng.integers(0, n_labels, n)
    X, Q = X.astype("float32"), Q.astype("float32")
    t0 = time.perf_counter()
    for q in Q[:20]:                               # time exact search one question at a time
        np.argpartition(-(X @ q), k)[:k]
    exact_ms = (time.perf_counter() - t0) * 1000 / 20
    truth = np.argsort(-(Q @ X.T), axis=1)[:, :k]
    return BenchSet(X=X, Q=Q, labels=labels, truth=truth, exact_ms=round(exact_ms, 2))


def exact_top_k(X, q, k=10, allowed=None):
    """Exact search, optionally only over the rows where allowed is True."""
    scores = X @ q
    if allowed is not None:
        scores = np.where(allowed, scores, -np.inf)
    return [int(i) for i in np.argsort(-scores)[:k] if np.isfinite(scores[i])]


def recall(truth_rows, got_rows, k=10) -> float:
    """Share of the true top k that came back, averaged over the questions."""
    return round(float(np.mean([len(set(map(int, t[:k])) & set(map(int, g[:k]))) / min(k, len(t))
                                for t, g in zip(truth_rows, got_rows)])), 3)


# ----------------------------------------------------------------------------
# One class per database, all with the same five methods
# ----------------------------------------------------------------------------
class _VectorDB:
    name = "?"
    dial = "ef"

    def __init__(self, folder=None):
        self.folder = pathlib.Path(folder or tempfile.mkdtemp(prefix=f"lab2_{self.name}_"))
        self.folder.mkdir(parents=True, exist_ok=True)
        self.effort = MIDDLE_EFFORT
        self.build_s = 0.0

    def build(self, X, labels=None) -> float:           # load every row, build the index, return seconds
        raise NotImplementedError

    def set_effort(self, ef: int):                      # the query-time dial
        self.effort = int(ef)

    def search(self, q, k=10, label=None) -> list:      # one question, row numbers of the top k
        raise NotImplementedError

    def search_many(self, Q, k=10) -> list:             # many questions in one call where the database allows it
        return [self.search(q, k) for q in Q]

    def close(self):
        pass

    def remove(self):
        self.close()
        shutil.rmtree(self.folder, ignore_errors=True)


class ChromaDB(_VectorDB):
    name = "chroma"
    dial = "ef_search"

    def _client(self):
        import chromadb
        from chromadb.config import Settings
        # anonymized_telemetry=False: Chroma otherwise sends usage pings to its makers.
        return chromadb.PersistentClient(path=str(self.folder), settings=Settings(anonymized_telemetry=False))

    def build(self, X, labels=None):
        self.client = self._client()
        cfg = {"hnsw": {"space": "cosine", "ef_construction": 100, "max_neighbors": 16, "ef_search": self.effort}}
        t0 = time.perf_counter()
        self.col = self.client.create_collection("freshcart", embedding_function=None, configuration=cfg)
        for i in range(0, len(X), LOAD_BATCH):
            j = min(len(X), i + LOAD_BATCH)
            meta = [{"label": int(v)} for v in labels[i:j]] if labels is not None else None
            self.col.add(ids=[str(r) for r in range(i, j)], embeddings=X[i:j], metadatas=meta)
        self.build_s = round(time.perf_counter() - t0, 1)
        return self.build_s

    def set_effort(self, ef):
        # Chroma keeps the old ef until the collection is opened again, so change it,
        # drop the cached client, and reopen from the folder.
        import chromadb
        self.effort = int(ef)
        self.col.modify(configuration={"hnsw": {"ef_search": self.effort}})
        chromadb.api.client.SharedSystemClient.clear_system_cache()
        self.client = self._client()
        self.col = self.client.get_collection("freshcart")

    def search(self, q, k=10, label=None):
        where = {"label": int(label)} if label is not None else None
        res = self.col.query(query_embeddings=np.asarray(q, dtype="float32")[None, :], n_results=k,
                             where=where, include=[])
        return [int(i) for i in res["ids"][0]]

    def search_many(self, Q, k=10):
        res = self.col.query(query_embeddings=np.asarray(Q, dtype="float32"), n_results=k, include=[])
        return [[int(i) for i in row] for row in res["ids"]]

    def close(self):
        try:
            import chromadb
            chromadb.api.client.SharedSystemClient.clear_system_cache()
        except Exception:
            pass


class QdrantDB(_VectorDB):
    name = "qdrant"
    dial = "hnsw_ef"

    def __init__(self, folder=None, compression=None, rescore=False):
        super().__init__(folder)
        self.compression = compression      # None, "int8" (4 times smaller) or "pq16" (16 times smaller)
        self.rescore = rescore              # re-check the top candidates with the full numbers

    def build(self, X, labels=None):
        import qdrant_edge as qe
        quant = None
        if self.compression == "int8":
            quant = qe.ScalarQuantizationConfig(type=qe.ScalarType.Int8, always_ram=True)
        elif self.compression == "pq16":
            quant = qe.ProductQuantizationConfig(compression=qe.CompressionRatio.X16, always_ram=True)
        cfg = qe.EdgeConfig(vectors=qe.EdgeVectorParams(size=X.shape[1], distance=qe.Distance.Cosine),
                            hnsw_config=qe.HnswIndexConfig(m=16, ef_construct=100, full_scan_threshold=10),
                            quantization_config=quant)
        t0 = time.perf_counter()
        (self.folder / "shard").mkdir(exist_ok=True)
        self.shard = qe.EdgeShard.create(str(self.folder / "shard"), cfg)
        if labels is not None:
            self.shard.update(qe.UpdateOperation.create_field_index("label", qe.PayloadSchemaType.Integer))
        for i in range(0, len(X), LOAD_BATCH):
            j = min(len(X), i + LOAD_BATCH)
            pts = [qe.Point(id=r, vector=X[r].tolist(), payload={"label": int(labels[r])} if labels is not None else None)
                   for r in range(i, j)]
            self.shard.update(qe.UpdateOperation.upsert_points(pts))
        self.shard.optimize()                           # builds the graph now, not on the first search
        self.build_s = round(time.perf_counter() - t0, 1)
        return self.build_s

    def search(self, q, k=10, label=None, exact=False):
        import qdrant_edge as qe
        quant = None
        if self.compression:
            quant = qe.QuantizationSearchParams(rescore=self.rescore, oversampling=2.0 if self.rescore else None)
        flt = None
        if label is not None:
            flt = qe.Filter(must=[qe.FieldCondition(key="label", match=qe.MatchValue(value=int(label)))])
        hits = self.shard.search(qe.SearchRequest(
            query=qe.Query.Nearest(np.asarray(q, dtype="float32").tolist()), limit=k, filter=flt,
            params=qe.SearchParams(hnsw_ef=self.effort, exact=exact, quantization=quant)))
        return [int(h.id) for h in hits]

    def close(self):
        try:
            self.shard.close()
        except Exception:
            pass


class MilvusDB(_VectorDB):
    name = "milvus"
    dial = "ef"

    def build(self, X, labels=None):
        from pymilvus import MilvusClient, DataType
        self.client = MilvusClient(str(self.folder / "milvus.db"))
        schema = MilvusClient.create_schema(auto_id=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("vec", DataType.FLOAT_VECTOR, dim=X.shape[1])
        schema.add_field("label", DataType.INT64)
        t0 = time.perf_counter()
        self.client.create_collection("freshcart", schema=schema)
        for i in range(0, len(X), LOAD_BATCH):
            j = min(len(X), i + LOAD_BATCH)
            self.client.insert("freshcart", [{"id": r, "vec": X[r].tolist(),
                                              "label": int(labels[r]) if labels is not None else 0}
                                             for r in range(i, j)])
        self.client.flush("freshcart")
        ip = self.client.prepare_index_params()
        ip.add_index(field_name="vec", index_type="HNSW", metric_type="COSINE", params={"M": 16, "efConstruction": 100})
        self.client.create_index("freshcart", ip)
        self.client.load_collection("freshcart")
        self.build_s = round(time.perf_counter() - t0, 1)
        return self.build_s

    def _params(self):
        return {"params": {"ef": max(self.effort, 10)}}

    def search(self, q, k=10, label=None):
        res = self.client.search("freshcart", data=[np.asarray(q, dtype="float32").tolist()], limit=k,
                                 anns_field="vec", search_params=self._params(),
                                 filter=f"label == {int(label)}" if label is not None else "")
        return [int(h["id"]) for h in res[0]]

    def search_many(self, Q, k=10):
        res = self.client.search("freshcart", data=np.asarray(Q, dtype="float32").tolist(), limit=k,
                                 anns_field="vec", search_params=self._params())
        return [[int(h["id"]) for h in row] for row in res]

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass


def open_db(name: str, **kw) -> _VectorDB:
    return {"chroma": ChromaDB, "qdrant": QdrantDB, "milvus": MilvusDB}[name](**kw)


# ----------------------------------------------------------------------------
# Measurements
# ----------------------------------------------------------------------------
def time_questions(db, Q, k=10, warmup=5):
    """p50 and p95 in milliseconds, one question at a time, after a short warm-up."""
    for q in Q[:warmup]:
        db.search(q, k)
    lat, got = [], []
    for q in Q:
        t0 = time.perf_counter()
        got.append(db.search(q, k))
        lat.append((time.perf_counter() - t0) * 1000)
    lat = np.array(lat)
    return got, round(float(np.percentile(lat, 50)), 3), round(float(np.percentile(lat, 95)), 3)


def measure(db, bench: BenchSet, k=10) -> dict:
    """Recall and time at the database's current effort: one question at a time, then
    all the questions in one call."""
    got, p50, p95 = time_questions(db, bench.Q, k)
    t0 = time.perf_counter()
    db.search_many(bench.Q, k)
    batch_ms = (time.perf_counter() - t0) * 1000 / len(bench.Q)
    return {"database": db.name, "ef": db.effort, "recall@10": recall(bench.truth, got, k),
            "p50_ms": p50, "p95_ms": p95, "ms_each_in_one_call": round(batch_ms, 3), "load_s": db.build_s}


def sweep(db, bench: BenchSet, efforts=EFFORTS, k=10, timed_questions=100) -> list[dict]:
    """Turn the dial. Recall uses every question; time uses the first timed_questions,
    one at a time, so the slowest database does not hold the room up."""
    rows = []
    for ef in efforts:
        db.set_effort(ef)
        got = db.search_many(bench.Q, k)
        _, p50, p95 = time_questions(db, bench.Q[:timed_questions], k)
        rows.append({"database": db.name, "ef": ef, "recall@10": recall(bench.truth, got, k),
                     "p50_ms": p50, "p95_ms": p95})
    db.set_effort(MIDDLE_EFFORT)
    return rows


def filter_test(db, bench: BenchSet, label=3, k=10, n_questions=20) -> dict:
    """Ask for k results among rows with one label (about 10 percent of the rows), two ways:
    the database's own filter, and a filter applied by hand to the unfiltered top k."""
    allowed = bench.labels == label
    db_counts, post_counts, db_got, truth = [], [], [], []
    for q in bench.Q[:n_questions]:
        inside = db.search(q, k, label=label)
        after = [r for r in db.search(q, k) if allowed[r]]
        db_counts.append(len(inside)); post_counts.append(len(after))
        db_got.append(inside); truth.append(exact_top_k(bench.X, q, k, allowed))
    return {"database": db.name, "asked for": k,
            "database filter returned": round(float(np.mean(db_counts)), 1),
            "filter after the search returned": round(float(np.mean(post_counts)), 1),
            "recall inside the filter": recall(truth, db_got, k)}


def compression_test(bench: BenchSet, ef=80, k=10) -> list[dict]:
    """Qdrant three ways: full numbers, int8 (4 times smaller) and product quantization
    (16 times smaller), each with and without re-checking the top candidates."""
    full_mb = bench.X.nbytes / 1e6
    rows = []
    for comp, factor in ((None, 1), ("int8", 4), ("pq16", 16)):
        db = QdrantDB(compression=comp)
        db.build(bench.X)
        db.set_effort(ef)
        for rescore in ((False, True) if comp else (False,)):
            db.rescore = rescore
            got, p50, _ = time_questions(db, bench.Q, k)
            rows.append({"stored as": {None: "full numbers", "int8": "int8, 4x smaller",
                                       "pq16": "PQ, 16x smaller"}[comp],
                         "vectors in memory, MB": round(full_mb / factor, 1),
                         "re-check": "yes" if rescore else "no",
                         "recall@10": recall(bench.truth, got, k), "p50_ms": p50})
        db.remove()
    return rows


def small_corpus_top3(dbs, M, q) -> dict:
    """The top 3 row numbers each database returns for one question on the lab corpus."""
    return {db.name: db.search(q, 3) for db in dbs}
