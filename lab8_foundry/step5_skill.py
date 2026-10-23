"""Lab 8, step 5: the same agent, with a skill. The refund procedure moves out of the instructions into
skills/refund-decision/SKILL.md, written once. The agent sees only the skill's name and description until a
request needs it, then loads the steps.

    python step5_skill.py --runs 3         the 9 cases, 3 times each: compare with step 1
    python step5_skill.py --ask "..."      your own question
    python step5_skill.py --chat           chat, with memory, as in step 3
"""
import asyncio
import pathlib                                   # find the skills folder
import logging                                   # show the memory library's warnings
import os                                        # read the project address
import re                                         # make your account name a valid memory scope
import sys                                       # read --chat
import time                                      # time each tool call
from typing import Annotated                     # describe each parameter for the model

from agent_framework import Agent, function_middleware, SkillsProvider, FileSkillsSource
from agent_framework.foundry import FoundryMemoryProvider    # long-term memory, kept in a Foundry memory store
from azure.identity.aio import AzureCliCredential           # sign in as you, as the model client does

from freshcart_tools import TOOLS, get_official_number
from lab8_common import make_client, ask, run_cases, options, who_am_i, TIME_LIMIT

# New in step 5: short instructions. The refund procedure is in the skill now, not here. The compare_months line
# from step 4 stays; the eight refund rules went into the skill.
INSTRUCTIONS = """You are FreshCart's support agent. You help support staff with refund requests and business numbers.
Use your skills and tools. Use get_official_number for business numbers.
Use compare_months to compare a business number between two months; never work out a change yourself."""
SKILLS = pathlib.Path(__file__).parent / "skills"   # each skill is one folder with a SKILL.md


# New in step 4: your own tool. An ordinary function; its name, docstring and parameter notes are all the model sees.
def compare_months(
        metric: Annotated[str, "revenue, order_count or refund_rate"],
        first_month: Annotated[str, "The earlier month, YYYY-MM, within 2024"],
        second_month: Annotated[str, "The later month, YYYY-MM, within 2024"]) -> dict:
    """Compare one official FreshCart number between two months of 2024: both values, the change, and the
    change in percent of the first month."""
    a, b = get_official_number(metric, first_month), get_official_number(metric, second_month)
    if not (a.get("ok") and b.get("ok")):
        return {"ok": False, "message": a.get("message") or b.get("message")}
    change = b["value"] - a["value"]
    percent = round(change / a["value"] * 100, 1) if a["value"] else None
    return {"ok": True, "metric": metric, "first_month": first_month, "first_value": a["value"],
            "second_month": second_month, "second_value": b["value"],
            "change": round(change, 4), "change_percent": percent}


@function_middleware
async def trace_tool(context, call_next):
    """New in step 2: runs around every tool call the agent makes. Prints what it asked for and what came back."""
    start = time.time()
    print(f"    tool {context.function.name}, asked with {dict(context.arguments)}")
    await call_next()                                            # the tool itself runs here
    result = context.result                                      # the tool's answer, as the agent will read it
    text = " ".join(str(getattr(part, "text", part)) for part in result) if isinstance(result, list) else str(result)
    text = " ".join(text.split())                               # one line: no line breaks or runs of spaces
    print(f"    tool {context.function.name}, answered in {time.time() - start:.1f}s: {text[:150]}")


MEMORY_STORE = "lab8-memory"                     # the class memory store, made once by the trainer


async def chat(agent, you):
    """New in step 3: a conversation. One session per chat; the memory store outlives every chat."""
    session = agent.create_session()             # short-term memory: everything said in this chat
    print(f"Chatting as {you}. Type new for a new chat, bye to stop.")
    while True:
        try:
            text = input("\nyou: ").strip()
        except (EOFError, KeyboardInterrupt):    # Ctrl+C or the end of the input: stop quietly
            break
        if text.lower() == "bye":
            break
        if text.lower() == "new":
            session = agent.create_session()     # a new chat: the session forgets, the memory store does not
            print("(new chat)")
            continue
        try:
            response = await asyncio.wait_for(agent.run(text, session=session), TIME_LIMIT)
        except asyncio.TimeoutError:
            print(f"agent: (no answer: gave up after {TIME_LIMIT} seconds)")
            continue
        print(f"agent: {response.text}")


async def main():
    runs, only, question = options()
    client = make_client()
    # New in step 2: one line sends traces to the Application Insights linked to the Foundry project.
    # enable_sensitive_data=True also records the prompts and answers; fine for a class, not for real customers.
    await client.configure_azure_monitor(enable_sensitive_data=True)
    # New in step 5: the skills, from the skills folder. No approvals: this skill has steps and a reference file,
    # and no scripts to run.
    skills = SkillsProvider(FileSkillsSource(SKILLS, script_extensions=()), disable_load_skill_approval=True,
                            disable_read_skill_resource_approval=True, disable_run_skill_script_approval=True)
    if "--chat" in sys.argv:
        # New in step 3: long-term memory. It reads what it knows about you before each answer, and saves what it
        # learnt after it (update_delay=0: at once, not after 5 minutes of quiet).
        you = who_am_i()                         # your class account, so your memories stay yours
        scope = re.sub(r"[^A-Za-z0-9_-]", "_", you)   # a scope allows only letters, digits, - and _: no @ or dots
        logging.getLogger("agent_framework_foundry").addHandler(logging.StreamHandler())   # show memory errors here
        async with AzureCliCredential() as credential, FoundryMemoryProvider(
                project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential,
                memory_store_name=MEMORY_STORE, scope=scope, update_delay=0) as memory:
            try:                                 # a missing store fails quietly later, so check it now
                await memory.project_client.beta.memory_stores.get(MEMORY_STORE)
            except Exception as error:
                raise SystemExit(f"Cannot open the memory store {MEMORY_STORE}; tell your trainer. ({error})")
            agent = Agent(client, INSTRUCTIONS, name="SupportAgent", tools=TOOLS + [compare_months], middleware=[trace_tool],
                          context_providers=[skills, memory])
            await chat(agent, you)
        return
    agent = Agent(client, INSTRUCTIONS, name="SupportAgent", tools=TOOLS + [compare_months], middleware=[trace_tool],
                  context_providers=[skills])                                                 # no memory
    if question:
        answer, calls, seconds = await ask(agent, question)
        print(answer, f"\n\ntools called: {calls}, {seconds}s")
    else:
        await run_cases(agent, runs, only)
    print("\nTraces sent to Azure; they show up there after 1 to 2 minutes.")

if __name__ == "__main__":                       # run only when started, not when another step imports it
    asyncio.run(main())
