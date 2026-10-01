"""
Day 1 tool step: the same seven files through three loaders.

Three ways to turn data/raw into text: the loaders in freshcart.py that this
course writes by hand, LangChain's document loaders, and LlamaIndex's file
readers. All three return freshcart.Doc objects, so verify() scores them the
same way and the comparison is like for like.

Install what the frameworks need before importing this module:

    pip install langchain-community docx2txt llama-index-core llama-index-readers-file
"""
from __future__ import annotations
import pathlib, time

from freshcart import Doc, RAW, load_all


# ----------------------------------------------------------------------------
# Loader 1: the ones written by hand in this course
# ----------------------------------------------------------------------------
def load_ours(raw_dir: pathlib.Path = RAW) -> tuple[list[Doc], list[tuple[str, str]]]:
    """Returns (docs, skipped). Nothing is ever skipped: every format has a
    loader, because we wrote one for each."""
    return load_all(raw_dir), []


# ----------------------------------------------------------------------------
# Loader 2: LangChain
# ----------------------------------------------------------------------------
# LangChain ships a loader per format. PyPDFLoader and Docx2txtLoader need only
# small packages. Its PowerPoint and Excel loaders both go through the
# 'unstructured' package, which is a much larger install, so this comparison
# leaves them out and records that as a result rather than hiding it.
LANGCHAIN_NATIVE = {".pdf", ".docx"}
LANGCHAIN_NEEDS_UNSTRUCTURED = {".pptx", ".xlsx", ".ppt", ".xls"}


def load_langchain(raw_dir: pathlib.Path = RAW) -> tuple[list[Doc], list[tuple[str, str]]]:
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader

    docs: list[Doc] = []
    skipped: list[tuple[str, str]] = []
    for p in sorted(raw_dir.iterdir()):
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            for i, d in enumerate(PyPDFLoader(str(p)).load(), start=1):
                docs.append(Doc(text=d.page_content,
                                meta={"source": p.name, "page": i, "format": "pdf",
                                      **{k: v for k, v in d.metadata.items() if k != "source"}}))
        elif suffix == ".docx":
            for d in Docx2txtLoader(str(p)).load():
                docs.append(Doc(text=d.page_content,
                                meta={"source": p.name, "format": "docx"}))
        elif suffix in LANGCHAIN_NEEDS_UNSTRUCTURED:
            skipped.append((p.name, "needs the unstructured package"))
        else:
            skipped.append((p.name, "no loader for this format"))
    return docs, skipped


# ----------------------------------------------------------------------------
# Loader 3: LlamaIndex
# ----------------------------------------------------------------------------
def load_llamaindex(raw_dir: pathlib.Path = RAW) -> tuple[list[Doc], list[tuple[str, str]]]:
    """SimpleDirectoryReader points at a folder and picks a reader per file
    extension. One call covers all five formats, which is the thing LangChain
    needed a second package for."""
    from llama_index.core import SimpleDirectoryReader

    reader = SimpleDirectoryReader(input_dir=str(raw_dir), filename_as_id=True)
    docs: list[Doc] = []
    for node in reader.load_data():
        meta = dict(node.metadata or {})
        name = meta.get("file_name") or pathlib.Path(meta.get("file_path", "?")).name
        docs.append(Doc(text=node.text,
                        meta={"source": name,
                              "format": pathlib.Path(name).suffix.lstrip(".").lower(),
                              **{k: v for k, v in meta.items()
                                 if k not in ("file_name", "file_path")}}))
    seen = {d.meta["source"] for d in docs}
    skipped = [(p.name, "reader returned nothing") for p in sorted(raw_dir.iterdir())
               if p.is_file() and p.name not in seen]
    return docs, skipped


LOADERS = {"ours": load_ours, "langchain": load_langchain, "llamaindex": load_llamaindex}


# ----------------------------------------------------------------------------
# Running all three and lining the answers up
# ----------------------------------------------------------------------------
def run_all(raw_dir: pathlib.Path = RAW, which: list[str] | None = None) -> dict:
    """Runs each loader over the same folder and records what came back, how
    long it took, and what it refused to read."""
    out = {}
    for name in (which or list(LOADERS)):
        t0 = time.perf_counter()
        docs, skipped = LOADERS[name](raw_dir)
        out[name] = {"docs": docs, "skipped": skipped,
                     "seconds": round(time.perf_counter() - t0, 2)}
    return out


def per_file(results: dict, raw_dir: pathlib.Path = RAW) -> list[dict]:
    """One row per source file, with units and characters from each loader.
    A dash means that loader never read the file at all, which is a different
    failure from reading it and getting nothing."""
    names = list(results)
    rows = []
    for p in sorted(raw_dir.iterdir()):
        if not p.is_file():
            continue
        row = {"source": p.name}
        for name in names:
            mine = [d for d in results[name]["docs"] if d.meta.get("source") == p.name]
            if not mine:
                row[f"{name} units"] = "-"
                row[f"{name} chars"] = "-"
            else:
                row[f"{name} units"] = len(mine)
                row[f"{name} chars"] = sum(len(d.text.strip()) for d in mine)
        rows.append(row)
    return rows


def find_text(results: dict, loader: str, source: str, needle: str, window: int = 190) -> str:
    """The text one loader produced around a phrase, so two loaders can be read
    side by side on exactly the same part of the document."""
    for d in results[loader]["docs"]:
        if d.meta.get("source") != source:
            continue
        i = d.text.find(needle)
        if i >= 0:
            start = max(0, i - 40)
            return " ".join(d.text[start:start + window].split())
    return "(phrase not found in what this loader produced)"


def metadata_keys(results: dict) -> dict[str, list[str]]:
    """Every metadata key each loader attached, anywhere. Metadata you do not
    have is metadata you cannot filter on later, which is the whole of step 5."""
    out = {}
    for name, r in results.items():
        keys = set()
        for d in r["docs"]:
            keys.update(d.meta)
        out[name] = sorted(keys)
    return out
