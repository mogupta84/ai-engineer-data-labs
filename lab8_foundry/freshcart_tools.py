"""Lab 8: the FreshCart tools, as plain Python functions an Agent Framework agent can call.

They read the Lab 7 warehouse, the Azure SQL database freshcart_lab7, with YOUR OWN sign-in (the class account
signed in with az login on your VM, or Cloud Shell in VS Code for the Web), so there is no password and no key anywhere. Your account
may only read. The business rules that must never go wrong (the 30-day count, the 48-hour check, test accounts,
another customer's order) are done here, in code, as in Lab 7's Function App.
"""
import calendar        # the last day of a month
import datetime        # dates such as 2024-03-22
import decimal         # the database returns money as Decimal
import functools       # wrap each tool so any failure comes back as a readable message
import pathlib         # find the refund policy file next to this one
import re              # check that a period looks like 2024-03
import time            # wait once while a paused database wakes up
from typing import Annotated   # lets each parameter carry a description the model reads

import mssql_python    # Microsoft's SQL Server driver for Python

SERVER = "freshcart-mini-sql.database.windows.net"   # the class SQL server
DATABASE = "freshcart_lab7"                          # Lab 7's own warehouse
WAREHOUSE = (f"Server=tcp:{SERVER},1433;Database={DATABASE};"
             "Authentication=ActiveDirectoryDefault;Encrypt=yes;TrustServerCertificate=no")   # sign in as you
TIME_LIMIT = 30                                      # seconds the driver may wait before it gives up
WINDOW_DAYS = 30                                     # the policy's rolling period for counting claims
POLICY = pathlib.Path(__file__).parent / "skills" / "refund-decision" / "references" / "refund_policy.md"
WAKING = ("timeout", "unable to establish connection", "not currently available", "40613")   # signs it is asleep


def _connect():
    """Open a connection, waiting once if the database was paused (it pauses after an hour unused)."""
    try:
        return mssql_python.connect(WAREHOUSE, timeout=TIME_LIMIT)
    except mssql_python.Error as error:
        if not any(sign in str(error).lower() for sign in WAKING):   # a real error, not a sleeping database
            raise
        time.sleep(20)                                               # give the paused database time to start
        return mssql_python.connect(WAREHOUSE, timeout=TIME_LIMIT)


