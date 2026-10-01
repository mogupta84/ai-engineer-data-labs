# Lab 2: Benchmark three vector databases and pick one

**Time** 80 minutes · **Pairs** · `notebooks/lab02_vector_stores.ipynb` · `starter/lab2_starter.py`

## Goal
Produce a recall-versus-latency curve for Chroma, Qdrant and Milvus, and a one-page
memo your architect would accept: which database, at which setting, against which target.

## Steps
1. **The FreshCart pieces** in all three databases: same answers as exact search, and why 30 pieces prove nothing about speed.
2. **Scale up**: 100,000 vectors and 200 questions, with the answer key from exact search. Be ready to say what it does *not* tell you.
3. **Measure** all three at ef 40: recall@10, p50, p95, load time, one question at a time and 200 in one call.
4. **Sweep `ef`** over 10, 20, 40, 80, 160. Predict the shape before you run it.
5. **Compression**: Qdrant stored 4 and 16 times smaller, with and without re-checking.
6. **Filter test**: ask for ten inside a filter that keeps 1 row in 10, with the database's own filter and with a filter applied afterwards.
7. **Databricks AI Search**: the trainer's shared index, same questions, same answer key. No dial to turn.
8. **Operating point**: your targets, the cheapest setting that meets them, and your pick.
9. **Memo.**

## Definition of done
- [ ] All three databases measured on recall@10, p50, p95 and load time
- [ ] The `ef` curve for each, with the elbow identified
- [ ] The compression rows, with what re-checking wins back
- [ ] Filter result counts, with the difference explained
- [ ] The Your write-up cell in the notebook completed

## Predict before you measure
Write these down before step 4. Raising `ef` from 10 to 160 does what to:
recall, p95 latency, memory usage?
