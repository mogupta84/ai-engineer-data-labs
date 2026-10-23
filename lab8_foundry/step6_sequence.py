"""Lab 8, step 6: from one agent to a sequence. Your step 5 agent decides, then Replywriter, a second agent,
turns the decision into an email to the customer. Day 7's sequence pattern: every request runs every step,
in the same order. Agent Framework calls a pipeline a workflow, and each step in it an executor.

    python step6_sequence.py --case 1,9,10   three cases through the sequence; read every email
    python step6_sequence.py --ask "..."     your own request
"""
import asyncio
from typing_extensions import Never                 # the last step sends no message onward

from agent_framework import Agent, Executor, handler, WorkflowContext, WorkflowBuilder, SkillsProvider, FileSkillsSource

from freshcart_tools import TOOLS
from cases import CASES
from lab8_common import make_client, options, run_agent
from step5_skill import INSTRUCTIONS, SKILLS, compare_months, trace_tool   # your step 5 agent's parts, unchanged

REPLYWRITER = """You receive a support decision. Rewrite it as an email to the customer: start with 'Dear customer,',
at most 4 sentences, keep the policy section numbers, end with 'FreshCart Support'. Never add a fact or a rule of
your own, and never say what has already been done."""


class Decide(Executor):
    """Step 1 of the sequence: your support agent decides, and passes on its decision, as text, to the next step."""
    def __init__(self, agent):
        super().__init__(id="decide")
        self.agent = agent

    @handler
    async def decide(self, request: str, ctx: WorkflowContext[str, dict]) -> None:
        decision = (await run_agent(self.agent, request)).text
        await ctx.yield_output({"step": "SupportAgent", "text": decision})   # show it
        await ctx.send_message(decision)                                       # and pass it on


class Write(Executor):
    """Step 2: Replywriter turns the decision into an email. It sees the decision only, never the tools' data."""
    def __init__(self, agent):
        super().__init__(id="write")
        self.agent = agent

    @handler
    async def write(self, decision: str, ctx: WorkflowContext[Never, dict]) -> None:
        email = (await run_agent(self.agent, decision)).text
        await ctx.yield_output({"step": "Replywriter", "text": email})


async def build_sequence():
    client = make_client()
    await client.configure_azure_monitor(enable_sensitive_data=True)   # tracing, as in step 2
    skills = SkillsProvider(FileSkillsSource(SKILLS, script_extensions=()), disable_load_skill_approval=True,
                            disable_read_skill_resource_approval=True, disable_run_skill_script_approval=True)
    support = Agent(client, INSTRUCTIONS, name="SupportAgent", tools=TOOLS + [compare_months],
                    middleware=[trace_tool], context_providers=[skills])
    replywriter = Agent(client, REPLYWRITER, name="Replywriter")             # no tools: it only writes
    decide, write = Decide(support), Write(replywriter)
    # New in step 6: the pipeline. Start at decide; whatever decide sends goes to write.
    return WorkflowBuilder(start_executor=decide).add_edge(decide, write).build()


async def main():
    runs, only, question = options()
    sequence = await build_sequence()
    requests = [question] if question else [q for case_id, q, _ in CASES if not only or case_id in only]
    for request in requests:
        result = await sequence.run(request)
        print(f"\nREQUEST: {request}")
        for out in result.get_outputs():                         # one output per step, in order: decision, email
            print(f"\n{out['step']}:\n{out['text']}")
        print("\n" + "-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
