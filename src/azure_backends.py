"""
Azure track: the same lab steps, backed by Azure services.

  Azure OpenAI           embeddings and chat (grounded answers, NL2SQL, reranking)
  Azure AI Search        managed vector + keyword index, hybrid queries, filters
  PostgreSQL + pgvector  vectors next to relational data, row-level security
  Document Intelligence  OCR for the scanned SOP that extracts zero characters
  Language (PII)         PII detection at ingestion
  Application Insights   one log record per answer, queried with KQL

Every call uses the keys in lab.env, so a student needs no Azure login.
"""
from __future__ import annotations
import os, re, json, time, datetime, pathlib
import numpy as np

from labenv import student_id


# ============================================================== usage and cost
class Usage:
    """Counts tokens so every lab can print what the Azure track actually cost."""
    def __init__(self):
        import threading
        self.chat_in = self.chat_out = self.embed = self.calls = 0
        self.lock = threading.Lock()

    def cost_usd(self):
        # List prices per 1M tokens (GlobalStandard, 2026): gpt-4.1-mini 0.40 in /
        # 1.60 out; text-embedding-3-small 0.02. Check the Azure pricing page.
        return round(self.chat_in / 1e6 * 0.40 + self.chat_out / 1e6 * 1.60
                     + self.embed / 1e6 * 0.02, 6)

    def line(self):
        return (f"Azure OpenAI usage: {self.calls} chat calls, {self.chat_in} tokens in, "
                f"{self.chat_out} out, {self.embed} embedding tokens, about ${self.cost_usd():.4f}")


USAGE = Usage()
_tls = __import__("threading").local()


def thread_usage(reset=False):
    """Tokens used by chat calls made in THIS thread, so a lab running questions in
    parallel can still attribute cost to each answer."""
    if reset or not hasattr(_tls, "used"):
        _tls.used = {"in": 0, "out": 0}
    return _tls.used


# ============================================================== Azure OpenAI
_client = None


def openai_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(base_url=os.environ["AZURE_OPENAI_BASE_URL"],
                         api_key=os.environ["AZURE_OPENAI_API_KEY"], max_retries=5, timeout=90)
    return _client


def chat_deployment():
    return os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]


def chat(messages, temperature=0.0, max_tokens=700, json_mode=False) -> str:
    """One chat completion. Reasoning models (gpt-5 family) do not accept a
    temperature, so it is only sent to models that support it."""
    model = chat_deployment()
    kwargs = {"model": model, "messages": messages}
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        kwargs["max_completion_tokens"] = max_tokens * 4
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    r = openai_client().chat.completions.create(**kwargs)
    with USAGE.lock:
        USAGE.calls += 1
        if r.usage:
            USAGE.chat_in += r.usage.prompt_tokens or 0
            USAGE.chat_out += r.usage.completion_tokens or 0
    if r.usage:
        used = thread_usage()
        used["in"] += r.usage.prompt_tokens or 0
        used["out"] += r.usage.completion_tokens or 0
    return (r.choices[0].message.content or "").strip()


