"""Shared by the Lab 8 scripts: the model client, and a runner that asks the 9 cases and scores the answers."""
import asyncio        # Agent Framework agents run asynchronously
import os             # read the project address from an environment variable
import sys            # read the command-line options
import json           # save every answer, so it can be re-scored without asking again
import base64         # read your account name from your sign-in token
import time           # time each answer
import pathlib        # name the answers file after the step you ran

from azure.identity import AzureCliCredential          # sign in as you: the account signed in to Azure CLI
from agent_framework.foundry import FoundryChatClient  # Agent Framework's client for models in a Foundry project

from cases import CASES, is_right                      # the 9 cases and their right answers

MODEL = "gpt-4.1-mini"                                 # the same model as Labs 5 to 7
TIME_LIMIT = 120                                       # seconds one answer may take before we give up on it


async def run_agent(agent, text):
    """Run an agent once, but never wait more than TIME_LIMIT seconds: a stuck call must not stop the whole lab."""
    return await asyncio.wait_for(agent.run(text), TIME_LIMIT)


def make_client():
    """A chat client for the class Foundry project, signed in as you. No key."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")   # your trainer gives you this address
    if not endpoint:
        sys.exit("Set FOUNDRY_PROJECT_ENDPOINT first: export FOUNDRY_PROJECT_ENDPOINT=<the address your trainer gives you> "
                 "(Windows PowerShell: $env:FOUNDRY_PROJECT_ENDPOINT=\"<address>\")")
    return FoundryChatClient(project_endpoint=endpoint, model=MODEL, credential=AzureCliCredential())


def who_am_i():
    """The class account you signed in with (az login), read from your sign-in token. Used to keep your memories
    apart from your classmates', even when every VM has the same login name."""
    token = AzureCliCredential().get_token("https://management.azure.com/.default").token
    claims = token.split(".")[1]                                          # the middle part of the token says who you are
    claims = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
    return claims.get("upn") or claims.get("unique_name") or claims["oid"]


def tool_calls(response):
    """The names of the tools the agent called, in order, read from the response messages."""
    names = []
    for message in response.messages:
        for content in message.contents:
            if getattr(content, "type", "") == "function_call":
                names.append(content.name)
    return names


async def ask(agent, question):
    """Ask once, in a new conversation, and return the answer text, the tools it called and the seconds taken."""
    start = time.time()
    try:
        response = await run_agent(agent, question)
    except asyncio.TimeoutError:
        return f"(no answer: gave up after {TIME_LIMIT} seconds)", [], round(time.time() - start, 1)
    return response.text, tool_calls(response), round(time.time() - start, 1)


async def run_cases(agent, runs=1, only=None, show=True):
    """Ask every case (or only some) `runs` times; print each answer's decision line and the score."""
    right = total = 0
    log = []                                                    # every answer, for later reading or re-scoring
    for case_id, question, expected in CASES:
        if only and case_id not in only:
            continue
        for run in range(runs):
            answer, calls, seconds = await ask(agent, question)
            ok = is_right(case_id, answer)
            right += ok; total += 1
            log.append({"case": case_id, "try": run + 1, "answer": answer, "tools": calls, "seconds": seconds})
            last = [line for line in answer.splitlines() if line.strip()][-1][:110] if answer.strip() else "(no answer)"
            print(f"case {case_id} try {run + 1}: {'RIGHT' if ok else 'WRONG'} (expected {expected}) | tools {calls} | {seconds}s")
            if show:
                print(f"    {last}")
    print(f"\nScore: {right} of {total} answers right")
    script = pathlib.Path(sys.argv[0]).stem                     # the step you ran, e.g. step1_agent
    with open(f"answers_{script}.json", "w") as file:           # e.g. answers_step1_agent.json, one file per step
        json.dump(log, file, indent=1)
    return right, total


def options():
    """Command-line options: --runs N (tries per case), --case 1,4 to ask only some cases, --ask "your own question"."""
    args = sys.argv[1:]
    runs = int(args[args.index("--runs") + 1]) if "--runs" in args else 1
    only = args[args.index("--case") + 1].split(",") if "--case" in args else None
    question = args[args.index("--ask") + 1] if "--ask" in args else None
    return runs, only, question
