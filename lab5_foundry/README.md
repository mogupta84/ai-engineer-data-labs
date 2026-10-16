# Lab 5 on Microsoft Foundry: your own function as an OpenAPI tool and an MCP server

Start with the handbook, **[Foundry_grounding_and_MCP_demo.pdf](Foundry_grounding_and_MCP_demo.pdf)**.
Parts 3 and 4 use the files in this folder.

```
function_app.py   get_metric as a web address and an MCP tool
freshcart.db      the FreshCart warehouse for Parts 3 and 4, one SQLite file; the function opens it read-only
requirements.txt  the one package Azure installs
host.json         loads the preview add-on that the MCP tool needs
openapi.json      the get_metric tool description to paste into Foundry; replace YOUR-APP-ADDRESS first
Lab 6 is separate, with its own Function App, in ../lab6_foundry.
.vscode/          settings for the VS Code Azure Functions extension, used to deploy
```

Never put a function key in a file, a slide or a chat. Delete your Function App when you are done.
