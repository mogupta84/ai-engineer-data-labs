# AI Engineer (Data): Labs 1 to 6

The labs of the AI Engineer (Data) programme, with their data, so you can run them again on your own
Databricks workspace. **Start with the essentials labs.** They are the course labs from now on.

New here? Read the **[onboarding guide to Labs 1 to 6](AI_Engineer_Data_Onboarding_Guide_Labs_1-6.pdf)**
(PDF, 6 pages): how to get the labs, how to run them, and what each lab teaches.

## Start here: the essentials labs

Six short labs, about 50 minutes each, in `databricks/essentials/`. Each one uses LangChain from start
to finish, has a comment on every line of code, shows its problems in the middle of the notebook, and
ends with a **Look it up yourself** cell that lists every setting of the libraries it used.

| Day | Lab | What you do | Notebook |
|---|---|---|---|
| 1 | 1 | Load seven files in four formats with LangChain, find the problems no error message shows, cut them into pieces and search them by meaning | `lab01_essentials` |
| 2 | 2 | Put the same pieces into Chroma, Qdrant and FAISS, compare their scores and recall, and see why filtering after the search loses results | `lab02_essentials` |
| 3 | 3 | Add keyword search, rank merging, a reranker and a recency filter one at a time, and score each stage on 20 judged questions with nDCG@10 | `lab03_essentials` |
| 4 | 4 | Build an answer service with a real model that cites its sources, catch fake citations in code, and measure refusals and right facts | `lab04_essentials` |
| 5 | 5 | Give a model three tools (document search, an official business number, SQL), watch which it picks, break it three ways, and serve two tools from an MCP server | `lab05_essentials` |
| 6 | 6 | Let a model write SQL, find the numbers that are wrong with no error, add business rules and worked examples, and replace free SQL with a semantic layer, a sentence and a chart | `lab06_essentials` |

Run them in order: each one builds on the last.

### Set up once (10 minutes)

You need a Databricks workspace with serverless compute. The free edition works for Labs 1 to 3; Labs 4
to 6 also need Databricks' served models (below).

1. In the sidebar, click **Workspace**, then open your Home folder.
2. Click **Create**, then **Git folder**.
3. Paste `https://github.com/mogupta84/ai-engineer-data-labs` as the Git repository URL and click **Create Git folder**.
4. Open `databricks/essentials/lab01_essentials`, attach **Serverless**, and click **Run all**.
5. Read each step while it runs. Each step says **What this does** and **What you should see**, so you
   can check your output against it.

To take just one lab instead: click **Import** in your Home folder, choose **URL**, and paste its raw
link, for example `https://raw.githubusercontent.com/mogupta84/ai-engineer-data-labs/main/databricks/essentials/lab05_essentials.ipynb`.

### What to expect

- **The first cell installs the libraries and restarts Python**, about one to two minutes. The restart
  is expected. A red line about `fastapi` and `starlette` in Lab 5 can be ignored.
- **The data downloads itself.** On the first run each notebook fetches the FreshCart documents, the
  warehouse and the test questions from this repository. No keys and no uploads.
- **Labs 4, 5 and 6 call a language model** that Databricks serves, `databricks-meta-llama-3-3-70b-instruct`.
  You sign in as yourself, so there is no key. It is billed per use, a few cents a run. If your workspace
  does not offer served models, those three labs stop at the model step.
- **The served model allows only a few calls a second per workspace.** If several people run Labs 4 to
  6 at once, some calls wait and retry. Run them one at a time if you can.
- **Numbers can move a little between runs**, even with the model set to its most predictable setting.
  Each step's **What you should see** gives the range we measured.

The data is a fictional food delivery company, FreshCart: two refund policies, a partner contract, a
scanned procedure, a Word table, a slide deck, a spreadsheet and an orders warehouse, in `data/`.

## The full labs (Days 1 to 4, optional)

The longer class labs for Days 1 to 4, built on the course's own code, with more measurements and a
written answer sheet. Use them after the essentials if you want to go deeper.

