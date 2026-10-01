"""Shared plumbing for the lab scripts in labs/. Nothing here is a lab answer."""
from __future__ import annotations
import json, os, time, pathlib, contextlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from freshcart import (ROOT, RAW, load_all, verify, chunk_docs, VectorIndex, apply_ocr,
                       get_embedder, Chunk, Doc)

GOLDEN = ROOT / "data" / "golden"
CACHE = ROOT / "data" / "cache"


@dataclass
class Corpus:
    docs: list
    chunks: list
    index: VectorIndex

    @property
    def by_id(self):
        return {c.id: c for c in self.chunks}


def ocr_cached(path: pathlib.Path) -> str:
    """OCR each scanned file once. The recognised text is kept in data/cache so
    re-running a lab does not pay Document Intelligence again."""
    from azure_backends import ocr_pdf
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"ocr_{path.stem}.txt"
    if out.exists():
        return out.read_text(encoding="utf-8")
    text = ocr_pdf(path)
    out.write_text(text, encoding="utf-8")
    return text


def build_corpus(azure: bool, ocr: bool = True, quiet: bool = False, raw_dir=RAW) -> Corpus:
    docs = load_all(raw_dir)
    if azure and ocr:
        docs = apply_ocr(docs, ocr_cached, raw_dir)
    chunks = chunk_docs(docs)
    index = VectorIndex(get_embedder()).build(chunks)
    if not quiet:
        emb = index.embedder
        print(f"corpus: {len(docs)} document units, {len(chunks)} chunks, "
              f"embedder {emb.name}, dim {index.M.shape[1]}")
    return Corpus(docs, chunks, index)


def load_golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def relevance(item: dict, chunks: list) -> dict:
    """Grades every chunk for one golden query using its text rules."""
    grades = {}
    for c in chunks:
        g = 0
        for rule in item["rules"]:
            if c.meta.get("source") == rule["source"] and _norm(rule["contains"]) in _norm(c.text):
                g = max(g, rule["grade"])
        if g:
            grades[c.id] = g
    return grades


@contextlib.contextmanager
def stopwatch(store: dict, key: str):
    t = time.perf_counter()
    yield
    store[key] = store.get(key, 0.0) + (time.perf_counter() - t) * 1000


def table(rows: list[dict], cols: list[str] | None = None, width: int = 12) -> str:
    if not rows:
        return "(no rows)"
    cols = cols or list(rows[0].keys())
    fmt = lambda v: (f"{v:.3f}" if isinstance(v, float) else str(v))
    widths = {c: max(len(c), *(len(fmt(r.get(c, ""))) for r in rows)) for c in cols}
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    out = [line, "  ".join("-" * widths[c] for c in cols)]
    for r in rows:
        out.append("  ".join(fmt(r.get(c, "")).ljust(widths[c]) for c in cols))
    return "\n".join(out)


def banner(text: str):
    print(f"\n=== {text} ===")


def pmap(fn, items, azure: bool):
    """Runs fn over items, in order. On the Azure track most time is spent waiting
    for the network, so six requests run at once (set FRESHCART_WORKERS to change)."""
    workers = int(os.getenv("FRESHCART_WORKERS", "6" if azure else "1"))
    items = list(items)
    if workers <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))
