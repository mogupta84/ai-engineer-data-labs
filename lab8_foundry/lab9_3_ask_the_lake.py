"""Lab 9, Part E: an agent that answers questions about the tickets by reading the lakehouse you built.

It runs in your Lab 8 folder, with Lab 8's environment and sign-in. Put LAKE_SQL_ENDPOINT in your .env file. The tool below lets the model run only a single SELECT on six tables; your account
could do more, so the check in query_lake is what keeps the agent read-only.

    python lab9_3_ask_the_lake.py                 ask the 5 test questions, 3 times each, and score them
    python lab9_3_ask_the_lake.py --ask "..."     ask your own question
    python lab9_3_ask_the_lake.py --fixed         the same 5 questions, with one sentence added to the tool
"""
import asyncio, json, os, re, sys, time

import mssql_python                                        # Microsoft's SQL Server driver for Python
from agent_framework import Agent

from lab8_common import make_client                        # Lab 8's model client, signed in as you; reads .env
from freshcart_tools import DB_SIGN_IN                     # Lab 8's database sign-in, the token kept between calls

ENDPOINT = os.environ.get("LAKE_SQL_ENDPOINT", "")         # your lakehouse's SQL analytics endpoint address
LAKE = f"Server=tcp:{ENDPOINT},1433;Database=freshcart_lake;Encrypt=yes"   # no password: DB_SIGN_IN hands the token
TABLES = ("tickets_clean", "tickets_quarantine", "tickets_enriched", "run_log", "enrich_log", "ticket_labels")
# Words that change something or reach outside the six tables. T-SQL needs no ';' between statements.
WRITES = {"insert", "update", "delete", "merge", "drop", "create", "alter", "truncate", "exec", "execute", "grant",
          "revoke", "deny", "into", "declare", "set", "enable", "disable", "backup", "restore", "kill", "dbcc",
          "bulk", "openrowset", "opendatasource", "openquery", "shutdown", "reconfigure", "waitfor", "use"}


def read_sql(sql):
    """Read the query once, left to right, the way SQL Server does: comments become spaces, quoted text and
    quoted names become placeholders. Returns the bare query, or None if a quote or comment is never closed."""
    out, i, n = [], 0, len(sql)
    while i < n:
        two = sql[i:i + 2]
        if two == "--":                                    # comment to the end of the line
            end = sql.find("\n", i)
            i = n if end < 0 else end
            out.append(" ")
        elif two == "/*":                                  # block comment
            end = sql.find("*/", i + 2)
            if end < 0:
                return None
            i = end + 2
            out.append(" ")
        elif sql[i] in "'\"[":                              # 'text', "name" or [name]
            close = {"'": "'", '"': '"', "[": "]"}[sql[i]]
            j = i + 1
            while True:
                j = sql.find(close, j)
                if j < 0:
                    return None
                if sql[j + 1:j + 2] == close and close != "]":  # '' inside text is one quote
                    j += 2
                    continue
                break
            out.append(" '' " if sql[i] == "'" else " quoted_name ")
            i = j + 1
        else:
            out.append(sql[i])
            i += 1
    return "".join(out).lower()


def allowed(sql):
    """None if the query is one read-only SELECT over the six tables; otherwise the reason it is refused."""
    bare = read_sql(sql.strip().rstrip(";"))
    if bare is None:
        return "a quote or a comment is never closed"
    words = set(re.findall(r"[a-z_@#][\w@#$]*", bare))
    if not re.match(r"\s*(select|with)\b", bare) or ";" in bare or words & WRITES:
        return "only one read-only SELECT statement is allowed"
    ctes = set(re.findall(r"(?:\bwith|,)\s*([a-z_]\w*)\s+as\s*\(", bare))       # names made inside the query
    sources = re.findall(r"\b(?:from|join|apply)\s+([a-z_][\w.]*|quoted_name)", bare)
    sources = [name[4:] if name.startswith("dbo.") else name for name in sources]   # dbo. is the default schema
    if not sources or any(name not in TABLES and name not in ctes for name in sources):
        return "query only these tables: " + ", ".join(TABLES)
    return None


MAX_ROWS = 50                                              # the model never sees more than 50 rows
TIME_LIMIT = 120


