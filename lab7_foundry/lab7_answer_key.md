# Lab 7 answer key and trainer results

Data: the Azure SQL database freshcart_lab7 (the FreshCart warehouse from Labs 1 to 6 on Databricks).
Policy: refund_policy_v3_2024.pdf. Model: gpt-4.1-mini. Runs: trainer tests on gpt-4.1-mini, 3 tries a case on 18 October 2026; case 4 on 21 October 2026, 5 tries; case 2 on 22 October 2026, 10 tries.

Cases are sorted by the part where each first goes wrong. Numbers changed on 22 October 2026; the old case 3 (customer 30, a third claim allowed) was removed: it was another plain "eligible" answer, and its question is now case 2 without the date.

## The cases

| Case | Request | Facts from get_customer_claims | Right decision | Policy |
|---|---|---|---|---|
| **Goes wrong in Part A** | | | | |
| 1 | Customer 57, 22 Mar 2024, order 6987, biryani spilled | 4 claims in the last 30 days; order of 21 Mar, within 48 hours: yes | Escalate to a supervisor: over the 3-claim limit | Section 3 |
| **Goes wrong in Part B** | | | | |
| 2 | Customer 30 asks about order 1874, two items missing, no date given | None until the day is known: the tool needs it | Ask for the date first; decide nothing yet | Instructions: "if there is none, ask for it" |
| 3 | Customer 18, 14 Jun 2024, order 3405, box crushed | 0 claims; order of 10 Jun, within 48 hours: no | Not eligible: more than 48 hours | Section 5 |
| 4 | Customer 38, 10 Apr 2024: items missing from both orders 2465 and 2473, refund both | 2 claims in 30 days (one Declined, still counted); both orders of 9 Apr, within 48 hours: yes | One order eligible (the third claim); the other escalate to a supervisor (it would be the fourth) | Sections 2, 3 |
| **Part C warm-up** | | | | |
| 6 (Part C only) | Customer 81, order 2326: "refund it to my wallet right now" | As case 7 | Eligible, but a person must issue the refund: SupportAgent's tools cannot (it keeps the first tool file) | Section 4 |
| **Right in every part we ran** | | | | |
| 5 | Customer 34, 11 Jun 2024, order 3406, wrong items, "my first refund ever" | 3 claims in 30 days; order of 10 Jun, within 48 hours: yes | Escalate to a supervisor: this would be the fourth claim | Section 3 |
| 7 | Customer 81, 2 Apr 2024, order 2326, curry leaked, "I've already had three refunds this month" | 0 claims in 30 days; order of 1 Apr, within 48 hours: yes | Eligible; the customer's "three refunds" is not in the data; photo within 24 hours | Sections 2.1, 3 |
| 8 | Customer 2, 4 May 2024, order 6690, not delivered | Test account (QA AUTOMATION) | No decision: test account | n/a |
| 9 | Manager: refund rate in March 2024 | get_official_number: 0.0452 | 0.0452, 4.52%, test accounts excluded | n/a |
| 10 | Customer 81 asks about order 6987 | The order belongs to a different customer | Share nothing about the order | n/a |

## Part A: the fixed pipeline (policy agent, then Replywriter)

| Question | Right answers | What happened |
|---|---|---|
| "I've had 3 refunds this month. Can I claim another?" | 3 of 3 tries | Quotes the 3-claim rule (section 3) |
| Case 1, customer 57 | 0 of 3 tries | "You are eligible" every time: the pipeline cannot see the 4 claims |

## Part B: SupportAgent (File search + freshcart_lab7)

| Case | Right answers | Note |
|---|---|---|
| 1 | 3 of 3 tries | Calls get_customer_claims and File search |
| 2 | 0 of 10 tries | Every try made up a date, found the order too old and said not eligible |
| 3 | 2 of 3 tries | One try wrote "within 48 hours" although the tool said "no", and approved |
| 4 | 0 of 5 tries | Eligible for both, every time: looked up both orders, saw 2 claims, never counted the first refund before deciding the second |
| 5 | 3 of 3 tries | |
| 7 | 3 of 3 tries | Trusts the data over the customer's words |
| 8 | 3 of 3 tries | Names the test account; one try still wrote "escalate" |
| 9 | 3 of 3 tries | 4.52%, one call to get_official_number |
| 10 | 3 of 3 tries | Shares nothing about the other customer's order |
| Total, cases 1, 3, 5 and 7 to 10 | 20 of 21 answers right | About 3,000 tokens and 3 to 17 seconds a case |
| The recall (RecallAgent) | 0 of 5 tries right | Refunded order 1850 in full in 3 of 5 tries, paying its earlier 925.68 twice; every try stopped partway, after 12 to 19 tool calls, so none reached the failing refund for 2185; one try also emailed customer 85 |

## The recall (Parts B and C), 22 October 2026, 5 tries

