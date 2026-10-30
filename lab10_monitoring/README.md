# Lab 10: evaluation and monitoring, knowing when it breaks

Handbook: Lab10_knowing_when_it_breaks.pdf.

portal/lab10_gate_cases.jsonl      Parts A and B: 7 Lab 7 cases with their right answers, uploaded as the evaluation's dataset
portal/right_decision_prompt.txt   Part A: the judge's instructions, pasted into the evaluator
portal/cost_fault_partner_list.txt Part A, fault 2: the long list of restaurants pasted into your agent
notebooks/lab10_0_refresh.ipynb    Part C: the pipeline's first step, so the quality check sees the newest tickets
notebooks/lab10_3_health.ipynb     Part C: five health checks on your Lab 9 pipeline, each with an owner and a first action
notebooks/lab10_4_drift.ipynb      Part D: embedding drift and one MLflow run per day to chart

Optional, the same in code (the handbook appendix): lab10_1_gate.py, gate.json and lab10_2_traces.py are not in these
files; your trainer can share them. They run in your lab8_foundry folder from Lab 8, with Lab 8's environment and sign-in.
