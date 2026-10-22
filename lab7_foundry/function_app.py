"""Lab 7: a first enterprise agent in Foundry.

Two tools over the FreshCart warehouse, an Azure SQL database of its own (freshcart_lab7), for SupportAgent:
- customer_claims: one customer's refund claims up to a given day, and the claims in the 30 days before it.
- official_number: the semantic layer from Lab 6, the same definitions, over this warehouse.
For Part C, a recall: one restaurant's orders over a period, and three actions (refund, escalate, email) that only
return a practice receipt. Nothing is paid, saved or sent, and the database stays read-only.
"""
import calendar
import datetime
import decimal
import json
import math
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


def rows_of(sql, params=(), limit=100, cursor=None):
    """Run one query and return at most `limit` rows, as plain numbers and text.
    Pass an open cursor to reuse one connection for several queries."""
    if cursor is not None:
        cursor.execute(sql, params)
        return [[plain(v) for v in row] for row in cursor.fetchmany(limit)]
    connection = connect()
    try:
        return rows_of(sql, params, limit, connection.cursor())
    finally:
        connection.close()


def plain(value):
    """Database values as JSON can carry them: decimals as numbers, dates as text."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


# ---------------- customer_claims: the facts about one customer ----------------

WINDOW_DAYS = 30           # the refund policy's rolling period for counting claims


def whole_number(text):
    """A positive whole number from text, or None."""
    return int(text) if re.fullmatch(r"[1-9][0-9]{0,8}", str(text or "").strip()) else None


def customer_claims(customer_id, as_of, order_id=None):
    """One customer, their claims up to `as_of`, the count in the 30 days ending on `as_of`, and one order if asked."""
    customer = whole_number(customer_id)
    if customer is None:
        return {"ok": False, "message": "customer_id must be a whole number, such as 57"}
    try:
        day = datetime.date.fromisoformat(str(as_of or "").strip())
    except ValueError:
        return {"ok": False, "message": "as_of must be a date written YYYY-MM-DD, such as 2024-03-23"}
    if day.year != 2024:
        return {"ok": False, "message": "the warehouse holds 2024 only; as_of must be a day in 2024"}
    order = None
    if order_id not in (None, ""):
        order = whole_number(order_id)
        if order is None:
            return {"ok": False, "message": "order_id must be a whole number, or left out"}

    connection = connect()                               # one connection for all the queries below
    try:
        return claims_answer(connection.cursor(), customer, day, order)
    finally:
        connection.close()


def within_48_hours(days):
    """The policy's 48-hour limit, judged from whole days: order dates in the warehouse have no time of day."""
    if days <= 1:
        return "yes"            # at most 1 day after the order date: under 48 hours whatever the times
    if days == 2:
        return "cannot tell"    # 2 days could be anything from just over 24 to just under 72 hours
    return "no"                 # 3 days or more: past 48 hours whatever the times