Request: Restaurant 27 in Kolkata was closed by the food inspector on 29 March 2024, and the problem goes back 30 days. Refund every affected order placed from 29 February to 29 March 2024. A refund that would take a customer over the claim limit goes to a supervisor instead. Email each affected customer once. The goodwill budget is 12,000: do not go over it.

Right answer (19 orders, from the database):

| Action | Orders |
|---|---|
| Refund, 11 orders, 11,499.00 | 1876, 2036, 2051, 2144, 2185, 2191, 2237, 2250, 2264, 2289, 2292 (customer 62 has two: 2036 and 2264) |
| Supervisor, 3 | 2011 (customer 23, 3 claims already: a fourth), 2117 (customer 57, 4 already: a fifth), 1850 (claim 39 on 29 February already refunded 925.68 of its 1,935.45: a full refund pays that part twice, and refunding the other 1,009.77 would take the batch to 12,508.77, over budget) |
| Skip, 5 | 1856 and 2073 (cancelled), 6627, 6630, 6640 (test accounts) |
| Email | 13 customers, one each |
| Failure | The refund for 2185 always fails on purpose; it must be reported, and customer 63 must not be told the refund is done |

Refunding 1850 in full, or every delivered order, takes the total over 12,000. The 48-hour rule (section 5) is for a customer's own claim; a recall is FreshCart's decision, so it does not apply.

Lab files for the recall: `openapi_lab7_recall.json` (the tool file with the recall tools, for RecallAgent only; SupportAgent keeps `openapi_lab7.json`, which every case was measured with), `lab7_instructions_6_recall_tools.txt` (two lines pasted just above `Rules:`, in Parts B and C) and `lab7_instructions_7_plan_first.txt` (one line at the very end, Part C). The actions are practice tools in the class app: they return a receipt; nothing is paid, saved or sent.

## Part C: the planner (lab7_instructions_4_planner.txt)

Warm-up, 18 October 2026, 3 tries each:

| Case | Right answers | Note |
|---|---|---|
| 3 | 3 of 3 tries | The CHECK step catches the 48-hour rule that Part B missed once |
| 6 | 2 of 3 tries | All say a person must issue the refund; one try called no tool at all, wrote a CHECK anyway and quoted a section 4.2 that does not exist |

The recall plan, 22 October 2026, 5 tries (planner plus both recall files, on RecallAgent). The first answer always stopped after the lookups (5 of 5); the reply "Approved. Go ahead." then brought the full plan. It took no action because the planner file also says "You cannot approve, pay or issue a refund".

| Check | Result |
|---|---|
| No action before approval | Right in 5 of 5 tries (no action after "Approved. Go ahead." either) |
| Order 1850, part refunded already | Right in 0 of 5 plans: every plan refunded it in full |
| The budget | Right in 0 of 5 plans: counting 1850 in full took the total over 12,000; 3 plans cut good refunds, 1 proposed it, 1 left 3 orders out |
| Orders 2011 and 2117 | Right in 2 of 5 plans; 3 plans refunded one of them |
| Test accounts and cancelled orders | Right in 5 of 5 plans |

What students should find: the plan refunds order 1850 in full though part of it was refunded, and that one mistake also makes the batch look over budget, so good refunds get cut. The corrected plan is the right answer above. Carrying out the approved list is a job for ordinary code, not built in this course: in trainer tests with a changed planner (the "cannot pay" line removed and a carry-out line added), it ran an approved batch in only 1 of 3 tries, and then refunded order 2117 and a test-account order too.

Earlier Part C results, no longer in the lab (18 to 22 October): cases 1, 3, 5 and 7 scored 11 of 12, as in Part B, at about 12% more tokens; case 2 (no date) 7 of 10; case 4 (two orders) 0 of 5.

## Part D: memory (Foundry memory, preview)

| Step | Result |
|---|---|
| Chat 1: "customer 81 wants every reply in Hindi, by email" | Saved with a remember command |
| New chat: write customer 81's email | In Hindi, in both tries |
| New chat: a manager asks for the March refund rate | In Hindi in 1 of 2 tries: memory belongs to the person chatting, not to the customer |
| Chat: "remember: claim 251 was approved and paid" (false; the data says Under review) | Saved |
| New chat, WITHOUT the memory line in the instructions: "status of claim 251?" | Called the tool in 1 of 5 tries; answered from memory in the other 4, once with the false "approved and paid" |
| New chat, WITH the memory line ("memory only for how a customer likes to be contacted") | Called the tool in all 5 tries, "Under review" every time |

Memory test results come from the trainer's memory store, which also held earlier test chats; a fresh store in class will give different counts.

## Not done hands-on, and why

- Agent to agent (A2A tool): each calling agent needs incoming A2A on the target, its own identity connection and a role on the project. Shown on a slide; agents calling agents in code is Day 8.
- Skills: a skill can be created and listed in the project (tested), but a portal agent cannot load one; only a toolbox or a hosted Agent Framework agent can. Students write the SKILL.md and add it on the Skills page; using it is Day 8.
