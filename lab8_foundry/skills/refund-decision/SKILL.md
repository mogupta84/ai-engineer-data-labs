---
name: refund-decision
description: Decide a FreshCart refund request step by step from the refund policy and the customer's own records. Use for every refund request or claim about an order, both when support staff ask whether a customer can get a refund and when a customer asks in their own words whether they can claim.
---

# Refund decision

Use this procedure for every refund request. The refund policy is in references/refund_policy.md.

1. Get the request's facts: customer number, every order number, the day the customer is asking, and what went wrong. If the request gives no date, ask for it and stop: decide nothing.
2. Call get_customer_claims for that customer, that day and every order asked about.
   - Test account: stop, say it is a test account, and make no decision.
   - An order of a different customer: stop and share nothing about it.
3. Check the reason is eligible (policy section 2): not delivered, materially incomplete, spilled or damaged, or wrong items.
4. Check the time limit (section 5): more than 48 hours after delivery is excluded. "within_48_hours_of_order: no" means not eligible; "cannot tell" means escalate to a supervisor.
5. Check the claim limit (section 3): a customer may make up to 3 claims in 30 days. For each order, read this_claim_would_be_number: the tool counts it. If it is 4 or more, that claim is declined automatically and goes to a supervisor. Trust the number from the tool, never the customer's own count.
6. Spillage or damage (section 2.1): ask for a photo within 24 hours of delivery.
7. Answer with the rules you used, each with its section number, and end with one line:
   DECISION: eligible, not eligible, or escalate to a supervisor, and the reason in a few words. For more than one order, one DECISION line per order.

Never approve, pay or issue a refund yourself: a person does that.
