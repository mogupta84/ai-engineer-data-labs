import json
import pathlib
import sqlite3
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)   # callers need the function key
DB = pathlib.Path(__file__).parent / "freshcart.db"                # the warehouse, shipped with the code

# Each official number, written once with its business rules.
# Test accounts (is_internal = 1) are always left out; revenue counts delivered orders only.
METRICS = {
    "revenue": "SELECT SUM(o.order_value) FROM orders_v2 o JOIN dim_customer c ON c.customer_id = o.customer_id "
               "WHERE c.is_internal = 0 AND o.status = 'delivered' AND substr(o.order_date, 1, 7) = ?",
    "order_count": "SELECT COUNT(*) FROM orders_v2 o JOIN dim_customer c ON c.customer_id = o.customer_id "
                   "WHERE c.is_internal = 0 AND substr(o.order_date, 1, 7) = ?",
    "refund_claims": "SELECT COUNT(*) FROM fact_refund_claim f JOIN dim_customer c ON c.customer_id = f.customer_id "
                     "WHERE c.is_internal = 0 AND substr(f.claim_date, 1, 7) = ?",
}


def lookup(metric, month):
    """The shared logic: one official number for one month, or a message saying why not."""
    if metric not in METRICS:
        return {"ok": False, "message": "metric must be revenue, order_count or refund_claims"}

    # Open the warehouse file read-only, so this function can never change the data.
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    value = db.execute(METRICS[metric], (month,)).fetchone()[0]
    db.close()

    if not value:
        return {"ok": False, "message": "no data for that month; use YYYY-MM within 2024"}
    return {"ok": True, "metric": metric, "month": month, "value": round(value, 2),
            "scope": "excluding test accounts"}


# Way 1: a web address, for Foundry's OpenAPI tool.
@app.route(route="get_metric", methods=["GET"])
def get_metric(req: func.HttpRequest) -> func.HttpResponse:
    body = lookup(req.params.get("metric"), req.params.get("month"))   # metric, and month as YYYY-MM
    # Always status 200, with any problem in the body: Foundry stops the agent run on an error code.
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")


# Way 2: the same lookup as an MCP tool, for Foundry's MCP tool.
# The app's MCP server address is https://<app address>/runtime/webhooks/mcp
@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger", toolName="get_metric",
    description="Return one official FreshCart number for one month of 2024: revenue (delivered orders "
                "only), order_count or refund_claims. Test accounts are always excluded.",
    toolProperties=json.dumps([
        {"propertyName": "metric", "propertyType": "string", "description": "revenue, order_count or refund_claims"},
        {"propertyName": "month", "propertyType": "string", "description": "YYYY-MM, for example 2024-03"},
    ]))
def get_metric_mcp(context) -> str:
    arguments = json.loads(context).get("arguments", {})   # what the agent sent
    return json.dumps(lookup(arguments.get("metric"), arguments.get("month")))