def query_lake(sql: str) -> dict:
    """Run ONE read-only SELECT on the FreshCart lakehouse (T-SQL) and return at most 50 rows.
    Tables: tickets_clean (ticket_id, created_at, customer_id, order_id, channel, category, priority,
    first_response_minutes, resolution_minutes, refund_amount, text), tickets_quarantine (the same columns plus
    failed_rules, the rules a ticket broke), tickets_enriched (tickets_clean plus ai_category, ai_model,
    ai_prompt_version, categories_agree), enrich_log (one row per labelling run), ticket_labels, and run_log
    (one row per run of the optional Part B notebook; it may not exist)."""
    text = sql.strip().rstrip(";")
    refused = allowed(text)
    if refused:
        return {"ok": False, "message": refused}
    connection = mssql_python.connect(LAKE, timeout=60, token_provider=DB_SIGN_IN)
    try:
        cursor = connection.cursor()
        cursor.execute(text)
        columns = [c[0] for c in cursor.description]
        rows = [[str(v) if v is not None else None for v in row] for row in cursor.fetchmany(MAX_ROWS)]
    except mssql_python.Error as error:
        return {"ok": False, "message": f"SQL error: {str(error)[:300]}"}
    finally:
        connection.close()
    return {"ok": True, "columns": columns, "rows": rows}


INSTRUCTIONS = ("You answer questions about FreshCart support tickets using query_lake. Always query; never guess a "
                "number. Give the number first, then one sentence on how you got it. Tickets that failed a quality "
                "rule are in tickets_quarantine, not in tickets_clean. 'category' is what support recorded; "
                "'ai_category' is the AI label.")

# The fix for Part E, one sentence: say what the log columns mean. Switched on with --fixed.
FIX_LOGS = (" enrich_log has one row per labelling run: run_at, model_calls (calls made to the model in that run), "
            "cache_hits, tokens_in, tokens_out, cost_usd (US dollars for that run), rows, seconds. The first run is "
            "the earliest run_at.")

# Five questions and the numbers the answer must contain (checked against the lakehouse on 18 October 2026, after
# Lab 9's new day and before the Lab 10 days: a lake with the Lab 10 days in it gives other numbers).
QUESTIONS = [
    ("1", "How many tickets were put in quarantine, and for which reasons?", ["22", "9", "4", "6", "3"]),
    ("2", "Which ticket text is the most common, and how many clean tickets have it?", ["20225"]),
    ("3", "Of the clean tickets whose text is 'item missing from the bag', how many did support record as missing_item?", ["2492"]),
    ("4", "How many clean tickets were created in December 2024?", ["17152"]),
    ("5", "In the first AI labelling run, how many model calls were made and what did it cost?", ["10", "0.000248"]),
]


def is_right(answer, needed):
    numbers = set(re.findall(r"\d+(?:\.\d+)?", answer.replace(",", "")))
    return all(n in numbers for n in needed)


async def main():
    if not ENDPOINT:
        sys.exit("Add LAKE_SQL_ENDPOINT=<your lakehouse's SQL analytics endpoint> to the .env file in this folder.")
    client = make_client()
    if "--fixed" in sys.argv:
        query_lake.__doc__ += FIX_LOGS                     # the model reads the docstring as the tool's description
    agent = Agent(client, INSTRUCTIONS, tools=[query_lake], name="AskTheLake")
    if "--ask" in sys.argv:
        print((await asyncio.wait_for(agent.run(sys.argv[sys.argv.index("--ask") + 1]), TIME_LIMIT)).text)
        return
    right, log = 0, []
    for qid, question, needed in QUESTIONS:
        for run in range(3):
            start = time.time()
            try:
                response = await asyncio.wait_for(agent.run(question), TIME_LIMIT)
                answer = response.text
                sql = [c.arguments for m in response.messages for c in m.contents if getattr(c, "type", "") == "function_call"]
            except asyncio.TimeoutError:
                answer, sql = "(no answer in time)", []
            ok = is_right(answer, needed)
            right += ok
            log.append({"question": qid, "run": run + 1, "right": ok, "answer": answer, "sql": [str(s) for s in sql],
                        "seconds": round(time.time() - start, 1)})
            print(f"Q{qid} run {run + 1}: {'RIGHT' if ok else 'WRONG'} | {len(sql)} queries | {time.time() - start:.0f} s | "
                  + answer.replace("\n", " ")[:160])
    print(f"\nRight: {right} of {len(QUESTIONS) * 3}")
    with open("answers_lake_fixed.json" if "--fixed" in sys.argv else "answers_lake.json", "w") as file:
        json.dump(log, file, indent=1)

if __name__ == "__main__":
    asyncio.run(main())
