import json
import pathlib
import re
import sqlite3
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)   # callers need the function key
DB = pathlib.Path(__file__).parent / "freshcart.db"                # the warehouse, shipped with the code

# The semantic layer: each official number, written once with its business rules.
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
    "refund_rate": {"formula": "ROUND(1.0 * COUNT(DISTINCT f.claim_id) / COUNT(DISTINCT o.order_id), 4)",
                    "tables": ORDERS + " LEFT JOIN fact_refund_claim f ON f.order_id = o.order_id",
                    "rules": "c.is_internal = 0", "date": "o.order_date"},
}
BREAKDOWNS = {"city": "c.city", "region": "c.region"}               # "month" is worked out from the date


def dates_of(period):
    """A period as its first and last day: 2024-03 (a month), 2024-Q2 (a quarter) or 2024 (a year)."""
    period = str(period or "")
    if re.fullmatch(r"2024-(0[1-9]|1[0-2])", period):
        return period + "-01", period + "-31"                        # dates are text, so -31 covers every month
    if re.fullmatch(r"2024-Q[1-4]", period):
        first = 3 * int(period[-1]) - 2
        return f"2024-{first:02d}-01", f"2024-{first + 2:02d}-31"
    if period == "2024":
        return "2024-01-01", "2024-12-31"
    return None


def lookup(metric, month, breakdown=None):
    """The shared logic: one official number, or one per city, region or month, or a message saying why not."""
    if metric not in METRICS:
        return {"ok": False, "message": "no such business number; use revenue, order_count, refund_claims or refund_rate"}
    days = dates_of(month)
    if not days:
        return {"ok": False, "message": "month must be YYYY-MM, YYYY-Qn or YYYY, within 2024"}
    breakdown = breakdown or "none"
    if breakdown not in ("none", "city", "region", "month"):
        return {"ok": False, "message": "breakdown must be none, city, region or month"}

    m = METRICS[metric]
    # The code writes the SQL from the definition, so a rule can never be forgotten.
    group = {"none": None, "month": f"substr({m['date']}, 1, 7)"}.get(breakdown, BREAKDOWNS.get(breakdown))
    select = f"{group}, {m['formula']}" if group else m["formula"]
    sql = f"SELECT {select} FROM {m['tables']} WHERE {m['rules']} AND {m['date']} BETWEEN ? AND ?"
    if group:
        sql += f" GROUP BY {group} ORDER BY {group}"

    # Open the warehouse file read-only, so this function can never change the data.
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = db.execute(sql, days).fetchall()
    db.close()

    answer = {"ok": True, "metric": metric, "period": month, "scope": "excluding test accounts"}
    if group:
        answer.update(breakdown=breakdown, rows=[[label, round(value or 0, 4)] for label, value in rows])
    elif rows[0][0] is None:
        return {"ok": False, "message": "no data for that period"}
    else:
        answer["value"] = round(rows[0][0], 4)
    return answer


def reply(body):
    # Always status 200, with any problem in the body: Foundry stops the agent run on an error code.
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")


# Way 1: web addresses, for Foundry's OpenAPI tool.
@app.route(route="get_metric", methods=["GET"])
def get_metric(req: func.HttpRequest) -> func.HttpResponse:
    return reply(lookup(req.params.get("metric"), req.params.get("month"), req.params.get("breakdown")))


# Way 2: the same lookup as an MCP tool, for Foundry's MCP tool.
# The app's MCP server address is https://<app address>/runtime/webhooks/mcp
@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger", toolName="get_metric",
    description="Return one official FreshCart number for 2024: revenue (delivered orders only), order_count, "
                "refund_claims or refund_rate (claims per order). Test accounts are always excluded. "
                "Optionally split it by city, region or month.",
    toolProperties=json.dumps([
        {"propertyName": "metric", "propertyType": "string",
         "description": "revenue, order_count, refund_claims or refund_rate"},
        {"propertyName": "month", "propertyType": "string",
         "description": "the period: YYYY-MM (a month), YYYY-Qn (a quarter) or YYYY (the year), within 2024"},
        {"propertyName": "breakdown", "propertyType": "string", "description": "none, city, region or month"},
    ]))
def get_metric_mcp(context) -> str:
    arguments = json.loads(context).get("arguments", {})   # what the agent sent
    return json.dumps(lookup(arguments.get("metric"), arguments.get("month"), arguments.get("breakdown")))
