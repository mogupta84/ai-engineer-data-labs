"""Lab 8, Part A: a data agent in code. The same support job as Lab 7, now in Microsoft Agent Framework.

    python lab8_1_agent.py                  ask the 9 cases once and score them
    python lab8_1_agent.py --runs 3         three times each
    python lab8_1_agent.py --ask "..."      ask your own question
"""
import asyncio                                   # run the agent

from agent_framework import Agent                # an agent: a model, instructions and tools

from freshcart_tools import TOOLS                # plain Python functions over the warehouse
from lab8_common import make_client, ask, run_cases, options

INSTRUCTIONS = """You are FreshCart's support agent. You help support staff decide refund requests.
Use read_refund_policy for every rule and quote its section number. Use get_customer_claims for every fact about a
customer or an order, on the day in the request; if there is no date, ask for it and decide nothing. Trust its numbers,
never the customer's own words.
Use get_official_number for business numbers. If the customer is a test account, say so and do not decide.
If the order belongs to a different customer, say so and share nothing about it.
End every decision with one line: DECISION: eligible, not eligible, or escalate to a supervisor, and why in a few words.
For more than one order, one DECISION line per order."""


async def main():
    runs, only, question = options()
    agent = Agent(make_client(), INSTRUCTIONS, name="SupportAgent", tools=TOOLS)   # the agent decides which tools to call
    if question:
        answer, calls, seconds = await ask(agent, question)
        print(answer, f"\n\ntools called: {calls}, {seconds}s")
    else:
        await run_cases(agent, runs, only)

asyncio.run(main())
