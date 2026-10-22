"""Lab 8, Part B: the same agent with a skill. The refund procedure lives in skills/refund-decision/SKILL.md,
written once; the agent sees only its name and description until a request needs it, then loads the steps.

    python lab8_2_skill.py --runs 3
"""
import asyncio                                                   # run the agent
import pathlib                                                   # find the skills folder

from agent_framework import Agent, SkillsProvider, FileSkillsSource   # skills come from SKILL.md files

from freshcart_tools import TOOLS
from lab8_common import make_client, ask, run_cases, options

SKILLS = pathlib.Path(__file__).parent / "skills"               # each skill is one folder with a SKILL.md

INSTRUCTIONS = """You are FreshCart's support agent. You help support staff with refund requests and business numbers.
Use your skills and tools. Use get_official_number for business numbers."""      # short: the procedure is in the skill


async def main():
    runs, only, question = options()
    source = FileSkillsSource(SKILLS, script_extensions=())          # this skill has steps and a reference file, no scripts
    skills = SkillsProvider(source, disable_load_skill_approval=True, disable_read_skill_resource_approval=True,
                            disable_run_skill_script_approval=True)     # no approvals: there are no scripts to run
    agent = Agent(make_client(), INSTRUCTIONS, name="SkillAgent", tools=TOOLS, context_providers=[skills])
    if question:
        answer, calls, seconds = await ask(agent, question)
        print(answer, f"\n\ntools called: {calls}, {seconds}s")
    else:
        await run_cases(agent, runs, only)

asyncio.run(main())
