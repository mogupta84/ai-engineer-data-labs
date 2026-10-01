"""
Settings for the two lab tracks.

  Command-line track  runs everything on your machine. No keys, no cloud.
  Azure track         swaps in Azure services. Needs lab.env from the trainer.

Every lab script calls setup_track() first. It loads lab.env (if present) into
the environment and decides which track to run:

    python labs/lab03_hybrid.py            -> command-line track
    python labs/lab03_hybrid.py --azure    -> Azure track
"""
from __future__ import annotations
import os, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "lab.env"

AZURE_KEYS = {
    "openai": ["AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY",
               "AZURE_OPENAI_CHAT_DEPLOYMENT", "AZURE_OPENAI_EMBED_DEPLOYMENT"],
    "search": ["AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_KEY"],
    "postgres": ["PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"],
    "ai": ["AZURE_AI_ENDPOINT", "AZURE_AI_KEY"],
    "insights": ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
}


def load_env(path: pathlib.Path = ENV_FILE) -> dict:
    """Reads KEY=VALUE lines. Values already set in the shell win, so a student
    can override one setting without editing the shared file."""
    loaded = {}
    if not path.exists():
        return loaded
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def student_id() -> str:
    """Keeps each student's tables and documents apart on shared services.
    Set it once per machine:  setx STUDENT_ID yourname   (then open a new window)."""
    sid = os.getenv("STUDENT_ID") or os.getenv("USERNAME") or os.getenv("USER") or "student"
    return "".join(ch for ch in sid.lower() if ch.isalnum())[:20] or "student"


GENERIC_USERS = {"admin", "administrator", "user", "student", "labuser", "azureuser", "trainee"}


def require(*groups: str):
    missing = [k for g in groups for k in AZURE_KEYS[g] if not os.getenv(k)]
    if missing:
        raise SystemExit(
            "The Azure track needs these settings, but they are empty: " + ", ".join(missing) +
            f"\nCopy the lab.env file from your trainer to: {ENV_FILE}")


def setup_track(title: str, needs=("openai",)) -> bool:
    """Call at the top of every lab script. Returns True for the Azure track."""
    load_env()
    azure = "--azure" in sys.argv[1:]
    track = "Azure track" if azure else "command-line track (offline, no keys)"
    print(f"{title}  |  {track}")
    if azure:
        require(*needs)
        if not os.getenv("STUDENT_ID") and student_id() in GENERIC_USERS:
            raise SystemExit(
                f"Your Windows user name is '{student_id()}', which every lab machine may share.\n"
                "Pick a student id so your work does not overwrite anyone else's, then run:\n"
                "    setx STUDENT_ID yourname\n    set STUDENT_ID=yourname")
        os.environ["FRESHCART_EMBEDDER"] = "azure"
        print(f"student id: {student_id()}")
    elif os.getenv("FRESHCART_EMBEDDER", "").lower() == "azure":
        os.environ["FRESHCART_EMBEDDER"] = "offline"
    return azure


def arg_value(name: str, default=None):
    """Tiny argument reader: --name value."""
    argv = sys.argv[1:]
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default
