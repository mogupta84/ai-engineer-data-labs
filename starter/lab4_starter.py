"""
LAB 4 STARTER: an answer service with citations that are checked in code.

    python3 starter/lab4_starter.py

Reference: labs/lab04_rag_api.py    Guided version: the lab04_rag_api notebook in your workspace
"""
import sys, pathlib, json, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from ragstack import RagStack
from rag import faithfulness
from labkit import load_golden, table, banner

THRESHOLD = 0.15      # TODO 4: the refusal threshold you would ship


def phantom_every_third(generate):
    """Fault injection: every third answer cites text that was never retrieved."""
    state = {"n": 0}
    def wrapped(prompt, context, question=None):
        text = generate(prompt, context, question)
        state["n"] += 1
        return text + " [deadbeef0000]" if state["n"] % 3 == 0 else text
    return wrapped


def main():
    svc = RagStack(False, threshold=THRESHOLD)
    gold = load_golden("qa_golden.json")
    questions = [(g, item) for g in ("answerable", "unanswerable") for item in gold[g]]

    # TODO 1: ask one question and print the whole response, not just the answer.
    #         Name each of the six fields and say who needs it.
    ans, hits = svc.ask("How many refund claims can a customer make in thirty days?")
    print(json.dumps(ans.to_dict(), indent=1)[:600])

    # TODO 2: turn on the phantom citation fault and count how many are caught.
    #         Nothing raises an error, so how would you have found this in production?

    # TODO 3: run all 25 questions and report the four numbers SEPARATELY:
    #         refusal rate on answerable, refusal rate on unanswerable, faithfulness,
    #         correct facts. Never report one refusal rate for both groups.
    rows = []
    for group, item in questions:
        a, h = svc.ask(item["question"])
        text = a.answer or ""
        rows.append({"id": item["id"], "group": group, "refused": a.refused,
                     "top score": round(h[0][0], 3) if h else 0.0,
                     "faithful": round(faithfulness(text, h), 3) if text else None,
                     "correct": (any(e.lower() in text.lower() for e in item.get("expect_any", []))
                                 if group == "answerable" else None)})
    print(table(rows, ["id", "group", "refused", "top score", "faithful", "correct"]))

    # TODO 4: sweep the threshold from 0.3 to 0.8 and show what each choice costs.
    #         Find the best operating point, then say why no point is clean.

    # TODO 5: list the answers that are fully grounded and still do not answer the
    #         question. Pick one and decide: retrieval, chunking, or the answer writer?

    # TODO 6: fill in handouts/lab4_answers.md.


if __name__ == "__main__":
    main()
