# AI Engineer (Data): Labs 1 and 2

The Week 1 labs of the AI Engineer (Data) programme, with their data, so you can run them again on
your own Databricks workspace or on your own computer.

| Lab | What you do | Notebook |
|---|---|---|
| 1 | Load seven files in five formats, find the two that fail silently, cut them into pieces, label every piece, and see why a search returns a withdrawn policy | `lab01_ingest` |
| 2 | Put the same data into three vector databases, Chroma, Qdrant and Milvus, measure how much each finds and how fast, and defend one choice in a memo | `lab02_vector_stores` |

The data is a fictional food delivery company, FreshCart: two refund policies, a partner contract,
a scanned procedure, a Word table, a slide deck and a spreadsheet, in `data/raw/`.

## On Databricks

Any workspace with serverless compute works, including the free edition. The first cell of each
notebook installs what that lab needs, about a minute, and then Python restarts. That is expected.

**Option A: a Git folder (recommended).** It brings the notebooks and the data in one step.

1. In the sidebar, click **Workspace**, then open your Home folder.
2. Click **Create**, then **Git folder**.
3. Paste `https://github.com/mogupta84/ai-engineer-data-labs` as the Git repository URL and click **Create Git folder**.
4. Open `databricks/lab01_ingest`, attach **Serverless**, and click **Run all**. Then do the same with
   `databricks/lab02_vector_stores`.

**Option B: one notebook only.** Click **Import** in your Home folder, choose **URL**, and paste the
notebook's raw link:

- `https://raw.githubusercontent.com/mogupta84/ai-engineer-data-labs/main/databricks/lab01_ingest.ipynb`
- `https://raw.githubusercontent.com/mogupta84/ai-engineer-data-labs/main/databricks/lab02_vector_stores.ipynb`

Its setup cell downloads the code and the data from this repository on the first run.

Two steps behave differently outside class:

- **Lab 1, Step 2** runs `ai_parse_document`, Databricks' own document reader, on six small files.
  It is paid per page, so it costs a few cents at most. If your workspace does not offer it, the cell
  shows what it returned when the lab was built.
- **Lab 2, Step 7** measures a shared Databricks AI Search index that your trainer runs only during
  class. Anywhere else it prints `skipped`, and the rest of the lab runs as normal. Do not create an
  AI Search endpoint for this: every endpoint is billed by the hour while it holds an index.

## On Windows

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
   all cells. Lab 2 is `notebooks\lab02_vector_stores.ipynb`.

On macOS or Linux, run these in the folder instead of step 3:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On your own machine, Lab 1, Step 2 shows the recorded results for its two layout tools: Docling
only runs once you install it (`pip install docling`, about 1.8 GB), and `ai_parse_document` exists
only on Databricks. Lab 2, Step 7 prints `skipped`.

## How the notebooks work

Every step shows you the real thing first. The cell marked `YOUR CALL` is the only one you edit:
type your prediction or your setting there, then run the next cell to see what really happens. Each
`YOUR CALL` cell already holds a working value, so a notebook runs from top to bottom before you
change anything.

## What is in this repository

```
databricks/   the two notebooks for Databricks
notebooks/    the same two notebooks for your own machine
src/          the lab code the notebooks call
data/raw/     the seven FreshCart documents
data/golden/  what the two layout tools returned when the lab was built
handouts/     the one-page briefs, the Lab 1 answer sheet and the Lab 2 memo template
starter/      Labs 1 and 2 as plain Python files, with TODOs, for the command line
solutions/    working versions of the starter files
setup/        the one-command Windows setup
```

Course material for participants of the AI Engineer (Data) programme.
