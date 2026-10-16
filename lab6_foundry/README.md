# Lab 6 on Microsoft Foundry: questions in English, numbers you can defend

Start with the handbook, **[Foundry_Lab6_numbers_you_can_defend.pdf](Foundry_Lab6_numbers_you_can_defend.pdf)**.
Lab 6 is independent of Lab 5: it has its own Function App, deployed from this folder.

```
function_app.py      the two tools: run_sql (the model writes SQL) and official_number (the semantic layer)
requirements.txt     the packages Azure installs: azure-functions and mssql-python
mini_warehouse.sql   the small Azure SQL warehouse: six tables, 56 rows, the same traps as the full one
openapi_sql.json     the run_sql tool description to paste into Foundry; replace YOUR-APP-ADDRESS first
openapi_layer.json   the same for official_number, the semantic layer
lab6_instructions_*.txt  the four sets of agent instructions: schema only, rules, examples, semantic layer
```

Never put a function key in a file, a slide or a chat.
