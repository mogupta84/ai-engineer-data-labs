"""Lab 4: grounded answering with verifiable citations and a refusal path."""
from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict

GROUNDING_PROMPT = """Answer using only the provided context.
If the context does not contain the answer, say you could not find it.
Cite the source id in square brackets for every factual claim.
If sources disagree, say so and prefer the most recent.
Do not infer beyond what the context states."""

@dataclass
class Answer:
    answer: str | None
    citations: list = field(default_factory=list)
    confidence: float = 0.0
    retrieved: list = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    def to_dict(self): return asdict(self)

def extract_citations(text: str) -> list[str]:
    return re.findall(r"\[([a-f0-9]{6,16})\]", text or "")

def verify_citations(text: str, retrieved_ids: list[str]) -> tuple[list[str], list[str]]:
    """Models cite chunks they never saw. Keep the ids you sent and assert."""
    cited = extract_citations(text)
    valid = [c for c in cited if c in retrieved_ids]
    phantom = [c for c in cited if c not in retrieved_ids]
    return valid, phantom

def answer_question(question, hits, generate, threshold=0.15) -> Answer:
    """hits: [(score, chunk)]. generate(prompt, context) -> text.
    Refusal is a success state, not a failure."""
    retrieved_ids = [c.id for _, c in hits]
    if not hits or hits[0][0] < threshold:
        return Answer(None, [], hits[0][0] if hits else 0.0, retrieved_ids,
                      True, "no sufficiently relevant context")
    context = "\n\n".join(f"[{c.id}] {c.text}" for _, c in hits)
    text = generate(GROUNDING_PROMPT, context, question)
    valid, phantom = verify_citations(text, retrieved_ids)
    if phantom:
        return Answer(None, [], hits[0][0], retrieved_ids, True,
                      f"unverifiable citations: {phantom}")
    if not valid:
        return Answer(None, [], hits[0][0], retrieved_ids, True, "no citation produced")
    return Answer(text, valid, hits[0][0], retrieved_ids, False, None)

def faithfulness(answer_text: str, hits) -> float:
    """Proportion of answer sentences whose content words appear in cited context."""
    if not answer_text: return 0.0
    ctx = " ".join(c.text.lower() for _, c in hits)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", answer_text) if s.strip()]
    if not sents: return 0.0
    ok = 0
    for s in sents:
        words = [w for w in re.findall(r"[a-z]{4,}", s.lower())]
        if not words: ok += 1; continue
        if sum(1 for w in words if w in ctx) / len(words) >= 0.6: ok += 1
    return round(ok / len(sents), 3)

def echo_generator(prompt, context, question=None):
    """Offline stand-in for a language model. Quotes the top context with its id,
    so the pipeline mechanics (citation, verification, refusal) are exercised."""
    first = context.split("\n\n")[0]
    cid = re.match(r"\[([a-f0-9]+)\]", first)
    body = first.split("] ", 1)[-1]
    return f"{body[:260]} [{cid.group(1) if cid else 'unknown'}]"
