"""
LAB 1 STARTER: ingest five formats into one indexed corpus.

Work through the TODOs in order. Run this file often; it prints as it goes.
A working reference is in solutions/lab1_solution.py; use it if you are stuck
past the 45 minute mark, not before.

    python3 starter/lab1_starter.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from freshcart import (load_all, verify, chunk_docs, VectorIndex,
                       chunk_fixed, chunk_recursive, chunk_structural, current_only)

TEST_QUERIES = [
    "how many refund claims can a customer make in thirty days",
    "who pays when food is spilled in transit",
    "how long does a customer have to submit photographic evidence",
    "when must an agent escalate to a supervisor",
    "what is the first response target for a spillage complaint",
]


def step1_load():
    print("\n=== STEP 1: load ===")
    docs = load_all()
    print(f"loaded {len(docs)} document units from data/raw")
    return docs


def step2_verify(docs):
    print("\n=== STEP 2: verify extraction (do NOT skip) ===")
    for r in verify(docs):
        print(f"  {r['source']:44s} units={r['units']:<3} chars={r['chars']:<6} {r['status']}")
    # TODO 1: one source extracts zero characters. Which, and why?
    #         Write your answer in handouts/lab1_answers.md.
    #         What would you do about it in production?


def step3_chunk(docs):
    print("\n=== STEP 3: chunk ===")
    # TODO 2: compare strategies on the 2024 refund policy.
    #         Print the first chunk from each and judge which is retrievable alone.
    policy = next(d for d in docs if "refund_policy_v3_2024" in d.meta.get("source", ""))
    for name, fn in (("fixed", chunk_fixed), ("recursive", chunk_recursive),
                     ("structural", chunk_structural)):
        pieces = fn(policy.text)
        first = " ".join(pieces[0].split())[:150]
        print(f"  {name:11s} -> {len(pieces):2d} chunks | first: {first}...")

    # TODO 3: chunk_docs() picks a strategy per document type. Read strategy_for()
    #         in src/freshcart.py. Do you agree with the choices? Change one and
    #         note what happens to the queries below.
    chunks = chunk_docs(docs)
    print(f"  total chunks: {len(chunks)}")
    return chunks


def step4_index(chunks):
    print("\n=== STEP 4: embed and index ===")
    idx = VectorIndex().build(chunks)
    print(f"  indexed {len(chunks)} chunks, dim {idx.M.shape[1]}")
    return idx


def step5_query(idx):
    print("\n=== STEP 5: run the test queries ===")
    for q in TEST_QUERIES:
        print(f"\nQ: {q}")
        for score, c in idx.search(q, k=3):
            sup = c.meta.get("superseded")
            flag = "  <-- SUPERSEDED" if sup else ""
            print(f"   {score:.3f}  {c.meta.get('source','')[:34]:34s} "
                  f"{' '.join(c.text.split())[:70]}{flag}")

    # TODO 4: at least one query returns the SUPERSEDED 2022 policy above the
    #         current 2024 one. Find it. Why does similarity not help here?
    #
    # TODO 5: re-run the same query with the recency filter and compare:
    #             idx.search(q, k=3, where=current_only)
    #         This single filter is the fix. Add it below and prove it works.


def main():
    docs = step1_load()
    step2_verify(docs)
    chunks = step3_chunk(docs)
    idx = step4_index(chunks)
    step5_query(idx)
    print("\nDone. Now complete handouts/lab1_answers.md before the debrief.")


if __name__ == "__main__":
    main()
