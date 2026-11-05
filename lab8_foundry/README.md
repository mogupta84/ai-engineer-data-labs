# Lab 8: an AI data agent in code, with Microsoft Agent Framework

Start with the handbook, **[Foundry_Lab8_agent_in_code.pdf](Foundry_Lab8_agent_in_code.pdf)**.
Run it in VS Code on your class VM, signed in with VS Code's Sign in to Azure or with az login; VS Code for the Web, opened from Microsoft Foundry, is the backup. No keys.

```
my_agent.py               step 1: YOUR agent; fill in the two gaps
step1_agent.py            step 1, finished: the support agent in code, scored on 9 of the Lab 7 cases
step2_trace.py            step 2: tracing, in the terminal and in Application Insights
step3_memory.py           step 3: memory, a session and a Foundry memory store (--chat)
step4_tool.py             step 4: a tool you write, compare_months
step5_skill.py            step 5: the refund-decision skill
step6_sequence.py         step 6: a sequence, the agent then Replywriter
step7_router.py           step 7: a router, triage then three desks, and an agent as a tool (--fixed)
lab9_3_ask_the_lake.py    Lab 9 Part E: an agent that answers from your Fabric lakehouse
lab11_1_pii.py            Lab 11 G1: personal data out first, checked against a hand-made list
lab11_2_who_sees_what.py  Lab 11 G2 and G3: access by team in the search, and an audit log
freshcart_tools.py        the tools: one customer's claims, official numbers, the refund policy
skills/refund-decision/   the skill: SKILL.md and the refund policy
cases.py, lab8_common.py  the cases, the scorer and the shared runner
copilot_studio_instructions.txt  Part D: the instructions for the Copilot Studio demo
```

Put the settings your trainer gives you in a file named .env in this folder, one NAME=value per line:
FOUNDRY_PROJECT_ENDPOINT (Lab 8), LAKE_SQL_ENDPOINT (Lab 9 Part E), SEARCH_ENDPOINT and SEARCH_QUERY_KEY (Lab 11,
the same as in Labs 1 to 4 in Azure) and LANGUAGE_ENDPOINT (Lab 11). SEARCH_QUERY_KEY can only read the index.
The .env file never goes to GitHub.
