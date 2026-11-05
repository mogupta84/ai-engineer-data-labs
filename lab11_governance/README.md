# Lab 11: privacy and access control, who may see what

Start with the handbook, **[Lab11_who_may_see_what.pdf](Lab11_who_may_see_what.pdf)**. Everything runs in the
browser.

```
Lab11_who_may_see_what.pdf   the handbook
lab11_support_notes.txt      G1: the support notes to paste in (made up for the lab); open it and copy all its text
lab11_g2_queries.txt         G2: three ready-made searches to paste into Search explorer
code/                        the optional Lab 11 scripts: put a .env with FOUNDRY_PROJECT_ENDPOINT, LANGUAGE_ENDPOINT,
                             SEARCH_ENDPOINT and SEARCH_QUERY_KEY next to them, run
                             python -m pip install -r requirements.txt, and sign in as in Lab 8 (az login or VS Code)
```

The same optional code is also in the lab8_foundry folder (lab11_1_pii.py, lab11_2_who_sees_what.py), where it uses
Lab 8's environment, sign-in and .env file. The trainer's index script, code/lab11_0_build_index.py, needs
SEARCH_ADMIN_KEY and Lab 9's read/ folder, so the trainer runs it from lab8_foundry.
