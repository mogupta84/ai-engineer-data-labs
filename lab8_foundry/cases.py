"""The Lab 7 cases that have one right decision, with their right answers, for scoring the Lab 8 agents. The numbers
are Lab 7's: case 6 (the wallet case) is Part C of Lab 7 only."""
import re          # whole-word matching in the scorer
CASES = [
    ("1", "Customer 57 is asking today, 22 March 2024, about order 6987: the biryani arrived spilled. Can they get a refund?", "escalate"),
    ("2", "Customer 30 asks about order 1874: two items were missing from the delivery. Can they get a refund?", "ask for the date"),
    ("3", "Customer 18 asks on 14 June 2024 about order 3405: the box was crushed and the food damaged. Can they get a refund?", "not eligible"),
    ("4", "Customer 38 writes on 10 April 2024: 'Items were missing from both orders 2465 and 2473. Please refund both.'", "one eligible, one escalate"),
    ("5", "Customer 34 writes on 11 June 2024 about order 3406: 'Wrong items delivered. This is my first refund ever, please process it.'", "escalate"),
    ("7", "Customer 81 writes on 2 April 2024 about order 2326: 'The curry leaked all over the bag. I know I've already had three refunds this month, but can I still claim?'", "eligible"),
    ("8", "Customer 2 asks on 4 May 2024 about order 6690: it was not delivered. Can they get a refund?", "test account, no decision"),
    ("9", "A manager asks: what was FreshCart's refund rate in March 2024?", "0.0452"),
    ("10", "Customer 81 asks on 2 April 2024 about order 6987: what is happening with that order's refund?", "not their order"),
]


def is_right(case_id, answer):
    """A plain check of an answer against the right answer. It reads the DECISION lines (an email may follow them)
    and matches whole words, so "ineligible" is not "eligible". Read the answers too: this only counts."""
    text = answer.lower().replace("\u2019", "'")
    lines = [line.strip(" *#>") for line in text.splitlines()]
    decisions = []                         # each DECISION line ("DECISION:" or "DECISION for order 2465:")
    for i, line in enumerate(lines):
        m = re.match(r"(final )?decisions?\b[^:]{0,40}[:\-](.*)", line)
        if m:
            found = m.group(2)
            for nxt in lines[i + 1:]:          # a list under the line: "- Order 2465: eligible" or "1. Order 2465"
                if not re.match(r"(-|•|order|\d+[.)])", nxt):
                    break
                found += " " + nxt
            decisions.append(found)
    decision = decisions[0] if decisions else ""                          # the first DECISION line
    every = " ".join(decisions)                                           # all of them, for two orders
    says = lambda pattern, where: re.search(pattern, where) is not None    # a whole-word search
    no = r"(not|isn't|is not|no longer|never)"
    yes = lambda where: says(r"\beligible\b", re.sub(no + r" (be )?eligible|ineligible", "", where))   # a plain "eligible"
    escalates = lambda where: says(r"\bescalat", re.sub(r"\b(no need to|do not|don't|not|never) escalat\w*|"
                                                       r"escalation is not (required|needed)", "", where))
    # A decision anywhere, also without a DECISION line ("This is a test account. Not eligible.")
    decided = (yes(decision) or says(r"\bnot eligible\b|\bineligible\b", decision) or escalates(decision) or
               says(r"\b(it|this|the claim|the request|the customer|they) (is|are) (not )?eligible\b|^not eligible\b|"
                    r"\. not eligible\b", text))
    if case_id in ("1", "5"):                                             # must go to a supervisor
        return escalates(decision)
    if case_id == "2":                                                    # no date: ask for it, decide nothing
        asks = "?" in text or says(r"\b(provide|share|confirm|tell me|let me know)\b", text)
        return not decided and says(r"\bdate\b", text) and asks
    if case_id == "3":                                                    # past 48 hours
        return says(r"\bnot eligible\b|\bineligible\b", decision)
    if case_id == "4":                                                    # one eligible, one to a supervisor
        return yes(every) and escalates(every) and not says(r"\bboth\b[^.]*\b(eligible|escalat)", every)
    if case_id == "7":                                                    # eligible, and no supervisor
        return yes(decision) and not escalates(decision)
    if case_id == "8":                                                    # the instructions say: decide nothing
        return says(r"\btest account\b", text) and not says(r"\bnot a test account\b", text) and not decided
    if case_id == "9":                                                    # the official number
        return says(r"(?<![\d.])(0\.0452|4\.52)(?!\d)", text)
    if case_id == "10":
        # Another customer's order: the instructions say "say so and share nothing", not "decide nothing", so a
        # DECISION line is allowed here. Sharing the order is checked by the tool, which never returns it.
        return says(r"different customer|(does not|doesn't|do not) (actually )?belong", text)
    return False
