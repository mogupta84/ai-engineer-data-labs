"""Lab 8, step 7: from a sequence to a router, Day 7's router pattern in code. Step 6 sent every request down
every step, so a manager's question got a customer email. Here a triage agent reads each request first and the
workflow sends it down one branch only:
REFUND to the refund desk (the skill agent, which can ask Replywriter, another agent, to draft the email),
NUMBER to the numbers desk (one tool only), PERSON to a support person (no model at all).

    python step7_router.py                 run the cases through the pipeline and score route and answer
    python step7_router.py --ask "..."     send your own request through the pipeline
    python step7_router.py --fixed         the same, with the four fixes from the handbook switched on
"""
import asyncio                                       # run the workflow
import json                                          # save every answer
import sys                                           # read --fixed
import pathlib                                       # find the skills folder
import re                                            # look for a date in the request
from dataclasses import dataclass                    # a small message that carries the route and the request
from typing_extensions import Never                 # a desk sends no message onward

from agent_framework import (Agent, Executor, handler, WorkflowContext, WorkflowBuilder, Case, Default,
                             SkillsProvider, FileSkillsSource)

from freshcart_tools import get_customer_claims, get_official_number, read_refund_policy
from cases import CASES, is_right
from lab8_common import make_client, tool_calls, options, run_agent, TIME_LIMIT

SKILLS = pathlib.Path(__file__).parent / "skills"


@dataclass
class Routed:
    route: str           # REFUND, NUMBER or PERSON
    request: str         # the request, unchanged


class Triage(Executor):
    """Step 1: an agent with no tools decides the route. The workflow, not the agent, then decides what runs."""
    def __init__(self, agent):
        super().__init__(id="triage")
        self.agent = agent

    @handler
    async def route(self, request: str, ctx: WorkflowContext[Routed]) -> None:
        try:
            word = (await run_agent(self.agent, request)).text.strip().upper()
        except asyncio.TimeoutError:
            word = "PERSON"                                  # no answer in time: a person looks at it
        first = word.split()[0].strip(".,:") if word else ""        # the one word the triage agent was asked for
        route = first if first in ("REFUND", "NUMBER", "PERSON") else "PERSON"   # anything else means a person
        await ctx.send_message(Routed(route, request))


class Desk(Executor):
    """Step 2: one branch. With an agent it answers; without one it hands the request to a person."""
    def __init__(self, id, agent=None, needs_date=False):
        super().__init__(id=id)
        self.agent = agent
        self.needs_date = needs_date                     # the date fix: a check in code, before any model runs

    @handler
    async def answer(self, item: Routed, ctx: WorkflowContext[Never, dict]) -> None:   # sends nothing on; yields the answer
        if self.agent is None:
            await ctx.yield_output({"route": item.route, "answer": "Sent to a support person: " + item.request, "tools": []})
            return
        if self.needs_date and not DATE.search(item.request):
            await ctx.yield_output({"route": item.route, "answer": ASK_DATE, "tools": []})
            return
        try:
            response = await run_agent(self.agent, item.request)
        except asyncio.TimeoutError:
            await ctx.yield_output({"route": item.route, "answer": f"(no answer: gave up after {TIME_LIMIT} seconds)", "tools": []})
            return
        await ctx.yield_output({"route": item.route, "answer": response.text, "tools": tool_calls(response)})


# The four fixes. Step 7 asks you to find the problems first, then switch these on with --fixed. Three are one
# sentence in an agent's instructions; the date fix is a check in code, because a sentence did not hold (see below).
FIX_TRIAGE = (" A request about a delivery that went wrong (missing, spilled, damaged, late or wrong items) is REFUND "
              "even if it does not say the word refund.")
FIX_EMAIL = (" Load the refund-decision skill first, for every request, and follow it. Call write_customer_email "
             "ONLY when the request asks for an email; otherwise never call it.")
FIX_NUMBERS = " Never add a currency sign: the data has none."
# FIX_DATE: a request with no day in it never reaches the refund desk's model. We tried a sentence first. At the end
# of the instructions the desk still made up a date (right in 1 of 5 tries); at the start it also asked for dates
# that cases 8 and 10 already give (right in 1 of 5 each). Code that must always hold goes in code.
MONTH = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = re.compile(rf"\b\d{{1,2}}(st|nd|rd|th)? {MONTH},? 20\d\d\b|\b{MONTH} \d{{1,2}}(st|nd|rd|th)?,? 20\d\d\b|"
                  r"\b20\d\d-\d\d-\d\d\b", re.IGNORECASE)   # "14 June 2024", "June 14, 2024", "2nd April 2024", "2024-06-14"
