"""
Lab 1, step 2: two tools that read the layout for you, judged by the same three
checks as the repair you just ran by hand.

Docling is free and open source (started at IBM, now an LF AI & Data project). It
runs a layout model over every page, so it can rebuild paragraphs, keep a table
under its heading, and read a scanned page with OCR.

ai_parse_document is Databricks' own document reader: a SQL function, generally
available on Azure Databricks since 16 April 2026 in some regions, and paid for
under AI Functions. It reads PDF, Word, PowerPoint and images, but not Excel.

Both are much heavier than the loaders in freshcart.py, so neither runs inside
the notebook's own Python. Docling gets its own install folder and runs in a
separate process; ai_parse_document runs on Databricks' side. Where a tool
cannot run, the cells show what it returned when the lab was built, recorded in
data/golden/layout_tools_recorded.json.
"""
from __future__ import annotations
import html, importlib.util, json, os, pathlib, re, subprocess, sys, time

from freshcart import ROOT, RAW

RECORDED = ROOT / "data" / "golden" / "layout_tools_recorded.json"
DOCLING_DIR = ROOT / "data" / "cache" / "docling_pkgs"   # Docling's own install, outside the notebook's Python
MODELS_DIR = ROOT / "data" / "cache" / "docling_models"  # where its layout and OCR models are downloaded

CONTRACT = "partner_agreement_extract.pdf"
SLA = "support_sla_matrix.docx"
SCAN = "support_escalation_sop_scanned.pdf"
CLAUSE_41 = ("Where a refund is issued to a customer, the cost of that refund is borne by the party "
             "responsible for the underlying failure")

# ai_parse_document cannot open a spreadsheet, so it is never sent one.
AI_PARSE_FORMATS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def on_databricks() -> bool:
    return bool(os.environ.get("DATABRICKS_RUNTIME_VERSION"))


def files(raw_dir: pathlib.Path = RAW) -> list[pathlib.Path]:
    return sorted(p for p in raw_dir.iterdir() if p.is_file())


# ----------------------------------------------------------------------------
# The three checks. Each one is a question with a known answer for these files.
# ----------------------------------------------------------------------------
def checks(text_by_file: dict[str, str]) -> dict[str, object]:
    """The same three questions for every reader, asked of the text it produced.
    1. Does clause 4.1 of the contract come back as ONE line, not broken at the column edge?
    2. Does the Word table sit under its heading, before the Notes that follow it?
    3. How many characters came back from the scanned page?"""
    lines = [" ".join(line.split()) for line in text_by_file.get(CONTRACT, "").splitlines()]
    sla = text_by_file.get(SLA, "")
    head, p3, notes = (sla.find("Turnaround targets by priority"), sla.find("P3"), sla.find("Notes"))
    return {
        "clause 4.1 on one line": any(CLAUSE_41 in line for line in lines),
        "table under its heading": min(head, p3, notes) >= 0 and head < p3 < notes,
        "characters from the scan": len(text_by_file.get(SCAN, "").strip()),
    }


def texts_from_docs(docs) -> dict[str, str]:
    """freshcart.Doc objects, from any loader, joined into one text per source file."""
    out: dict[str, list[str]] = {}
    for d in docs:
        out.setdefault(d.meta.get("source", "?"), []).append(d.text)
    return {name: "\n\n".join(parts) for name, parts in out.items()}


# ----------------------------------------------------------------------------
# Docling, free. Installed on first use into data/cache, then run in its own process.
# ----------------------------------------------------------------------------
_DOCLING_RUN = r'''
import json, pathlib, sys, time
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
out = {}
for p in sys.argv[1:]:
    t0 = time.perf_counter()
    try:
        text = converter.convert(p).document.export_to_markdown()
        out[pathlib.Path(p).name] = {"text": text, "seconds": round(time.perf_counter() - t0, 1)}
    except Exception as e:
        out[pathlib.Path(p).name] = {"text": "", "error": (type(e).__name__ + ": " + str(e))[:300],
                                     "seconds": round(time.perf_counter() - t0, 1)}
print("@@RESULT@@" + json.dumps(out))
'''


def docling_ready() -> bool:
    return (DOCLING_DIR / "docling").exists() or importlib.util.find_spec("docling") is not None


def docling_install() -> float:
    """Installs Docling into its own folder, once per session. On Linux, which is what
    Databricks runs, it asks for the CPU build of PyTorch: the default build carries
    about 2 GB of GPU libraries that a notebook without a GPU never uses."""
    if docling_ready():
        return 0.0
    t0 = time.perf_counter()
    cmd = [sys.executable, "-m", "pip", "install", "-q", "--target", str(DOCLING_DIR), "docling"]
    if sys.platform.startswith("linux"):
        cmd += ["--extra-index-url", "https://download.pytorch.org/whl/cpu"]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("Docling did not install:\n" + done.stderr[-1500:])
    return time.perf_counter() - t0


