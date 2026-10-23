"""Lab 8, step 1: YOUR agent. Fill in the two gaps below, then run it.

    python my_agent.py --case 9            one case: the March refund rate
    python my_agent.py                     the 9 cases, scored
    python my_agent.py --runs 3            the 9 cases, 3 times each
    python my_agent.py --ask "..."         your own question

Stuck? step1_agent.py is this file, finished.
"""
import asyncio                                   # run the agent

from agent_framework import Agent                # an agent: a model, instructions and tools

from freshcart_tools import TOOLS                # the three tools, plain Python functions over the warehouse
from lab8_common import make_client, ask, run_cases, options

# GAP 1. The instructions: your support agent's rules. Write them in your own words, from Lab 7:
# who the agent is; which tool to use for rules, for customer facts and for business numbers; what to do with no
# date, a test account or another customer's order; and to end with a DECISION line.
INSTRUCTIONS = """
"""


async def main():
    runs, only, question = options()
    if not INSTRUCTIONS.strip():
        raise SystemExit("Fill in GAP 1 first: the agent's instructions.")
    # GAP 2. Make the agent. Replace None on the next line (keep the 4 spaces at the start of it) with:
    #     Agent(make_client(), INSTRUCTIONS, name="SupportAgent", tools=TOOLS)
    agent = None
    if agent is None:
        raise SystemExit("Fill in GAP 2: make the agent.")
    if question:
        answer, calls, seconds = await ask(agent, question)
        print(answer, f"\n\ntools called: {calls}, {seconds}s")
    else:
        await run_cases(agent, runs, only)

if __name__ == "__main__":
    asyncio.run(main())