def azure_generator(prompt, context, question=None):
    """Drop-in replacement for rag.echo_generator: a real model, same contract."""
    return chat([
        {"role": "system", "content": prompt + "\nCite chunk ids exactly as written in the "
                                               "context, for example [3f9a1c2b7d4e]."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ], temperature=0.0, max_tokens=400)


def llm_rerank(query, candidates, k=5, max_chars=600):
    """Second-stage relevance scoring with the chat model. Not a cross-encoder,
    but the same two-stage shape: score each (query, passage) pair together,
    then keep the best k. candidates: [(score, chunk)]."""
    if not candidates:
        return []
    passages = "\n\n".join(f"[{i}] {' '.join(c.text.split())[:max_chars]}"
                           for i, (_, c) in enumerate(candidates))
    text = chat([
        {"role": "system", "content":
            "You grade how well each passage answers the query. Return JSON: "
            '{"scores": [{"i": <passage number>, "score": <0 to 3>}]}. '
            "3 = directly answers, 2 = relevant, 1 = related topic, 0 = unrelated. "
            "Grade every passage."},
        {"role": "user", "content": f"Query: {query}\n\nPassages:\n{passages}"},
    ], json_mode=True, max_tokens=60 + 18 * len(candidates))
    try:
        scores = {int(s["i"]): float(s["score"]) for s in json.loads(text)["scores"]}
    except Exception:
        scores = {}
    # ties keep the first-stage order, which carries real signal
    ranked = sorted(range(len(candidates)), key=lambda i: (-scores.get(i, 0.0), i))
    return [(scores.get(i, 0.0) / 3.0, candidates[i][1]) for i in ranked[:k]]


# ============================================================== Azure AI Search
SEARCH_API = "2024-07-01"


def _search(method, path, body=None, ok=(200, 201, 204)):
    import requests
    url = f"{os.environ['AZURE_SEARCH_ENDPOINT'].rstrip('/')}/{path}"
    url += ("&" if "?" in url else "?") + f"api-version={SEARCH_API}"
    r = requests.request(method, url, json=body, timeout=60,
                         headers={"api-key": os.environ["AZURE_SEARCH_KEY"],
                                  "Content-Type": "application/json"})
    if r.status_code not in ok:
        raise RuntimeError(f"AI Search {method} {path} failed: {r.status_code} {r.text[:400]}")
    return r.json() if r.text.strip() else {}


def search_index_name():
    return os.getenv("AZURE_SEARCH_INDEX", "freshcart-chunks")


class AzureSearchIndex:
    """One shared index for the class (the Free tier allows 3). Each document
    carries an owner field, so students never overwrite each other."""

    def __init__(self, name=None, dims=1536):
        self.name = name or search_index_name()
        self.dims = dims
        self.owner = student_id()

    def definition(self):
        f = lambda name, typ="Edm.String", **kw: {"name": name, "type": typ, **kw}
        return {
            "name": self.name,
            "fields": [
                f("id", key=True, filterable=True),
                f("owner", filterable=True, facetable=True),
                f("chunk_id", filterable=True),
                f("text", searchable=True, analyzer="en.microsoft"),
                f("source", filterable=True, facetable=True),
                f("page", "Edm.Int32", filterable=True),
                f("doc_type", filterable=True, facetable=True),
                f("effective_date", filterable=True, sortable=True),
                f("version", filterable=True),
                f("superseded", "Edm.Boolean", filterable=True, facetable=True),
                f("sensitivity", filterable=True),
                f("region", filterable=True),
                f("synthetic", "Edm.Boolean", filterable=True),
                f("embedding", "Collection(Edm.Single)", searchable=True,
                  dimensions=self.dims, vectorSearchProfile="hnsw-profile"),
            ],
            "vectorSearch": {
                "algorithms": [{"name": "hnsw", "kind": "hnsw",
                                "hnswParameters": {"m": 16, "efConstruction": 200,
                                                   "efSearch": 100, "metric": "cosine"}}],
                "profiles": [{"name": "hnsw-profile", "algorithm": "hnsw"}],
            },
        }

    def exists(self):
        try:
            _search("GET", f"indexes/{self.name}")
            return True
        except RuntimeError:
            return False

    def create(self):
        if not self.exists():
            _search("PUT", f"indexes/{self.name}", self.definition())
        return self

    def upload(self, chunks, vectors, extra_meta=None):
        docs = []
        for c, v in zip(chunks, vectors):
            m = dict(c.meta, **(extra_meta or {}))
            docs.append({
                "@search.action": "mergeOrUpload",
                "id": f"{self.owner}-{c.id}", "owner": self.owner, "chunk_id": c.id,
                "text": c.text, "source": m.get("source"),
                "page": m.get("page") or m.get("slide"),
                "doc_type": m.get("doc_type"), "effective_date": m.get("effective_date"),
                "version": m.get("version"), "superseded": bool(m.get("superseded", False)),
                "sensitivity": m.get("sensitivity", "standard"), "region": m.get("region"),
                "synthetic": bool(m.get("synthetic", False)),
                "embedding": [float(x) for x in v],
            })
        for i in range(0, len(docs), 200):
            res = _search("POST", f"indexes/{self.name}/docs/index", {"value": docs[i:i + 200]},
                          ok=(200, 207))
            bad = [d for d in res.get("value", []) if not d.get("status")]
            if bad:
                raise RuntimeError(f"{len(bad)} documents failed to index: {bad[0]}")
        return len(docs)

    def sync(self, chunks, vectors):
        """Make this student's documents match the corpus exactly. Comparing ids and
        text, not counts: a chunking change keeps the count and changes every id, and
        an edited document can keep its chunk ids while the text changes."""
        live = {d["chunk_id"]: d.get("text") for d in self.query(None, None, k=1000,
                                                                select="chunk_id,text")}
        if live == {c.id: c.text for c in chunks}:
            return False
        self.delete_owner_docs()
        self.upload(chunks, vectors)
        time.sleep(2)                         # the index is near real time, not instant
        return True

    def delete_owner_docs(self, source=None):
        flt = f"owner eq '{self.owner}'" + (f" and source eq '{source}'" if source else "")
        ids = [d["id"] for d in self.query(None, None, k=1000, flt=flt, own_only=False,
                                           select="id")]
        for i in range(0, len(ids), 500):
            _search("POST", f"indexes/{self.name}/docs/index",
                    {"value": [{"@search.action": "delete", "id": x} for x in ids[i:i + 500]]})
        return len(ids)

    def count(self, flt=None):
        body = {"search": "*", "top": 0, "count": True}
        if flt:
            body["filter"] = flt
        return _search("POST", f"indexes/{self.name}/docs/search", body).get("@odata.count", 0)

    def query(self, text, vector, k=10, mode="hybrid", flt=None, own_only=True,
              exhaustive=False, filter_mode="preFilter", select=None):
        """mode: keyword | vector | hybrid. Hybrid fuses both lists with RRF
        inside the service, which is what Lab 3 builds by hand."""
        filters = []
        if own_only:
            filters.append(f"owner eq '{self.owner}'")
        if flt:
            filters.append(f"({flt})")
        body = {"top": k, "select": select or "id,chunk_id,text,source,page,superseded,"
                                                "effective_date,sensitivity,region,synthetic"}
        if filters:
            body["filter"] = " and ".join(filters)
        if mode in ("keyword", "hybrid") and text:
            body["search"] = text
        if mode in ("vector", "hybrid") and vector is not None:
            body["vectorQueries"] = [{"kind": "vector", "vector": [float(x) for x in vector],
                                      "fields": "embedding", "k": k, "exhaustive": exhaustive}]
            body["vectorFilterMode"] = filter_mode
        if "search" not in body and "vectorQueries" not in body:
            body["search"] = "*"
        return _search("POST", f"indexes/{self.name}/docs/search", body).get("value", [])


def search_hits_to_chunks(rows, chunks_by_id):
    """AI Search returns documents; the rest of the lab code wants (score, Chunk)."""
    out = []
    for r in rows:
        c = chunks_by_id.get(r.get("chunk_id"))
        if c is not None:
            out.append((float(r.get("@search.score", 0.0)), c))
    return out


# ============================================================== PostgreSQL + pgvector
def pg_connect():
    """Azure Database for PostgreSQL, or the local pgvector container
    (setup/pgvector_docker.cmd). lab.env decides which."""
    import psycopg
    return psycopg.connect(host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")),
                           user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"],
                           dbname=os.environ["PGDATABASE"],
                           sslmode=os.getenv("PGSSLMODE") or "prefer",
                           connect_timeout=5 if os.environ["PGHOST"] in ("localhost", "127.0.0.1") else 20,
                           autocommit=True)


def _vec(v):
    return "[" + ",".join(f"{float(x):.6f}" for x in v) + "]"


class PgVectorStore:
    """Vectors in a Postgres table beside their metadata, HNSW index on top.
    Same build/search/memory_bytes contract as the stores in stores.py."""
    name = "pgvector-hnsw"

    def __init__(self, table=None, ef_search=40, iterative=False):
        self.table = table or f"chunks_{student_id()}"
        self.ef_search, self.iterative = ef_search, iterative
        self.con = None
        self.meta = None

    def _connect(self):
        if self.con is None:
            self.con = pg_connect()
            self.con.execute("CREATE EXTENSION IF NOT EXISTS vector")
        return self.con

    def build(self, M, meta, chunks=None):
        con = self._connect()
        t = time.perf_counter()
        dims = M.shape[1]
        con.execute(f"DROP TABLE IF EXISTS {self.table}")
        con.execute(f"""CREATE TABLE {self.table} (
            i INTEGER PRIMARY KEY, chunk_id TEXT, source TEXT, superseded BOOLEAN,
            sensitivity TEXT, region TEXT, body TEXT, embedding vector({dims}))""")
        rows = []
        for i in range(len(M)):
            m = meta[i]
            rows.append((i, chunks[i].id if chunks else None, m.get("source"),
                         bool(m.get("superseded", False)), m.get("sensitivity", "standard"),
                         m.get("region"), chunks[i].text if chunks else None, _vec(M[i])))
        with con.cursor() as cur:
            with cur.copy(f"COPY {self.table} (i, chunk_id, source, superseded, sensitivity, "
                          f"region, body, embedding) FROM STDIN") as cp:
                for r in rows:
                    cp.write_row(r)
        con.execute(f"CREATE INDEX ON {self.table} USING hnsw (embedding vector_cosine_ops) "
                    f"WITH (m = 16, ef_construction = 64)")
        con.execute(f"ANALYZE {self.table}")
        self.meta = meta
        return time.perf_counter() - t

    def search(self, q, k=10, where=None, where_sql=None):
        con = self._connect()
        con.execute(f"SET hnsw.ef_search = {int(self.ef_search)}")
        if self.iterative:
            try:                                    # pgvector 0.8.0 or newer
                con.execute("SET hnsw.iterative_scan = relaxed_order")
            except Exception as e:
                print(f"  (iterative scan not available in this pgvector version: {e})")
                self.iterative = False
        sql = f"SELECT i, 1 - (embedding <=> %s::vector) FROM {self.table}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        qv = _vec(q)
        rows = con.execute(sql, (qv, qv, k)).fetchall()
        out = [(int(i), float(s)) for i, s in rows]
        if where:
            out = [(i, s) for i, s in out if where(self.meta[i])]
        return out

    def memory_bytes(self):
        con = self._connect()
        return con.execute("SELECT pg_total_relation_size(%s)", (self.table,)).fetchone()[0]


# ============================================================== Document Intelligence
def ocr_pdf(path: pathlib.Path) -> str:
    """Azure AI Document Intelligence 'prebuilt-read': text out of a scanned PDF."""
    import requests
    endpoint = os.environ["AZURE_AI_ENDPOINT"].rstrip("/")
    headers = {"Ocp-Apim-Subscription-Key": os.environ["AZURE_AI_KEY"]}
    url = (f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze"
           f"?api-version=2024-11-30")
    r = requests.post(url, headers={**headers, "Content-Type": "application/pdf"},
                      data=pathlib.Path(path).read_bytes(), timeout=120)
    if r.status_code != 202:
        raise RuntimeError(f"Document Intelligence failed: {r.status_code} {r.text[:300]}")
    op = r.headers["Operation-Location"]
    for _ in range(120):
        time.sleep(1)
        res = requests.get(op, headers=headers, timeout=60).json()
        if res.get("status") == "succeeded":
            return res["analyzeResult"].get("content", "")
        if res.get("status") == "failed":
            raise RuntimeError(f"OCR failed: {json.dumps(res)[:300]}")
    raise TimeoutError("OCR did not finish in 2 minutes")


# ============================================================== Language: PII
def detect_pii_azure(texts: list[str], categories=None) -> list[dict]:
    """Azure AI Language PII detection. Returns, per text, the entities found
    and the service's own redacted copy."""
    import requests
    endpoint = os.environ["AZURE_AI_ENDPOINT"].rstrip("/")
    url = f"{endpoint}/language/:analyze-text?api-version=2024-11-01"
    out = []
    for start in range(0, len(texts), 5):          # 5 documents per synchronous call
        batch = texts[start:start + 5]
        params = {"modelVersion": "latest"}
        if categories:
            params["piiCategories"] = categories
        body = {"kind": "PiiEntityRecognition", "parameters": params,
                "analysisInput": {"documents": [
                    {"id": str(i), "language": "en", "text": t} for i, t in enumerate(batch)]}}
        r = requests.post(url, json=body, timeout=60,
                          headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_AI_KEY"]})
        if r.status_code != 200:
            raise RuntimeError(f"Language PII failed: {r.status_code} {r.text[:300]}")
        docs = {d["id"]: d for d in r.json()["results"]["documents"]}
        for i in range(len(batch)):
            d = docs.get(str(i), {})
            out.append({"entities": [{"kind": e["category"], "value": e["text"],
                                      "confidence": e["confidenceScore"]}
                                     for e in d.get("entities", [])],
                        "redacted": d.get("redactedText", batch[i])})
    return out


# ============================================================== Application Insights
def track_event(name: str, properties: dict, measurements: dict | None = None) -> bool:
    """Sends one custom event. In the portal: Application Insights > Logs >
    customEvents (or AppEvents in the Log Analytics workspace)."""
    import requests
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    parts = dict(p.split("=", 1) for p in conn.split(";") if "=" in p)
    ikey = parts.get("InstrumentationKey")
    if not ikey:
        return False
    ingest = parts.get("IngestionEndpoint", "https://dc.services.visualstudio.com/").rstrip("/")
    envelope = {
        "name": "Microsoft.ApplicationInsights.Event",
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "iKey": ikey,
        "tags": {"ai.cloud.role": "freshcart-rag", "ai.user.id": student_id()},
        "data": {"baseType": "EventData", "baseData": {
            "ver": 2, "name": name,
            "properties": {k: (v if isinstance(v, str) else json.dumps(v))
                           for k, v in properties.items()},
            "measurements": {k: float(v) for k, v in (measurements or {}).items()},
        }},
    }
    r = requests.post(f"{ingest}/v2.1/track", json=[envelope], timeout=20)
    return r.status_code == 200


# ============================================================== NL2SQL
def azure_generate_sql(question: str, schema_text: str, definitions: str | None,
                       few_shot: list[tuple[str, str]]) -> str:
    """Schema-grounded SQL from the chat model. Returns one SELECT statement."""
    parts = [f"Schema:\n{schema_text}"]
    if definitions:
        parts.append(f"Business definitions (always apply):\n{definitions}")
    if few_shot:
        parts.append("Examples:\n" + "\n".join(f"Q: {q}\nSQL: {s}" for q, s in few_shot))
    parts.append(f"Question: {question}\nSQL:")
    text = chat([
        {"role": "system", "content": "You translate questions into ONE SQLite SELECT "
                                      "statement. Use only the tables and columns in the "
                                      "schema. Reply with the SQL only: no explanation, "
                                      "no code fences."},
        {"role": "user", "content": "\n\n".join(parts)},
    ], temperature=0.0, max_tokens=400)
    text = re.sub(r"^```(?:sql)?\s*|\s*```$", "", text.strip(), flags=re.I)
    return text.strip()