def docling_read(paths: list[pathlib.Path], timeout: float | None = None) -> dict:
    """Runs Docling over the files in a separate process and returns, per file, the text
    it produced (as Markdown) and the seconds it took. timeout stops a first run that is
    stuck downloading models, instead of letting the cell hang."""
    env = dict(os.environ)
    if (DOCLING_DIR / "docling").exists():
        env["PYTHONPATH"] = str(DOCLING_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    env.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
    env.setdefault("EASYOCR_MODULE_PATH", str(MODELS_DIR / "easyocr"))
    # Databricks sets OPENSSL_FORCE_FIPS_MODE=0, which means FIPS mode is off. A library that
    # Docling installs bundles an older OpenSSL that treats the variable merely being SET as
    # "on", fails its FIPS self-test, and stops the process. FIPS is off on the machine either
    # way, so the variable is left out of Docling's process, and only when its value is "0".
    if env.get("OPENSSL_FORCE_FIPS_MODE") == "0":
        del env["OPENSSL_FORCE_FIPS_MODE"]
    try:
        done = subprocess.run([sys.executable, "-c", _DOCLING_RUN, *map(str, paths)],
                              capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Docling did not finish within {timeout:.0f} seconds")
    marker = [line for line in done.stdout.splitlines() if line.startswith("@@RESULT@@")]
    if not marker:
        raise RuntimeError("Docling stopped before it finished:\n" + done.stderr[-1500:])
    return json.loads(marker[-1][len("@@RESULT@@"):])


# ----------------------------------------------------------------------------
# ai_parse_document, paid. Databricks only.
# ----------------------------------------------------------------------------
def _table_text(html_table: str) -> str:
    """ai_parse_document returns a table as HTML. Turn it into one line per row."""
    t = re.sub(r"(?i)</t[dh]>", " | ", html_table)
    t = re.sub(r"(?i)</tr>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return "\n".join(" ".join(line.split()).rstrip(" |") for line in html.unescape(t).splitlines() if line.strip())


def ai_parse_read(paths: list[pathlib.Path]) -> tuple[dict, float]:
    """Sends the files to ai_parse_document in one query and returns, per file, the text
    of its elements in document order, the element types, and any errors it reported.
    The files live on this session's disk, not in a volume, so their bytes go in a
    DataFrame column. Figure descriptions are switched off: they cost extra and these
    files have no figures."""
    from pyspark.sql import SparkSession
    spark = SparkSession.getActiveSession()
    rows = [(p.name, p.read_bytes()) for p in paths if p.suffix.lower() in AI_PARSE_FORMATS]
    df = spark.createDataFrame(rows, "name string, content binary")
    t0 = time.perf_counter()
    got = df.selectExpr(
        "name",
        "to_json(ai_parse_document(content, map('version', '2.0', 'descriptionElementTypes', ''))) AS parsed",
    ).collect()
    seconds = time.perf_counter() - t0
    out = {}
    for r in got:
        parsed = json.loads(r["parsed"] or "{}")
        elements = (parsed.get("document") or {}).get("elements") or []
        parts, kinds = [], []
        for e in elements:
            kinds.append(e.get("type"))
            if e.get("type") in ("page_header", "page_footer", "page_number"):
                continue
            content = e.get("content") or ""
            parts.append(_table_text(content) if e.get("type") == "table" else content.strip())
        out[r["name"]] = {"text": "\n\n".join(p for p in parts if p), "types": kinds,
                          "errors": parsed.get("error_status") or []}
    return out, seconds


# ----------------------------------------------------------------------------
# What each tool returned when the lab was built, for places where it cannot run.
# ----------------------------------------------------------------------------
def recorded(tool: str) -> dict:
    return json.loads(RECORDED.read_text(encoding="utf-8"))[tool]


def per_file(results: dict, raw_dir: pathlib.Path = RAW) -> list[dict]:
    """One row per source file: characters returned, or why nothing came back."""
    rows = []
    for p in files(raw_dir):
        r = results.get(p.name)
        if r is None:
            rows.append({"source": p.name, "characters": "-", "note": "not sent: format not supported"})
        elif r.get("error"):
            rows.append({"source": p.name, "characters": 0, "note": r["error"][:60]})
        else:
            n = len(r["text"].strip())
            rows.append({"source": p.name, "characters": n,
                         "note": "" if n else "nothing came back"})
    return rows
