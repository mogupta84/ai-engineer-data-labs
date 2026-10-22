# Lab 7 on Microsoft Foundry: a first enterprise agent

Start with the handbook, **[Foundry_Lab7_first_enterprise_agent.pdf](Foundry_Lab7_first_enterprise_agent.pdf)**.
Lab 7 has its own database (freshcart_lab7) and its own Function App, deployed from this folder.

```
function_app.py           the tools: customer_claims, official_number, restaurant_orders, and three practice
                          actions for the recall (refund, escalate, email) that only return a receipt
openapi_lab7.json         the tools' description to paste into Foundry; replace YOUR-APP-ADDRESS first
openapi_lab7_recall.json  the same plus the recall tools, for RecallAgent only (Parts B and C)
refund_policy_v3_2024.pdf the refund policy, for File search
lab7_instructions_*.txt   the agent instructions: policy agent, Replywriter, SupportAgent, planner, memory line,
                          and the recall's two additions (recall tools, plan first)
refund-decision/SKILL.md  the refund procedure as a skill
lab7_answer_key.md        the 10 cases, their right answers, and what the trainer's runs gave
load_warehouse.py         loads ../data/freshcart.db into your own Azure SQL database (appendix use only)
```

Never put a function key in a file, a slide or a chat.
