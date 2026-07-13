"""r5_paths.py — single source of truth for external data locations.

Migration (2026-07): race data moved OUT of the project into a shared folder.

    RacingData/files 2   → read-only DRF input          (R5_DATA_DIR)
    RacingData/Results   → single-WRITER output + DB     (R5_RESULTS_DIR)

Invariant: THIS project is the sole writer of RacingData/Results (r5_results.db
and all generated artifacts). A separate consumer project opens the DB read-only;
we never coordinate with it — we just keep writing normally.

Override either root via environment variables or a repo-root .env file:
    R5_DATA_DIR=/path/to/RacingData
    R5_RESULTS_DIR=/path/to/RacingData/Results
Defaults point at ~/Documents/RacingData so a fresh checkout works with no config.

Note: CM/CM1 DBs (comparemodels/*.db) and the TXT_Files/ + database/ DRF
archives stay in-project and are intentionally NOT resolved here.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent   # Claude/ -> repo root


def _load_dotenv() -> None:
    """Populate os.environ from a repo-root .env (does not override real env vars)."""
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for raw in env.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

_DEFAULT_DATA = Path.home() / "Documents" / "RacingData"

DATA_ROOT    = Path(os.environ.get("R5_DATA_DIR", str(_DEFAULT_DATA))).expanduser()
RESULTS_DIR  = Path(os.environ.get("R5_RESULTS_DIR", str(DATA_ROOT / "Results"))).expanduser()

# Read-only input
DRF_DIR      = DATA_ROOT / "files 2"

# Single-writer output
R5_DB_PATH   = RESULTS_DIR / "r5_results.db"
BETA_PATH    = RESULTS_DIR / "logit_beta.json"
CHART_DIRS   = [RESULTS_DIR / "2026", RESULTS_DIR]

# Auxiliary DRF archives that did NOT migrate (stay in-project)
DRF_DIRS     = [DRF_DIR, REPO_ROOT / "TXT_Files", REPO_ROOT / "database"]


def find_chart_pdf_by_name(filename: str):
    """Locate a chart PDF by basename across CHART_DIRS. Returns Path or None."""
    for d in CHART_DIRS:
        cand = d / filename
        if cand.exists():
            return cand
    return None