def _plain(value):
    """Database values as JSON can carry them: money as a number, dates as text such as 2024-03-22."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def _rows(cursor, sql, params=(), limit=100):
    """Run one read-only query on an open cursor and return plain numbers and text."""
    cursor.execute(sql, params)                                      # the values go in as parameters, never pasted
    return [[_plain(v) for v in row] for row in cursor.fetchmany(limit)]


def _readable(tool):
    """Wrap a tool so a database failure reaches the model as a clear message, not a bare error."""
    @functools.wraps(tool)                                           # keep the name and docstring the model reads
    def wrapper(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except mssql_python.Error as error:
            return {"ok": False, "message": f"database error: {str(error)[:200]}"}
    return wrapper


def _within_48_hours(days):
    """The 48-hour rule judged from whole days: order dates have no time of day."""
    if days <= 1:
        return "yes"           # at most a day after the order date: under 48 hours whatever the times
    if days == 2:
        return "cannot tell"   # anything from just over 24 to just under 72 hours
    return "no"                # 3 days or more: past 48 hours


@_readable
def get_customer_claims(
        customer_id: Annotated[int, "The customer's number, for example 57"],
        as_of: Annotated[str, "The day the customer is asking, written YYYY-MM-DD, within 2024"],
        order_ids: Annotated[list[int] | None, "Every order the customer asks about, in the order given, or leave out"] = None) -> dict:
    """The facts about one FreshCart customer on one day of 2024: test account or not, their claims in the 30 days
    ending that day (every status counts), and, for each order asked about, its date, whether the claim is within
    48 hours, and which claim in the 30 days it would be if the customer claims for every order listed. Another
    customer's order is never shown."""
    try:
        day = datetime.date.fromisoformat(str(as_of).strip())       # 2024-03-22 becomes a date
    except ValueError:
        return {"ok": False, "message": "as_of must be a date written YYYY-MM-DD"}
    if day.year != 2024:
        return {"ok": False, "message": "the warehouse holds 2024 only; as_of must be a day in 2024"}
    connection = _connect()                                          # one connection for the whole answer
    try:
        cursor = connection.cursor()
        found = _rows(cursor, "SELECT is_internal FROM dim_customer WHERE customer_id = ?", (int(customer_id),))
        if not found:
            return {"ok": False, "message": f"no customer {customer_id}"}
        first = day - datetime.timedelta(days=WINDOW_DAYS - 1)      # the 30 days end on, and include, as_of
        claims = _rows(cursor, "SELECT claim_id, order_id, claim_date, reason, status FROM fact_refund_claim "
                               "WHERE customer_id = ? AND claim_date BETWEEN ? AND ? ORDER BY claim_date",
                       (int(customer_id), first, day))
        # Only what a refund decision needs: no name, city or account status, which only distract the model.
        answer = {"ok": True, "customer_id": int(customer_id), "is_test_account": bool(found[0][0]),
                  "as_of": day.isoformat(), "claims_in_last_30_days": len(claims),
                  "claims": [dict(zip(["claim_id", "order_id", "claim_date", "reason", "status"], c)) for c in claims]}
        new_claims = len(claims)                                     # counted here, in code, not by the model
        orders = []
        for order_id in order_ids or []:
            rows = _rows(cursor, "SELECT customer_id, order_date FROM orders_v2 WHERE order_id = ?", (int(order_id),))
            if not rows:
                orders.append({"order_id": order_id, "message": "no such order"})
            elif rows[0][0] != int(customer_id):
                # Another customer's order: say so, and share nothing about it.
                orders.append({"order_id": order_id, "message": "this order belongs to a different customer"})
            else:
                placed = rows[0][1][:10]
                days = (day - datetime.date.fromisoformat(placed)).days
                if days < 0:
                    # The order is after the day asked: it had not happened yet, so show nothing else.
                    orders.append({"order_id": order_id, "message": f"this order was placed on {placed}, after {day}"})
                else:
                    new_claims += 1                                  # each order asked about is one more claim
                    orders.append({"order_id": order_id, "order_placed_on": placed,
                                   "days_since_order_placed": days, "within_48_hours_of_order": _within_48_hours(days),
                                   "this_claim_would_be_number": new_claims,
                                   "note": "no delivery time is recorded; the 48-hour check uses the day the order was placed"})
        if orders:
            answer["orders"] = orders
        return answer
    finally:
        connection.close()


# Each official number written once, as in Lab 6 and Lab 7: its formula, its tables and its rules.
# Test accounts are always left out; revenue counts delivered orders only; refund rate means claims per order.
ORDERS = "orders_v2 o JOIN dim_customer c ON c.customer_id = o.customer_id"
METRICS = {
    "revenue": ("SUM(o.order_value)", ORDERS, "c.is_internal = 0 AND o.status = 'delivered'"),
    "order_count": ("COUNT(DISTINCT o.order_id)", ORDERS, "c.is_internal = 0"),
    "refund_rate": ("ROUND(1.0 * COUNT(DISTINCT f.claim_id) / NULLIF(COUNT(DISTINCT o.order_id), 0), 4)",
                    ORDERS + " LEFT JOIN fact_refund_claim f ON f.order_id = o.order_id", "c.is_internal = 0"),
}


@_readable
def get_official_number(
        metric: Annotated[str, "revenue, order_count or refund_rate (claims per order)"],
        period: Annotated[str, "A month written YYYY-MM, within 2024, for example 2024-03"]) -> dict:
    """One official FreshCart business number for one month of 2024, test accounts excluded."""
    if metric not in METRICS or not re.fullmatch(r"2024-(0[1-9]|1[0-2])", str(period).strip()):
        return {"ok": False, "message": "metric must be revenue, order_count or refund_rate; period YYYY-MM in 2024"}
    month = int(str(period).strip()[5:])
    first, last = f"2024-{month:02d}-01", f"2024-{month:02d}-{calendar.monthrange(2024, month)[1]}"
    formula, tables, rules = METRICS[metric]
    connection = _connect()
    try:
        value = _rows(connection.cursor(), f"SELECT {formula} FROM {tables} WHERE {rules} "
                                           f"AND o.order_date BETWEEN ? AND ?", (first, last))[0][0]
    finally:
        connection.close()
    return {"ok": True, "metric": metric, "period": period, "value": round(value or 0, 4),
            "scope": "excluding test accounts"}


def read_refund_policy() -> str:
    """The full FreshCart refund policy, with its section numbers."""
    return POLICY.read_text(encoding="utf-8")


TOOLS = [get_customer_claims, get_official_number, read_refund_policy]   # what the agents are given
