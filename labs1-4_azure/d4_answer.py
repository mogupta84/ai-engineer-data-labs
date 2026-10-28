"""Lab 9, D4: an agent that answers from the documents, with sources, and says so when they do not answer
(Lab 4, in Azure). The agent is Microsoft Agent Framework, as in Lab 8; its one tool searches the shared index.

    python d4_answer.py                score Lab 4's 25 questions: 20 the documents answer, 5 they do not
    python d4_answer.py --ask "..."    ask your own question
    python d4_answer.py --fake         add a made-up source to every third answer: a test of the checking code

Code, not the model, checks the sources: an answer must cite at least one piece, and only pieces the search
returned. An answer with no source counts as unsupported, not right.
"""
import asyncio        # Agent Framework agents run asynchronously
import json           # save every answer
import re             # find the sources an answer cites
import sys            # read the options
from typing import Annotated

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

from docs_common import INDEX, SIGN_IN, golden, setting

REFUSAL = "I could not find the answer in the documents."
INSTRUCTIONS = f"""You answer questions for FreshCart support staff from FreshCart's documents.
Call search_documents first. Answer only from the pieces it returns, and cite each fact with the piece's id in
square brackets, like [3f2a9c1d7e44]. If the pieces do not answer the question, reply exactly: {REFUSAL}"""

search = SearchClient(setting("SEARCH_ENDPOINT"), INDEX, AzureKeyCredential(setting("SEARCH_QUERY_KEY")))
seen = []                                                              # the ids the search returned, per answer


def search_documents(question: Annotated[str, "The question, in the user's words"]) -> list:
    """Search FreshCart's current documents (policy, partner agreement, SLA, escalation SOP, quarterly review,
    claims register) and return the 5 best pieces, each with its id, file and text."""
    found = search.search(search_text=question, top=5, select=["id", "file", "content"], filter="current eq true",
                          vector_queries=[VectorizableTextQuery(text=question, k_nearest_neighbors=10, fields="vector")])
    pieces = [{"id": p["id"], "file": p["file"], "text": p["content"]} for p in found]
    seen.extend(p["id"] for p in pieces)
    return pieces


def check(answer):
    """The sources an answer cites, and which of them the search never returned. One bracket may hold several
    ids, like [3f2a9c1d7e44, 8b0e5a6f1c22]: each id counts."""
    cited = [i for group in re.findall(r"\[([0-9a-f, ]+)\]", answer) for i in re.findall(r"[0-9a-f]{12}", group)]
    return cited, [c for c in cited if c not in seen]


async def ask(agent, question, fake=False):
    seen.clear()
    answer = (await asyncio.wait_for(agent.run(question), 120)).text.strip()
    if fake:
        answer += " [deadbeef0000]"                                    # a source no search returned
    cited, unknown = check(answer)
    refused = answer.startswith(REFUSAL[:25])
    return {"answer": answer, "refused": refused, "cited": cited, "unknown": unknown,
            "unsupported": not refused and not set(cited) - set(unknown)}   # cited nothing the search returned


async def main():
    client = FoundryChatClient(project_endpoint=setting("FOUNDRY_PROJECT_ENDPOINT"), model="gpt-4.1-mini",
                               credential=SIGN_IN)
    agent = Agent(client, INSTRUCTIONS, name="DocsAgent", tools=[search_documents])
    if "--ask" in sys.argv:
        r = await ask(agent, sys.argv[sys.argv.index("--ask") + 1])
        print(r["answer"], f"\n\nsources {r['cited']}, not from the search: {r['unknown'] or 'none'}")
        return
    qa = golden("qa_golden.json")
    log, right, refused_good, refused_bad, fakes, caught, flagged = [], 0, 0, 0, 0, 0, 0
    for n, q in enumerate(qa["answerable"]):
        fake = "--fake" in sys.argv and n % 3 == 0
        r = await ask(agent, q["question"], fake)
        ok = not r["refused"] and not r["unsupported"] and any(e.lower() in r["answer"].lower() for e in q["expect_any"])
        right += ok; refused_good += r["refused"]; fakes += fake; caught += fake and "deadbeef0000" in r["unknown"]
        log.append({**q, **r, "right": ok})
        verdict = "RIGHT" if ok else "refused" if r["refused"] else "NO SOURCE" if r["unsupported"] else "WRONG"
        print(f"{q['id']} {verdict}  sources {len(r['cited'])}"
              f"{'  NOT FROM SEARCH ' + str(r['unknown']) if r['unknown'] else ''}")
    for q in qa["unanswerable"]:
        r = await ask(agent, q["question"])
        refused_bad += r["refused"]; flagged += r["unsupported"]
        log.append({**q, **r})
        verdict = "refused" if r["refused"] else "ANSWERED, NO SOURCE" if r["unsupported"] else "ANSWERED"
        print(f"{q['id']} {verdict}  {r['answer'][:90]!r}")
    print(f"\nRight facts: {right} of 20. Refused, though answerable: {refused_good} of 20. "
          f"Refused, as it should: {refused_bad} of 5; answered with no source: {flagged} of 5.")
    if fakes:
        print(f"Made-up sources added: {fakes}, caught by the check: {caught}")
    json.dump(log, open("answers_docs.json", "w"), indent=1)


asyncio.run(main())