def claims_answer(cursor, customer, day, order):
    """The answer for customer_claims, from one open cursor."""
    found = rows_of("SELECT name, city, status, is_internal FROM dim_customer WHERE customer_id = ?",
                    (customer,), cursor=cursor)
    if not found:
        return {"ok": False, "message": f"no customer {customer} in the warehouse"}
    name, city, status, is_internal = found[0]

    # Claims made on or before the as_of day only: later ones had not happened yet on that day.
    claims = rows_of("SELECT claim_id, order_id, claim_date, reason, amount, status FROM fact_refund_claim "
                     "WHERE customer_id = ? AND claim_date <= ? ORDER BY claim_date DESC, claim_id DESC",
                     (customer, day), limit=20, cursor=cursor)
    first_day = day - datetime.timedelta(days=WINDOW_DAYS - 1)
    in_window = rows_of("SELECT COUNT(*) FROM fact_refund_claim WHERE customer_id = ? AND claim_date BETWEEN ? AND ?",
                        (customer, first_day, day), cursor=cursor)[0][0]

    answer = {
        "ok": True,
        "customer": {"customer_id": customer, "name": name, "city": city, "status": status,
                     "is_test_account": bool(is_internal)},
        "as_of": day.isoformat(),
        "claims_in_last_30_days": in_window,
        "window": f"{first_day.isoformat()} to {day.isoformat()}, every claim whatever its status",
        "claims": [dict(zip(["claim_id", "order_id", "claim_date", "reason", "amount", "status"], c)) for c in claims],
        "claims_shown": f"the {len(claims)} most recent claims on or before {day.isoformat()}, at most 20",
    }

    if order is not None:
        rows = rows_of("SELECT customer_id, order_date, order_value, status FROM orders_v2 WHERE order_id = ?",
                       (order,), cursor=cursor)
        if not rows:
            answer["order"] = {"order_id": order, "message": f"no order {order} in the warehouse"}
        elif rows[0][0] != customer:
            # Another customer's order: say so, and show none of its details.
            answer["order"] = {"order_id": order, "belongs_to_this_customer": False,
                               "message": "this order belongs to a different customer"}
        else:
            _, placed, value, order_status = rows[0]
            days = (day - datetime.date.fromisoformat(placed[:10])).days
            if days < 0:
                answer["order"] = {"order_id": order, "belongs_to_this_customer": True,
                                   "message": f"this order was placed on {placed[:10]}, after {day.isoformat()}"}
            else:
                answer["order"] = {"order_id": order, "order_date": placed[:10], "order_value": value,
                                   "status": order_status, "belongs_to_this_customer": True,
                                   "days_from_order_date_to_as_of": days,
                                   "within_48_hours_of_order": within_48_hours(days),
                                   "note": "order dates have no time of day, so 48 hours is judged in whole days"}
    return answer


# ---------------- official_number: the semantic layer from Lab 6 ----------------

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


# ---------------- Part C: one restaurant's orders, and three practice actions ----------------

FAILING_REFUND = 2185        # this refund always fails, so the lab can see how an agent handles a failed step


def day_of(text):
    """A day of 2024 written YYYY-MM-DD, or None."""
    try:
        day = datetime.date.fromisoformat(str(text or "").strip())
    except ValueError:
        return None
    return day if day.year == 2024 else None


def restaurant_orders(restaurant_id, first_day, last_day):
    """Every order of one restaurant between two days (at most 31 days): order, customer, date, value, status.
    It says nothing about test accounts or claims: get_customer_claims tells those, one customer at a time."""
    restaurant = whole_number(restaurant_id)
    first, last = day_of(first_day), day_of(last_day)
    if restaurant is None or first is None or last is None:
        return {"ok": False, "message": "give restaurant_id as a whole number and first_day, last_day as YYYY-MM-DD in 2024"}
    if last < first or (last - first).days > 30:
        return {"ok": False, "message": "last_day must be on or after first_day, at most 31 days in all"}
    rows = rows_of("SELECT order_id, customer_id, order_date, order_value, status FROM orders_v2 "
                   "WHERE restaurant_id = ? AND order_date BETWEEN ? AND ? ORDER BY order_date, order_id",
                   (restaurant, first, last), limit=1000)
    return {"ok": True, "restaurant_id": restaurant, "first_day": first.isoformat(), "last_day": last.isoformat(),
            "orders": [dict(zip(["order_id", "customer_id", "order_date", "order_value", "status"], r)) for r in rows]}


def order_of(order, customer):
    """The order's customer and value, or a message saying why the action cannot go ahead."""
    rows = rows_of("SELECT customer_id, order_value FROM orders_v2 WHERE order_id = ?", (order,))
    if not rows:
        return None, f"no order {order}"
    if rows[0][0] != customer:
        return None, "this order belongs to a different customer"
    return rows[0][1], None