ASK_DATE = "This request gives no date. Please tell me the day the customer is asking, so I can check their claims."


def build_flow(fixed=False):
    client = make_client()
    triage = Agent(client, "Read the request and answer with ONE word only. REFUND: a customer's refund request or a "
                           "question about a refund. NUMBER: a question about a FreshCart business number such as "
                           "revenue, orders or refund rate. PERSON: anything else, including changing an address, "
                           "complaints about staff, or anything that needs a payment to be made."
                           + (FIX_TRIAGE if fixed else ""), name="Triage")
    replywriter = Agent(client, "You receive a support decision. Rewrite it as an email to the customer: start with "
                                "'Dear customer,', at most 4 sentences, keep the policy section numbers, end with "
                                "'FreshCart Support'. Never add a fact or a rule of your own, and never say what has "
                                "already been done.", name="Replywriter")
    skills = SkillsProvider(FileSkillsSource(SKILLS, script_extensions=()), disable_load_skill_approval=True,
                            disable_read_skill_resource_approval=True, disable_run_skill_script_approval=True)
    refund_desk = Agent(client, "You are FreshCart's refund desk. Use your skills and tools to decide the request. "
                                "If the request asks for an email to the customer, call write_customer_email with your "
                                "decision and show the email after the DECISION line." + (FIX_EMAIL if fixed else ""),
                        name="RefundDesk",
                        tools=[get_customer_claims, read_refund_policy,
                               replywriter.as_tool(name="write_customer_email",
                                                   description="Ask Replywriter, another agent, to turn a decision into a customer email",
                                                   arg_name="decision")],
                        context_providers=[skills])
    numbers_desk = Agent(client, "You give FreshCart's official business numbers with get_official_number. Give the "
                                 "number, its month and that test accounts are excluded." + (FIX_NUMBERS if fixed else ""),
                         name="NumbersDesk",
                         tools=[get_official_number])
    t = Triage(triage)
    r, n, p = Desk("refund_desk", refund_desk, needs_date=fixed), Desk("numbers_desk", numbers_desk), Desk("person_desk")
    return (WorkflowBuilder(start_executor=t)
            .add_switch_case_edge_group(t, [Case(condition=lambda m: m.route == "REFUND", target=r),
                                            Case(condition=lambda m: m.route == "NUMBER", target=n),
                                            Default(target=p)])
            .build())


EXTRA = [   # three more requests for the pipeline: an email, a request no tool can do, and a second number
    ("11", "Customer 30 asks on 2 March 2024 about order 1874: two items were missing. Decide, and write the email to the customer.", "REFUND"),
    ("12", "Customer 81 wants us to change the delivery address on their account.", "PERSON"),
    ("13", "What was FreshCart's revenue in May 2024?", "NUMBER"),
]
ROUTES = {case_id: ("NUMBER" if case_id == "9" else "REFUND") for case_id, _, _ in CASES}


async def main():
    runs, only, question = options()
    flow = build_flow(fixed="--fixed" in sys.argv)
    if question:
        print((await flow.run(question)).get_outputs()[0])
        return
    routes_right = answers_right = answers_total = 0
    log = []                                                    # every answer, saved for reading and re-scoring
    for case_id, request, *_ in CASES + EXTRA:
        if only and case_id not in only:
            continue
        for run in range(runs):
            out = (await flow.run(request)).get_outputs()[0]
            expected_route = ROUTES.get(case_id) or dict((e[0], e[2]) for e in EXTRA)[case_id]
            log.append({"case": case_id, "try": run + 1, **out})
            routes_right += out["route"] == expected_route
            line = f"case {case_id} try {run + 1}: route {out['route']} (expected {expected_route}) | tools {out['tools']}"
            if case_id in ROUTES:
                ok = is_right(case_id, out["answer"]); answers_right += ok; answers_total += 1
                line += f" | answer {'RIGHT' if ok else 'WRONG'}"
            emailed = "write_customer_email" in out["tools"]
            print(line + (" | emailed" if emailed else ""))
            if case_id in ("11", "12", "13"):
                print("    " + out["answer"].replace("\n", " ")[:300])
    total = sum(1 for c in CASES + EXTRA if not only or c[0] in only) * runs
    print(f"\nRoutes right: {routes_right} of {total}. Answers right on the 9 Lab 7 cases: {answers_right} of {answers_total}")
    with open("answers_flow_fixed.json" if "--fixed" in sys.argv else "answers_flow.json", "w") as file:
        json.dump(log, file, indent=1)

if __name__ == "__main__":
    asyncio.run(main())
