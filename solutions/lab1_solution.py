"""Lab 1 reference solution: full pipeline with the filter fix applied."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from freshcart import load_all, verify, chunk_docs, VectorIndex, current_only

QUERIES = [
    "how many refund claims can a customer make in thirty days",
    "who pays when food is spilled in transit",
    "how long does a customer have to submit photographic evidence",
    "when must an agent escalate to a supervisor",
    "what is the first response target for a spillage complaint",
]

def main():
    docs = load_all()
    print("=== verification ===")
    for r in verify(docs):
        print(f"  {r['source']:44s} units={r['units']:<3} chars={r['chars']:<6} {r['status']}")
    print("\n  -> support_escalation_sop_scanned.pdf has NO text layer. It is indexed as")
    print("     nothing, raises no error, and its content is unreachable. Fix: OCR at ingest.")

    chunks = chunk_docs(docs)
    idx = VectorIndex().build(chunks)
    print(f"\nindexed {len(chunks)} chunks\n")

    for q in QUERIES:
        print(f"Q: {q}")
        print("   unfiltered:")
        for sc, c in idx.search(q, k=2):
            flag = " <-- SUPERSEDED" if c.meta.get("superseded") else ""
            print(f"     {sc:.3f} {c.meta.get('source','')[:36]:36s}{flag}")
        print("   current only:")
        for sc, c in idx.search(q, k=2, where=current_only):
            print(f"     {sc:.3f} {c.meta.get('source','')[:36]:36s}")
        print()

    print("Teaching points:")
    print(" 1. 'who pays when food is spilled' ranks the SUPERSEDED 2022 policy first.")
    print("    Similarity is working perfectly; it is not measuring currency.")
    print(" 2. 'when must an agent escalate' cannot be answered at all: the SOP that")
    print("    answers it extracted zero characters, silently.")
    print(" 3. The recency filter fixes (1) with one metadata field and no model change.")

if __name__ == "__main__":
    main()
