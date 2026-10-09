# Lab 4: A RAG API with verifiable citations

**Time** 80 minutes · **Pairs** · main module: `src/rag.py`

## Build
- An endpoint over your Lab 3 retrieval stack
- Grounded prompt with refusal explicitly permitted
- Chunk-level citations in the response
- Code that verifies every cited id was actually retrieved
- A relevance threshold below which you refuse
- All five response-contract fields

## Definition of done
- [ ] 20 answerable and 5 unanswerable questions
- [ ] Faithfulness on the answerable set
- [ ] Refusal rate on each set, REPORTED SEPARATELY
- [ ] At least one caught phantom citation
- [ ] One answer that is faithful but unhelpful

## Note from the trainer
The two refusal rates separately is the discipline. One number hides everything.

## If you are stuck
Environment problems: ask immediately. Past the halfway mark with nothing running:
read the reference in `solutions/`, then come back. Being stuck silently is the
only way to waste this lab.
