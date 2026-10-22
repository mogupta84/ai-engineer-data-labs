---
name: refund-decision
description: Decide a FreshCart refund request step by step from the refund policy and the customer's own records. Use when support staff ask whether a customer can get a refund for an order.
---

# Refund decision

Use this procedure for every refund request.

1. Get the request's facts: customer number, order number, the day the customer is asking, and what went wrong.
2. Check the customer's records with get_customer_claims for that day and that order.
   - Test account: stop and say it is a test account.
   - Order of a different customer: stop and share nothing about it.
3. Check the reason is eligible (policy section 2): not delivered, materially incomplete, spilled or damaged, or wrong items.
4. Check the time limit (section 5): more than 48 hours after delivery is excluded. If the tool says "cannot tell", escalate to a supervisor.
5. Check the claim limit (section 3): if the customer already has 3 or more claims in the last 30 days, this claim is declined automatically and goes to a supervisor.
6. Spillage or damage (section 2.1): ask for a photo within 24 hours of delivery; partial leakage gets up to fifty percent of item value.
7. Answer with the rules you used, each with its section number, and end with one line:
   DECISION: eligible, not eligible, or escalate to a supervisor, and the reason in a few words.

Never approve, pay or issue a refund yourself: a person does that.
