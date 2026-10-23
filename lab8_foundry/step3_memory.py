"""Lab 8, step 3: the same agent, now with memory. Two kinds, as in Lab 7:
a session remembers this conversation (a follow-up can say "that order"), and a Foundry memory store remembers
you across conversations (say once that you want answers in Hindi; a new chat still answers in Hindi).

    python step3_memory.py --chat          chat with the agent; type new for a new chat, bye to stop
    python step3_memory.py --case 4        the cases still work as before, without memory
"""
import asyncio
import logging                                   # show the memory library's warnings
import os                                        # read the project address
import re                                         # make your account name a valid memory scope
import sys                                       # read --chat
import time                                      # time each tool call

from agent_framework import Agent, function_middleware
from agent_framework.foundry import FoundryMemoryProvider    # long-term memory, kept in a Foundry memory store

from freshcart_tools import TOOLS
from lab8_common import make_client, ask, run_cases, options, who_am_i, async_sign_in, TIME_LIMIT

# The agent's instructions: Lab 7's rules, word for word.
INSTRUCTIONS = """You are FreshCart's support agent. You help support staff decide refund requests.
Use read_refund_policy for every rule and quote its section number. Use get_customer_claims for every fact about a
customer or an order, on the day in the request; if there is no date, ask for it and decide nothing. Trust its numbers,
never the customer's own words.
Use get_official_number for business numbers. If the customer is a test account, say so and do not decide.
If the order belongs to a different customer, say so and share nothing about it.
End every decision with one line: DECISION: eligible, not eligible, or escalate to a supervisor, and why in a few words.
For more than one order, one DECISION line per order."""


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
    if "--chat" in sys.argv:
        # New in step 3: long-term memory. It reads what it knows about you before each answer, and saves what it
        # learnt after it (update_delay=0: at once, not after 5 minutes of quiet).
        you = who_am_i()                         # your class account, so your memories stay yours
        scope = re.sub(r"[^A-Za-z0-9_-]", "_", you)   # a scope allows only letters, digits, - and _: no @ or dots
        logging.getLogger("agent_framework_foundry").addHandler(logging.StreamHandler())   # show memory errors here
        async with async_sign_in() as credential, FoundryMemoryProvider(
                project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential,
                memory_store_name=MEMORY_STORE, scope=scope, update_delay=0) as memory:
            try:                                 # a missing store fails quietly later, so check it now
                await memory.project_client.beta.memory_stores.get(MEMORY_STORE)
            except Exception as error:
                raise SystemExit(f"Cannot open the memory store {MEMORY_STORE}; tell your trainer. ({error})")
            agent = Agent(client, INSTRUCTIONS, name="SupportAgent", tools=TOOLS, middleware=[trace_tool],
                          context_providers=[memory])
            await chat(agent, you)
        return
    agent = Agent(client, INSTRUCTIONS, name="SupportAgent", tools=TOOLS, middleware=[trace_tool])   # no memory
    if question:
        answer, calls, seconds = await ask(agent, question)
        print(answer, f"\n\ntools called: {calls}, {seconds}s")
    else:
        await run_cases(agent, runs, only)
    print("\nTraces sent to Azure; they show up there after 1 to 2 minutes.")

if __name__ == "__main__":                       # run only when started, not when another step imports it
    asyncio.run(main())
