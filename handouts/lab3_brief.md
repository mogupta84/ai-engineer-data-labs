# Lab 3: Hybrid retrieval, reranking and the lift

**Time** 75 minutes · **Pairs** · main module: `src/retrieval.py`

## Build
- Add BM25 alongside your vector search
- Fuse the two lists with reciprocal rank fusion
- Rerank the top 50 down to 5
- Add a recency filter using Week 1 metadata
- Judge relevance for 20 of your own queries

## Definition of done
- [ ] nDCG@10 at four stages: dense, hybrid, +rerank, +filter
- [ ] Which Week 1 failures now work
- [ ] Added latency at each stage
- [ ] One query that got WORSE, and your theory why

## Note from the trainer
Hybrid should beat dense clearly. The offline reranker is a lexical proxy and may not add much on this small corpus. Report what you measure, not what you expect.

## If you are stuck
Environment problems: ask immediately. Past the halfway mark with nothing running:
read the reference in `solutions/`, then come back. Being stuck silently is the
only way to waste this lab.