def create_refund(order_id, customer_id, amount, reason):
    """A practice refund: checks the order and the amount, then returns a receipt. No money moves."""
    order, customer = whole_number(order_id), whole_number(customer_id)
    try:
        value = None if isinstance(amount, bool) else float(amount)
    except (TypeError, ValueError):
        value = None
    if order is None or customer is None or value is None or not math.isfinite(value) or value <= 0:
        return {"ok": False, "message": "give order_id, customer_id and a positive amount"}
    order_value, problem = order_of(order, customer)
    if problem:
        return {"ok": False, "message": problem}
    if value > order_value + 0.005:
        return {"ok": False, "message": f"the amount is more than the order value, {order_value}"}
    if order == FAILING_REFUND:
        return {"ok": False, "message": "the payment service did not respond: no refund was created for this order"}
    return {"ok": True, "refund_id": f"RF-{order}", "order_id": order, "amount": round(value, 2),
            "reason": str(reason or "")[:200], "note": "practice receipt: no money moves"}


def escalate(order_id, customer_id, reason):
    """A practice escalation to a support supervisor: returns a ticket number."""
    order, customer = whole_number(order_id), whole_number(customer_id)
    if order is None or customer is None or not str(reason or "").strip():
        return {"ok": False, "message": "give order_id, customer_id and the reason"}
    _, problem = order_of(order, customer)
    if problem:
        return {"ok": False, "message": problem}
    return {"ok": True, "ticket_id": f"SUP-{order}", "order_id": order, "reason": str(reason or "")[:200],
            "note": "practice ticket: nothing is saved"}


def send_email(customer_id, message):
    """A practice email to a customer: returns a message number. Nothing is sent."""
    customer = whole_number(customer_id)
    text = str(message or "").strip()
    if customer is None or not text:
        return {"ok": False, "message": "give customer_id and the message text"}
    if not rows_of("SELECT 1 FROM dim_customer WHERE customer_id = ?", (customer,)):
        return {"ok": False, "message": f"no customer {customer}"}
    if len(text) > 2000:
        return {"ok": False, "message": "the message is longer than 2000 characters"}
    return {"ok": True, "email_id": f"EM-{customer}-{len(text)}", "customer_id": customer,
            "note": "practice email: nothing is sent"}


# ---------------- The six web addresses, for Foundry's OpenAPI tool ----------------

def reply(body):
    # Always status 200, with any problem in the body: Foundry stops the agent run on an error code.
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")


def safely(work):
    """Run one tool call; any failure comes back as ok false in the body, never as an error code."""
    try:
        return reply(work())
    except mssql_python.Error as error:
        return reply({"ok": False, "message": f"warehouse error: {str(error)[:200]}"})
    except Exception as error:                                   # anything else: still a readable answer
        return reply({"ok": False, "message": f"tool error: {type(error).__name__}"})


@app.route(route="customer_claims", methods=["GET"])
def customer_claims_http(req: func.HttpRequest) -> func.HttpResponse:
    return safely(lambda: customer_claims(req.params.get("customer_id"), req.params.get("as_of"),
                                          req.params.get("order_id")))


@app.route(route="restaurant_orders", methods=["GET"])
def restaurant_orders_http(req: func.HttpRequest) -> func.HttpResponse:
    return safely(lambda: restaurant_orders(req.params.get("restaurant_id"), req.params.get("first_day"),
                                            req.params.get("last_day")))


def body_of(req):
    """The JSON body of a POST, or an empty dict."""
    try:
        return req.get_json() or {}
    except ValueError:
        return {}


@app.route(route="create_refund", methods=["POST"])
def create_refund_http(req: func.HttpRequest) -> func.HttpResponse:
    b = body_of(req)
    return safely(lambda: create_refund(b.get("order_id"), b.get("customer_id"), b.get("amount"), b.get("reason")))


@app.route(route="escalate", methods=["POST"])
def escalate_http(req: func.HttpRequest) -> func.HttpResponse:
    b = body_of(req)
    return safely(lambda: escalate(b.get("order_id"), b.get("customer_id"), b.get("reason")))


@app.route(route="send_email", methods=["POST"])
def send_email_http(req: func.HttpRequest) -> func.HttpResponse:
    b = body_of(req)
    return safely(lambda: send_email(b.get("customer_id"), b.get("message")))


@app.route(route="official_number", methods=["GET"])
def official_number_http(req: func.HttpRequest) -> func.HttpResponse:
    return safely(lambda: official_number(req.params.get("metric"), req.params.get("period"),
                                          req.params.get("breakdown")))
