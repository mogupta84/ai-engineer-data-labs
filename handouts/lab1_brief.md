# Lab 1: Ingest five formats into one indexed corpus

**Time** 55 to 75 minutes · **Pairs** · `starter/lab1_starter.py`

## Goal
Build a working ingestion pipeline over the FreshCart corpus, and find everything
that breaks along the way. The failures are the deliverable, not the pipeline.

## Steps
1. **Load.** Run the starter. Seven files, several formats.
2. **Verify.** Read the verification table before you index anything. One source
   extracts zero characters. Find it.
3. **Chunk.** Compare fixed, recursive and structural on the 2024 policy. Judge
   which first chunk could answer a question on its own.
4. **Index and query.** Run the five test queries.
5. **Filter.** Re-run with `where=current_only` and compare.

## Definition of done
- [ ] Verification table printed and the empty source identified
- [ ] You can say which chunking strategy you chose per document type, and why
- [ ] Five test queries run, results recorded
- [ ] You found the query where the superseded policy outranks the current one
- [ ] `lab1_answers.md` completed

## If you are stuck
- Environment problems: ask immediately, do not debug quietly.
- Past 45 minutes with nothing running: open `solutions/lab1_solution.py`,
  read it, then come back. Reading a solution is not cheating; being stuck
  silently for an hour is the only way to waste this lab.
