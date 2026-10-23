"""Lab 8, step 2: the same agent, now traced. Two traces, two places:
in the terminal, one line per tool call (a middleware: code that runs around every tool call), and in Azure,
every run, model call and tool call, sent to the Application Insights linked to the class Foundry project.

    python step2_trace.py --case 4         one case, traced
    python step2_trace.py --ask "..."      your own question, traced
"""
import asyncio
import time                                      # time each tool call

from agent_framework import Agent, function_middleware

from freshcart_tools import TOOLS
from lab8_common import make_client, ask, run_cases, options

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


async def main():
    runs, only, question = options()
    client = make_client()
    # New in step 2: one line sends traces to the Application Insights linked to the Foundry project.
    # enable_sensitive_data=True also records the prompts and answers; fine for a class, not for real customers.
    await client.configure_azure_monitor(enable_sensitive_data=True)
    agent = Agent(client, INSTRUCTIONS, name="SupportAgent", tools=TOOLS, middleware=[trace_tool])
    if question:
        answer, calls, seconds = await ask(agent, question)
        print(answer, f"\n\ntools called: {calls}, {seconds}s")
    else:
        await run_cases(agent, runs, only)
    print("\nTraces sent to Azure; they show up there after 1 to 2 minutes.")

if __name__ == "__main__":                       # run only when started, not when another step imports it
    asyncio.run(main())
