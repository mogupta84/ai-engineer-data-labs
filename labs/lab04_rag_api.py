"""
LAB 4: a RAG API with verifiable citations.

    python labs/lab04_rag_api.py                    evaluate on the golden set
    python labs/lab04_rag_api.py --threshold 0.5    same, stricter refusal
    python labs/lab04_rag_api.py --inject-phantom   prove citation checking works
    python labs/lab04_rag_api.py serve              start the API on http://127.0.0.1:8000
    python labs/lab04_rag_api.py ask "How many refund claims can a customer make?"
Add --azure to any of these for Azure AI Search + Azure OpenAI.

Retrieval is the Lab 3 stack: hybrid, recency filter, rerank, top 5.
The response contract: answer, citations, confidence, retrieved, refused (+ reason).

TRY THIS: the default threshold refuses almost nothing that is unanswerable.
Tune --threshold until unanswerable questions are refused WITHOUT refusing
answerable ones. Report both refusal rates, separately.
"""
import sys, pathlib, json, time, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from labenv import setup_track, arg_value
AZURE = setup_track("Lab 4: RAG API with verifiable citations", needs=("openai", "search"))

from rag import faithfulness, Answer
from ragstack import RagStack
from labkit import load_golden, table, banner, pmap

THRESHOLD = float(arg_value("--threshold", "0.15"))


def make_stack():
    stack = RagStack(AZURE, threshold=THRESHOLD)
    if "--inject-phantom" in sys.argv:
        stack.generate = phantom_every_third(stack.generate)
    return stack


def phantom_every_third(generate):
    """Fault injection: every third answer cites a chunk id that was never retrieved."""
    state = {"n": 0}

    def wrapped(prompt, context, question=None):
        text = generate(prompt, context, question)
        state["n"] += 1
        return text + " [deadbeef0000]" if state["n"] % 3 == 0 else text
    return wrapped


def contract(ans: Answer, hits):
    d = ans.to_dict()
    d["retrieved"] = [{"id": c.id, "source": c.meta.get("source"), "score": round(s, 3)}
                      for s, c in hits]
    return d


def evaluate():
    svc = make_stack()
    gold = load_golden("qa_golden.json")
    rows = []
    t0 = time.perf_counter()
    todo = [(group, item) for group in ("answerable", "unanswerable") for item in gold[group]]
    answers = pmap(lambda gi: svc.ask(gi[1]["question"]), todo, AZURE)
    for (group, item), (ans, hits) in zip(todo, answers):
            text = ans.answer or ""
            correct = (not ans.refused and
                       any(e.lower() in text.lower() for e in item.get("expect_any", [])))
            rows.append({
                "id": item["id"], "group": group, "refused": ans.refused,
                "reason": (ans.refusal_reason or "")[:38],
                "top_score": round(hits[0][0], 3) if hits else 0.0,
                "faithful": faithfulness(text, hits) if text else None,
                "correct": correct if group == "answerable" else None,
                "answer": text.replace("\n", " ")[:90],
            })
    elapsed = time.perf_counter() - t0

    banner(f"per question (threshold {THRESHOLD})")
    print(table(rows, ["id", "group", "refused", "top_score", "faithful", "correct", "reason"]))

    ansb = [r for r in rows if r["group"] == "answerable"]
    unans = [r for r in rows if r["group"] == "unanswerable"]
    answered = [r for r in ansb if not r["refused"]]
    phantoms = [r for r in rows if r["reason"].startswith("unverifiable citations")]
    banner("the numbers for your debrief")
    print(f"  refusal rate, answerable   : {sum(r['refused'] for r in ansb)}/{len(ansb)}"
          f"  (should be LOW)")
    print(f"  refusal rate, unanswerable : {sum(r['refused'] for r in unans)}/{len(unans)}"
          f"  (should be HIGH)")
    if answered:
        print(f"  faithfulness, answered     : {statistics.mean(r['faithful'] for r in answered):.3f}")
        print(f"  correct facts, answerable  : {sum(bool(r['correct']) for r in ansb)}/{len(ansb)}")
    print(f"  phantom citations caught   : {len(phantoms)}")
    print(f"  time for {len(rows)} questions : {elapsed:.1f}s")

    unhelpful = [r for r in answered if (r["faithful"] or 0) >= 0.8 and not r["correct"]]
    banner("faithful but unhelpful (grounded, yet it does not answer the question)")
    for r in unhelpful[:3]:
        q = next(i["question"] for i in gold["answerable"] if i["id"] == r["id"])
        print(f"  {r['id']} Q: {q}\n      A: {r['answer']}")
    if not unhelpful:
        print("  none found this run")
    if AZURE:
        from azure_backends import USAGE
        print("\n" + USAGE.line())


def serve():
    import uvicorn
    from fastapi import FastAPI
    from pydantic import BaseModel

    svc = make_stack()
    app = FastAPI(title="FreshCart RAG API", version="1.0")

    class AskRequest(BaseModel):
        question: str
        threshold: float = THRESHOLD

    @app.get("/health")
    def health():
        return {"status": "ok", "chunks": len(svc.corpus.chunks), "azure": AZURE}

    @app.post("/ask")
    def ask(req: AskRequest):
        ans, hits = svc.ask(req.question, req.threshold)
        return contract(ans, hits)

    print("API ready: open http://127.0.0.1:8000/docs in a browser. Ctrl+C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=int(arg_value("--port", "8000")), log_level="warning")


def ask_cli():
    import urllib.request
    question = next((a for a in sys.argv[2:] if not a.startswith("--")), None)
    if not question:
        raise SystemExit('usage: python labs/lab04_rag_api.py ask "your question"')
    req = urllib.request.Request(f"http://127.0.0.1:{arg_value('--port', '8000')}/ask",
                                 data=json.dumps({"question": question}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        print(json.dumps(json.loads(r.read()), indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "eval"
    {"eval": evaluate, "serve": serve, "ask": ask_cli}[cmd]()