| Day | Lab | What you do | Notebook |
|---|---|---|---|
| 1 | 1 | Load seven files in five formats, find the two that fail silently, cut them into pieces, label every piece, and see why a search returns a withdrawn policy | `lab01_ingest` |
| 2 | 2 | Put the same data into three vector databases, Chroma, Qdrant and FAISS, measure how much each finds and how fast, and defend one choice in a memo | `lab02_vector_stores` |
| 3 | 3 | Add keyword search, reranking and a recency filter to meaning search one at a time, and score each stage on 20 judged questions with nDCG@10 | `lab03_hybrid` |
| 3 | 3b | The same four stages with real models served by Databricks: an embedding model, a model reranker and a document reader for the scanned PDF (Databricks only) | `lab03b_real_models` |
| 4 | 4 | Build an answer service that cites its sources, break it with fake citations, measure refusals, supported sentences and right facts, and run it as an API | `lab04_rag_api` |

### Full labs on Databricks

Any workspace with serverless compute works, including the free edition. The first cell of each
notebook installs what that lab needs, about a minute. In Labs 1 and 2, Python then restarts. That
is expected.

**Option A: a Git folder (recommended).** It brings the notebooks and the data in one step.

1. In the sidebar, click **Workspace**, then open your Home folder.
2. Click **Create**, then **Git folder**.
3. Paste `https://github.com/mogupta84/ai-engineer-data-labs` as the Git repository URL and click **Create Git folder**.
4. Open `databricks/lab01_ingest`, attach **Serverless**, and click **Run all**. The other labs are
   next to it: `lab02_vector_stores`, `lab03_hybrid`, `lab03b_real_models` and `lab04_rag_api`.

**Option B: one notebook only.** Click **Import** in your Home folder, choose **URL**, and paste the
notebook's raw link, for example:

- `https://raw.githubusercontent.com/mogupta84/ai-engineer-data-labs/main/databricks/lab01_ingest.ipynb`
- `https://raw.githubusercontent.com/mogupta84/ai-engineer-data-labs/main/databricks/lab04_rag_api.ipynb`

Its setup cell downloads the code and the data from this repository on the first run.

Steps that behave differently outside class:

- **Lab 1, Step 2** runs `ai_parse_document`, Databricks' own document reader, on six small files.
  It is paid per page, so it costs a few cents at most. If your workspace does not offer it, the cell
  shows what it returned when the lab was built.
- **Lab 2, Step 7** measures a shared Databricks AI Search index that your trainer runs only during
  class. Anywhere else it prints `skipped`, and the rest of the lab runs as normal. Do not create an
  AI Search endpoint for this: every endpoint is billed by the hour while it holds an index.
- **Lab 3b and Lab 4** call models that Databricks serves, `databricks-gte-large-en` and
  `databricks-meta-llama-3-3-70b-instruct`. They are billed per use, a few cents a run, and need no
  key. If your workspace does not offer them, Lab 3b shows the recorded run from 8 October and Lab 4
  falls back to the offline answer writer for the questions the model could not answer, and says so.

### Full labs on Windows

1. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/). In the
   installer, tick **Add python.exe to PATH**.
2. Get this repository: click **Code**, then **Download ZIP**, and unzip it, for example to
   `C:\labs\ai-engineer-data-labs`. If you use Git: `git clone https://github.com/mogupta84/ai-engineer-data-labs.git`
3. Open **Command Prompt** in that folder and run:

   ```bat
   setup\setup_windows.cmd
   ```

   It creates a private Python environment in `.venv` and installs the packages, which takes 5 to 10
   minutes the first time.
