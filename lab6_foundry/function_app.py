"""Lab 6: questions in English, numbers you can defend.

Two tools over the FreshCart mini warehouse, an Azure SQL database, in the order the lab uses them:
- run_sql (Steps C to F): the model writes its own SQL and this runs it, read-only.
- official_number (Step G): the semantic layer. The model picks a number; this code writes the SQL.
"""
import calendar
import datetime
import decimal
import json
import os
import re
import time
import azure.functions as func
import mssql_python

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)   # callers need the function key

# The warehouse. The server and database names come from the app's settings. The app signs in with its own
# Azure identity (ActiveDirectoryMSI), so there is no password, and that identity may only read.
WAREHOUSE = (f"Server=tcp:{os.environ.get('SQL_SERVER')},1433;Database={os.environ.get('SQL_DATABASE')};"
             "Authentication=ActiveDirectoryMSI;Encrypt=yes;TrustServerCertificate=no")


# On Azure's free offer the database pauses after about an hour unused. The first connection wakes it but
# usually times out first, so one failed connection that looks like that is tried again after a short wait.
WAKING = ("timeout", "unable to establish connection", "not currently available", "40613")


def connect():
    """Open a connection to the warehouse, waiting once for it to wake up if it was paused."""
    try:
        return mssql_python.connect(WAREHOUSE)
    except mssql_python.Error as error:
        if not any(sign in str(error).lower() for sign in WAKING):
            raise
        time.sleep(20)                                   # give the paused database time to start
        return mssql_python.connect(WAREHOUSE)


def rows_of(sql, params=(), limit=50):
    """Run one query and return at most `limit` rows, as plain numbers and text."""
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchmany(limit)
    finally:
        connection.close()
    return [[plain(v) for v in row] for row in rows]


def plain(value):
    """Database values as JSON can carry them: decimals as numbers, dates as text."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


# ---------------- Steps C to F: free SQL, written by the model ----------------

# Words that change data. A query that contains one is refused before it reaches the database.
CHANGES_DATA = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|merge|exec|execute|grant|into)\b",
                          re.IGNORECASE)


def run_sql(sql):
    """One read-only SELECT, written by the model, at most 50 rows back."""
    statement = (sql or "").strip().rstrip(";")
    if not statement:
        return {"ok": False, "message": "No SQL received. Send POST with a JSON body like {\"sql\": \"SELECT ...\"}"}
    if ";" in statement or not statement.lower().startswith(("select", "with")) or CHANGES_DATA.search(statement):
        return {"ok": False, "message": "REFUSED: only one read-only SELECT is allowed"}
    try:
        return {"ok": True, "rows": rows_of(statement)}   # the database user can only read: a second lock
    except mssql_python.Error as error:
        return {"ok": False, "message": f"SQL error: {str(error)[:300]}"}


# ---------------- Step G: the semantic layer ----------------

# Each official number, written once: its formula, its tables, its business rules and its date column.
# Test accounts (is_internal = 1) are always left out; revenue counts delivered orders only.
ORDERS = "orders_v2 o JOIN dim_customer c ON c.customer_id = o.customer_id"
METRICS = {
    "revenue": {"formula": "SUM(o.order_value)", "tables": ORDERS,
                "rules": "c.is_internal = 0 AND o.status = 'delivered'", "date": "o.order_date"},
    "order_count": {"formula": "COUNT(DISTINCT o.order_id)", "tables": ORDERS,
                    "rules": "c.is_internal = 0", "date": "o.order_date"},
    "refund_claims": {"formula": "COUNT(DISTINCT f.claim_id)",
                      "tables": "fact_refund_claim f JOIN dim_customer c ON c.customer_id = f.customer_id",
                      "rules": "c.is_internal = 0", "date": "f.claim_date"},
    # Refund rate means claims per order: decided once, here, so every team gets the same number.
    "refund_rate": {"formula": "ROUND(1.0 * COUNT(DISTINCT f.claim_id) / NULLIF(COUNT(DISTINCT o.order_id), 0), 4)",
                    "tables": ORDERS + " LEFT JOIN fact_refund_claim f ON f.order_id = o.order_id",
                    "rules": "c.is_internal = 0", "date": "o.order_date"},
}


def period_days(period):
    """2024-03 (a month), 2024-Q1 (a quarter) or 2024 (a year) as its first and last day."""
    period = str(period or "")
    if re.fullmatch(r"2024-(0[1-9]|1[0-2])", period):
        first = last = int(period[5:])
    elif re.fullmatch(r"2024-Q[1-4]", period):
        first = 3 * int(period[-1]) - 2
        last = first + 2
    elif period == "2024":
        first, last = 1, 12
    else:
        return None
    return f"2024-{first:02d}-01", f"2024-{last:02d}-{calendar.monthrange(2024, last)[1]}"


def official_number(metric, period, breakdown=None):
    """One official number, or one per city, region or month, or a message saying why not."""
    if metric not in METRICS:
        return {"ok": False, "message": "no such business number; use revenue, order_count, refund_claims or refund_rate"}
    days = period_days(period)
    if not days:
        return {"ok": False, "message": "period must be YYYY-MM, YYYY-Qn or YYYY, within 2024"}
    breakdown = breakdown or "none"
    m = METRICS[metric]
    group = {"none": None, "city": "c.city", "region": "c.region",
             "month": f"CONVERT(char(7), {m['date']}, 126)"}.get(breakdown, "bad")
    if group == "bad":
        return {"ok": False, "message": "breakdown must be none, city, region or month"}

    # The code writes the SQL from the definition, so a rule can never be forgotten.
    select = f"{group}, {m['formula']}" if group else m["formula"]
    sql = f"SELECT {select} FROM {m['tables']} WHERE {m['rules']} AND {m['date']} BETWEEN ? AND ?"
    if group:
        sql += f" GROUP BY {group} ORDER BY {group}"
    rows = rows_of(sql, days, limit=100)

    answer = {"ok": True, "metric": metric, "period": period, "scope": "excluding test accounts"}
    if group:
        answer.update(breakdown=breakdown, rows=[[label, round(value or 0, 4)] for label, value in rows])
    else:
        answer["value"] = round(rows[0][0] or 0, 4)
    return answer


# ---------------- The two web addresses, for Foundry's OpenAPI tool ----------------

def reply(body):
    # Always status 200, with any problem in the body: Foundry stops the agent run on an error code.
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")


@app.route(route="run_sql", methods=["POST"])
def run_sql_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        sql = req.get_json().get("sql")
    except ValueError:
        sql = None
    return reply(run_sql(sql))


@app.route(route="official_number", methods=["GET"])
def official_number_http(req: func.HttpRequest) -> func.HttpResponse:
    return reply(official_number(req.params.get("metric"), req.params.get("period"), req.params.get("breakdown")))
