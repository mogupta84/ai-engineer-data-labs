"""Shared by the Lab 9 documents scripts: the settings, the files, the judged questions and the scoring."""
import json           # read the judged questions
import math           # the log in nDCG
import os             # read the addresses and keys from environment variables
import pathlib        # find the course files
import sys            # stop with a readable message when a setting is missing

from azure.identity import AzureCliCredential, VisualStudioCodeCredential, ChainedTokenCredential

HERE = pathlib.Path(__file__).parent
DATA = pathlib.Path(os.environ.get("COURSE_DATA", HERE.parent / "data"))   # the course repository's data folder
RAW = DATA / "raw"                              # the 7 FreshCart files from Labs 1 to 4
GOLDEN = DATA / "golden"                        # the judged questions from Labs 3 and 4
READ = HERE / "read"                            # what D1 writes: one text file per document

# What each file is, for the labels on every piece of text. The 2022 policy is the old one on purpose.
LABELS = {
    "refund_policy_v3_2024.pdf": {"doc_type": "policy", "version": "3.0", "effective_date": "2024-04-01", "current": True},
    "refund_policy_v2_2022.pdf": {"doc_type": "policy", "version": "2.0", "effective_date": "2022-06-15", "current": False},
    "partner_agreement_extract.pdf": {"doc_type": "contract", "version": "", "effective_date": "2023-01-01", "current": True},
    "support_sla_matrix.docx": {"doc_type": "sla", "version": "", "effective_date": "2024-04-01", "current": True},
    "support_escalation_sop_scanned.pdf": {"doc_type": "sop", "version": "5", "effective_date": "2024-03-01", "current": True},
    "support_qbr_q1_2024.pptx": {"doc_type": "report", "version": "", "effective_date": "2024-04-12", "current": True},
    "refund_claims_march_2024.xlsx": {"doc_type": "register", "version": "", "effective_date": "2024-04-01", "current": True},
}
INDEX = "freshcart-docs-lab9"                    # the shared search index the trainer builds in D2

# The settings live in a file named .env in this folder, one NAME=value per line, as in Lab 8. A value set in the
# terminal wins.
ENV_FILE = HERE / ".env"
if not ENV_FILE.exists() and ENV_FILE.with_name(".env.txt").exists():
    sys.exit("Your settings file is called .env.txt; rename it to .env (Windows added .txt when saving it).")
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        name, _, value = line.partition("=")
        if name.strip() and not name.strip().startswith("#") and value.strip():
            os.environ.setdefault(name.strip(), value.strip().strip('"'))

# Sign in as you, with no key, as in Lab 8: az login, or VS Code's Sign in to Azure. The first that works wins.
SIGN_IN = ChainedTokenCredential(AzureCliCredential(), VisualStudioCodeCredential())


def setting(name):
    """One setting from the environment, or a clear message saying how to set it."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Add {name}=<the value from your trainer> to the .env file in this folder.")
    return value


def golden(name):
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def grade(rules, piece):
    """The judged grade of one piece of text: the best rule whose file matches and whose text it contains."""
    text = " ".join(piece["content"].lower().split())          # line breaks inside a sentence do not count
    return max([r["grade"] for r in rules
                if r["source"] == piece["file"] and " ".join(r["contains"].lower().split()) in text] or [0])


def ndcg_at_10(rules, ranked, every_piece):
    """How good the top 10 are, from 0 to 1: 1 means the best pieces in the index came first. As in Lab 3."""
    gains = [grade(rules, p) for p in ranked[:10]]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    best = sorted([grade(rules, p) for p in every_piece], reverse=True)[:10]
    ideal = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(best))
    return dcg / ideal if ideal else None