4. Open the folder in [VS Code](https://code.visualstudio.com/) with its Python and Jupyter
   extensions. Open `notebooks\lab01_ingest.ipynb`, choose the `.venv` kernel when asked, and run
   all cells. Labs 2, 3 and 4 are in the same folder. Lab 3b runs only on Databricks.

On macOS or Linux, run these in the folder instead of step 3:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On your own machine, Lab 1, Step 2 shows the recorded results for its two layout tools: Docling
only runs once you install it (`pip install docling`, about 1.8 GB), and `ai_parse_document` exists
only on Databricks. Lab 2, Step 7 prints `skipped`. Labs 3 and 4 run fully offline, with free
stand-ins for the models: Lab 4's answer writer quotes the best piece of text instead of writing
in its own words.

### Lab 4 as an API

The Lab 4 notebook proves the logic. As an API, the same answer service takes a question from any
other program, such as a support screen, a chat window or a nightly test, and returns the answer
with its proof. A Databricks notebook cannot open a port, so this part runs on your own computer
or a Windows lab machine, with no keys.

1. **Start it**, in Command Prompt inside the repository folder, and leave the window open:

   ```bat
   .venv\Scripts\activate
   python labs\lab04_rag_api.py serve
   ```

   Wait for `API ready`. The first start can take up to a minute.
2. **Ask it a question** from a second Command Prompt in the same folder:

   ```bat
   .venv\Scripts\python labs\lab04_rag_api.py ask "How many refund claims can a customer make in thirty days?"
   ```

3. **Or use the browser page**: open `http://127.0.0.1:8000/docs`, choose **POST /ask**, click
   **Try it out**, send `{"question": "How many refund claims can a customer make in thirty days?", "threshold": 0.15}`
   and click **Execute**. **GET /health** shows the service is up.
4. **Stop it** with **Ctrl+C** in the server window.

On macOS or Linux, use `source .venv/bin/activate` and forward slashes in the paths.

What happens on one `/ask` call:

1. **Read the request.** FastAPI checks the question and the threshold (0.15 if left out). `labs/lab04_rag_api.py`
2. **Find candidates.** Meaning search and keyword search, merged by rank; the recency filter drops withdrawn policies. `src/retrieval.py`
3. **Rerank, keep 5.** Each piece gets a match score; the best 5 go forward. `src/retrieval.py`, run in order by `src/ragstack.py`
4. **Gate.** If the best match score is under the threshold, refuse with `no sufficiently relevant context`, before any answer is written. `src/rag.py`
5. **Write.** The answer writer gets the grounding prompt, the 5 pieces tagged with their ids, and the question, and cites ids in square brackets.
6. **Check citations.** Every cited id must be one of the 5 retrieved; otherwise refuse with `unverifiable citations`, or `no citation produced` if there is none. `src/rag.py`

Every response has the same six fields, refused or not:

| Field | For the refund question | What it means |
|---|---|---|
| `answer` | "... up to three refund claims ... [37801390e45c]" | the text, ending with the id of the piece it used |
| `citations` | `["37801390e45c"]` | ids in the answer, each checked against what was retrieved |
| `confidence` | 0.749 | the match score of the best piece: how well its words match the question, not how sure the model is |
| `retrieved` | 5 pieces, scores 0.749 to 0.266 | every piece sent to the answer writer, with its source file |
| `refused`, `refusal_reason` | `false`, `null` | `true` with the reason in words when the service will not answer |

**Try this:** ask "What is FreshCart's refund policy for grocery orders in Singapore?" No document
covers it. At threshold 0.15 the offline writer still answers, because its match score is 0.740.
Send it again with threshold 0.75 and it is refused with `no sufficiently relevant context`.

If something goes wrong:

- `'python' is not recognized`: run the activate line first, or use `.venv\Scripts\python` as in step 2.
- `ask` says the connection was refused: the server window is closed or not ready yet.
- Port 8000 is already in use: add `--port 8001` to both the `serve` and the `ask` command.
- The `/docs` page does not load: use `http`, not `https`, on the same machine; `127.0.0.1` means this machine only.

### How the full notebooks work

Every step shows you the real thing first. The cell marked `YOUR CALL` is the only one you edit:
type your prediction or your setting there, then run the next cell to see what really happens. Each
`YOUR CALL` cell already holds a working value, so a notebook runs from top to bottom before you
change anything.

## What is in this repository

```
databricks/essentials/  the essentials labs, Labs 1 to 6: start here
databricks/   the full labs for Databricks: Labs 1, 2, 3, 3b and 4
notebooks/    the full labs for your own machine: Labs 1 to 4
labs/         Labs 3 and 4 as command-line programs; lab04_rag_api.py also runs the API
src/          the lab code the notebooks call
data/raw/     the seven FreshCart documents
data/freshcart.db  the FreshCart orders warehouse, one SQLite file, for Labs 5 and 6
data/golden/  the judged and test questions for Labs 3 to 6, and what the two layout tools returned
handouts/     the one-page briefs, the answer sheets and the Lab 2 memo template
starter/      the labs as plain Python files, with TODOs, for the command line
solutions/    working versions of the Lab 1 and 2 starter files
setup/        the one-command Windows setup
```

Course material for participants of the AI Engineer (Data) programme.
