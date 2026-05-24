#!/usr/bin/env python3
"""
R5 Web Frontend — Flask server wrapping the R5 handicapping engine.

Run:  python app.py
Then: open http://localhost:5050
"""
import io
import re
import sqlite3
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE       = Path(__file__).parent
CLAUDE_DIR = HERE.parent / "Claude"
WORK_BASE  = Path(tempfile.gettempdir()) / "r5_web_jobs"
WORK_BASE.mkdir(exist_ok=True)

# Use the project-level venv python (has requests + reportlab) for subprocesses.
# Falls back to current interpreter if not found.
_PROJECT_PYTHON = HERE.parent / "venv" / "bin" / "python3"
R5_PYTHON = str(_PROJECT_PYTHON) if _PROJECT_PYTHON.exists() else sys.executable

# ── CompareModels (optional — same project, direct import) ────────────────────
try:
    sys.path.insert(0, str(HERE.parent))
    from comparemodels.drf_to_csv import convert_drf_to_csv as _cm_convert
    from comparemodels.comparemodels_engine import score_card as _cm_score
    CM_AVAILABLE = True
except ImportError:
    CM_AVAILABLE = False

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

ALLOWED_EXT = {".drf", ".zip"}

# In-process job store (cleared on restart — fine for local use)
_jobs: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)


def extract_drfs(zip_path: Path, dest: Path) -> list[Path]:
    drfs = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.upper().endswith(".DRF"):
                out = zf.extract(member, dest)
                drfs.append(Path(out))
    return drfs


def run_r5(drf_path: Path, work_dir: Path, want_pdf: bool, want_scout: bool = False) -> tuple[str, Path | None, str]:
    """Returns (stdout_text, pdf_path_or_None, warning_string)."""
    cmd = [R5_PYTHON, str(CLAUDE_DIR / "run_r5.py"), str(drf_path)]
    if want_scout:
        cmd.append("--auto-scout")
    if want_pdf:
        cmd.append("--pdf")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(work_dir),
        timeout=180,
    )

    text = result.stdout or ""
    if result.returncode != 0 and not text.strip():
        raise RuntimeError(result.stderr[:600] or "Analysis produced no output")

    # Partial failure: engine produced output but still exited non-zero.
    # Surface stderr as a warning so it isn't silently swallowed.
    warning = ""
    if result.returncode != 0 and result.stderr.strip():
        first_line = result.stderr.strip().splitlines()[-1][:200]
        warning = f"Engine error after analysis (PDF may be missing): {first_line}"

    pdf_path = None
    if want_pdf:
        candidate = work_dir / (drf_path.stem + "_R5.pdf")
        if candidate.exists():
            pdf_path = candidate

    return text, pdf_path, warning


def run_cm(drf_path: Path, work_dir: Path) -> dict:
    """Run CompareModels against a DRF. Returns {race_num: cm_data_dict}."""
    if not CM_AVAILABLE:
        raise RuntimeError("comparemodels package not found")
    csv_path = work_dir / (drf_path.stem + "_cm.csv")
    _cm_convert(str(drf_path), str(csv_path))
    results = _cm_score(str(csv_path))

    cm_by_race: dict = {}
    for race_num, r in results.items():
        horses = r.get("ranked_horses", [])
        if not horses:
            continue
        top = horses[0]
        cm_by_race[race_num] = {
            "pgm":              top["pgm"],
            "name":             top["name"],
            "composite":        top["composite"],
            "consensus":        top["consensus_count"],
            "dominant":         top["is_dominant"],
            "early_pace_leader": r.get("early_pace_leader"),
            "late_pace_leader":  r.get("late_pace_leader"),
        }
    return cm_by_race


# ── Output parser ─────────────────────────────────────────────────────────────
#
# The R5 text output is fixed-width. Column positions come from run_r5.py's
# print statement:
#   f"{pgm:<4} {name:<22} {ml:>5}  {s4:>22}  {ws:>5}  {tr:>4}  {fc:>5}
#      {vp:>5}  {ped:>4}  {tj:>4}  {pce:>4}  {val:>4}  {comp:>5.2f}  {tier}"
#
# Cumulative start positions (0-indexed):
#   pgm   0   name  5   ml   28   s4   35   ws   59   tr   66
#   fc   72   vp   79   ped  86   tj   92   pce  98   val 104
#   comp 110  tier 117

_HORSE_COLS = {
    "pgm":  (0,   4),
    "name": (5,   27),
    "ml":   (28,  33),
    "s4":   (35,  57),
    "ws4":  (59,  64),
    "tr":   (66,  70),
    "fci":  (72,  77),
    "vpar": (79,  84),
    "ped":  (86,  90),
    "tj":   (92,  96),
    "pce":  (98,  102),
    "val":  (104, 108),
    "comp": (110, 115),
    "tier": (117, None),
}

_RACE_HDR_RE = re.compile(
    r'🏇\s+R5[^—]*—\s+(\w+)\s+Race\s+(\d+)\s*\|'
    r'\s*(\d+)\s*\|\s*([\d.]+f)\s+([DT])\s*\|\s*Purse\s*\$([\d,]+)\s*\|\s*(.+)',
)
_TOP_PICK_RE = re.compile(
    r'🏆\s+TOP WIN PICK:\s+#(\S+)\s+(.+?)\s+\[([^\]]+)\]\s+\|\s+Composite\s+(\S+)\s+\|\s+(\S+)'
)
_VAL_ALT_RE = re.compile(
    r'💰\s+VALUE ALT:\s+#(\S+)\s+(.+?)\s+\[([^\]]+)\]\s+\|\s+Composite\s+(\S+)\s+\|\s+(\S+)'
)
_TIGHT_CLUSTER_RE = re.compile(
    r'⚠[️️]?\s*TIGHT CLUSTER[^=\n]*(?:spread\s*=\s*([\d.]+)\s*pts?)?',
    re.IGNORECASE,
)
_SCRATCH_NOTICE_RE = re.compile(
    r'SCRATCH NOTICE[^:]*:\s+#(\S+)\s+(.+?)\s+\(pre-scratch Rank\s+(\d+)\)',
    re.IGNORECASE,
)
_REVISED_PICK_RE = re.compile(
    r'REVISED TOP PICK:\s+#?(\S+)\s+(.+?)\s+Composite\s+([\d.]+)',
    re.IGNORECASE,)


def parse_output(text: str) -> list[dict]:
    # Pre-collect scratch notices from full text keyed by race number.
    # Notices appear BETWEEN race blocks (after Race N exotics, before Race N+1
    # header), so they end up in the wrong block if parsed inside _parse_race_block.
    scratch_map: dict = {}
    lines_all = text.splitlines()
    for i, line in enumerate(lines_all):
        ms = _SCRATCH_NOTICE_RE.search(line)
        if ms:
            race_m = re.search(r'\bR(\d+)\b', line)
            race_num = int(race_m.group(1)) if race_m else None
            scratch = {
                "pgm":      ms.group(1),
                "name":     ms.group(2).strip(),
                "pre_rank": ms.group(3),
            }
            for j in range(i + 1, min(i + 4, len(lines_all))):
                mr = _REVISED_PICK_RE.search(lines_all[j])
                if mr:
                    scratch["revised_pgm"]  = mr.group(1)
                    scratch["revised_name"] = mr.group(2).strip()
                    scratch["revised_comp"] = mr.group(3)
                    break
            if race_num is not None:
                scratch_map.setdefault(race_num, []).append(scratch)

    # Split into race blocks at each ====...==== line that precedes a 🏇 header
    blocks = re.split(r'(?=={60,}\n\s*🏇)', text)
    races = []
    for block in blocks:
        if "🏇" not in block:
            continue
        race = _parse_race_block(block)
        if race:
            rn = race.get("race_num")
            if rn and rn in scratch_map:
                race["scratches"] = scratch_map[rn]
            races.append(race)
    return races


def _parse_race_block(block: str) -> dict | None:
    race: dict = {"raw": block, "horses": [], "exotics": {}}
    lines = block.splitlines()

    # ── Header ──────────────────────────────────────────────────────────────
    for line in lines:
        m = _RACE_HDR_RE.search(line)
        if m:
            race.update({
                "track":     m.group(1),
                "race_num":  int(m.group(2)),
                "date":      m.group(3),
                "distance":  m.group(4),
                "surface":   "Dirt" if m.group(5) == "D" else "Turf",
                "purse":     m.group(6),
                "pace_type": m.group(7).strip(),
            })
            break

    if "race_num" not in race:
        return None

    # ── Horses ──────────────────────────────────────────────────────────────
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") and "Horse" in stripped and "ML" in stripped:
            in_table = True
            continue
        if in_table:
            if not stripped or stripped.startswith("="):
                in_table = False
                continue
            if stripped.startswith("-"):
                continue
            h = _parse_horse_row(line)
            if h:
                race["horses"].append(h)

    # ── Top pick ────────────────────────────────────────────────────────────
    for line in lines:
        m = _TOP_PICK_RE.search(line)
        if m:
            race["top_pick"] = {
                "pgm": m.group(1), "name": m.group(2).strip(),
                "ml": m.group(3), "composite": m.group(4), "tier": m.group(5),
            }
            break

    # ── Value alt ───────────────────────────────────────────────────────────
    for line in lines:
        m = _VAL_ALT_RE.search(line)
        if m:
            race["value_alt"] = {
                "pgm": m.group(1), "name": m.group(2).strip(),
                "ml": m.group(3), "composite": m.group(4), "tier": m.group(5),
            }
            break

    # ── Exotics ─────────────────────────────────────────────────────────────
    for line in lines:
        for label, key in [("WIN:", "win"), ("EXACTA:", "exacta"),
                            ("TRIFECTA:", "trifecta"), ("SUPERFECTA:", "superfecta")]:
            if label in line:
                race["exotics"][key] = line.split(label, 1)[1].strip()

    # ── Tight cluster ────────────────────────────────────────────────────────
    for line in lines:
        m = _TIGHT_CLUSTER_RE.search(line)
        if m:
            race["tight_cluster"] = True
            race["tight_cluster_spread"] = m.group(1)  # e.g. "0.95", or None
            break

    return race


def _parse_horse_row(line: str) -> dict | None:
    if len(line) < 50:
        return None
    pgm = line[0:4].strip()
    if not pgm or not re.match(r'^[0-9A-Za-z]+$', pgm):
        return None

    def col(start, end):
        s = line[start:end] if end and end <= len(line) else line[start:]
        return s.strip()

    name = col(5, 27)
    if not name:
        return None

    s4_raw = col(35, 57)
    speeds = s4_raw.split() if s4_raw else []

    return {
        "pgm":   pgm,
        "name":  name,
        "ml":    col(28, 33),
        "speeds": speeds,
        "ws4":   col(59, 64),
        "trend": col(66, 70),
        "fci":   col(72, 77),
        "vpar":  col(79, 84),
        "ped":   col(86, 90),
        "tj":    col(92, 96),
        "pce":   col(98, 102),
        "val":   col(104, 108),
        "comp":  col(110, 115),
        "tier":  col(117, None),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({"cm_available": CM_AVAILABLE})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files provided"}), 400

    want_pdf   = request.form.get("pdf",   "false").lower() == "true"
    want_scout = request.form.get("scout", "false").lower() == "true"
    want_cm    = request.form.get("cm",    "false").lower() == "true" and CM_AVAILABLE

    job_id  = str(uuid.uuid4())
    work_dir = WORK_BASE / job_id
    work_dir.mkdir()

    all_text  = ""
    all_races: list = []
    pdf_paths: list = []
    errors:    list = []

    for f in files:
        fname = safe_filename(f.filename)
        ext   = Path(fname).suffix.lower()
        if ext not in ALLOWED_EXT:
            errors.append(f"{fname}: unsupported type (use .drf or .zip)")
            continue

        save_path = work_dir / fname
        f.save(str(save_path))

        drfs = []
        if ext == ".zip":
            drfs = extract_drfs(save_path, work_dir)
            if not drfs:
                errors.append(f"{fname}: no .DRF files found inside zip")
                continue
        else:
            drfs = [save_path]

        for drf in drfs:
            try:
                text, pdf_path, warning = run_r5(drf, work_dir, want_pdf, want_scout)
                drf_races = parse_output(text)

                # Merge CompareModels picks into each race
                if want_cm:
                    try:
                        cm_data = run_cm(drf, work_dir)
                        for race in drf_races:
                            rn = race.get("race_num")
                            if rn and rn in cm_data:
                                race["cm"] = cm_data[rn]
                    except Exception as cm_exc:
                        errors.append(f"{drf.name} (CM): {cm_exc}")

                all_text += text + "\n"
                all_races.extend(drf_races)
                if pdf_path:
                    pdf_paths.append(str(pdf_path))
                if warning:
                    errors.append(f"{drf.name}: {warning}")
            except Exception as exc:
                errors.append(f"{drf.name}: {exc}")

    _jobs[job_id] = {
        "text":      all_text,
        "races":     all_races,
        "pdf_paths": pdf_paths,
        "work_dir":  str(work_dir),
    }

    return jsonify({
        "job_id":        job_id,
        "races":         all_races,
        "text":          all_text,
        "pdf_available": len(pdf_paths) > 0,
        "cm_run":        want_cm,
        "errors":        errors,
    })


@app.route("/api/download/pdf/<job_id>")
def download_pdf(job_id):
    job = _jobs.get(job_id)
    if not job or not job.get("pdf_paths"):
        abort(404)
    path = job["pdf_paths"][0]
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=Path(path).name,
    )


@app.route("/api/download/txt/<job_id>")
def download_txt(job_id):
    job = _jobs.get(job_id)
    if not job:
        abort(404)
    buf = io.BytesIO(job["text"].encode("utf-8"))
    return send_file(
        buf,
        mimetype="text/plain",
        as_attachment=True,
        download_name="r5_analysis.txt",
    )


@app.route("/api/analytics")
def analytics():
    db_path = HERE.parent / "results" / "r5_results.db"
    if not db_path.exists():
        return jsonify({"error": "no_db"})

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # ── tier_hits ─────────────────────────────────────────────────────────────
    tier_order = ["HIGH", "SOLID", "FAIR", "SPEC"]
    rows = conn.execute("""
        SELECT p.tier, COUNT(*) AS races, SUM(p.won) AS wins
        FROM picks p
        JOIN races r ON p.race_id = r.id
        WHERE p.model_rank = 1
          AND r.result_fetched = 1
          AND p.finish_pos != -1
        GROUP BY p.tier
    """).fetchall()
    tier_map = {r["tier"]: dict(r) for r in rows}
    tier_hits = []
    for t in tier_order:
        if t in tier_map:
            d = tier_map[t]
            races = d["races"]
            wins  = d["wins"] or 0
            tier_hits.append({
                "tier":     t,
                "races":    races,
                "wins":     wins,
                "win_pct":  round(wins / races * 100, 1) if races else 0,
            })

    # ── val_roi ───────────────────────────────────────────────────────────────
    val_roi = []
    threshold = 6.0
    while threshold <= 10.01:
        row = conn.execute("""
            SELECT COUNT(*) AS plays,
                   SUM(p.won) AS wins,
                   AVG(CASE WHEN p.won = 1 THEN p.sp_odds ELSE NULL END) AS avg_sp
            FROM picks p
            JOIN races r ON p.race_id = r.id
            WHERE p.val_n >= ?
              AND p.model_rank <= 5
              AND r.result_fetched = 1
              AND p.finish_pos != -1
        """, (threshold,)).fetchone()
        plays  = row["plays"] or 0
        wins   = row["wins"]  or 0
        avg_sp = row["avg_sp"] or 0.0
        roi    = round((wins * avg_sp - plays) / plays * 100, 1) if plays else None
        val_roi.append({
            "threshold": round(threshold, 1),
            "plays":     plays,
            "wins":      wins,
            "win_pct":   round(wins / plays * 100, 1) if plays else 0,
            "roi":       roi,
        })
        threshold += 0.5

    # ── score_dist ────────────────────────────────────────────────────────────
    buckets_def = [("4-5", 4, 5), ("5-6", 5, 6), ("6-7", 6, 7),
                   ("7-8", 7, 8), ("8-9", 8, 9), ("9-10", 9, 10)]
    score_dist = []
    for label, lo, hi in buckets_def:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt, SUM(won) AS wins
            FROM picks
            WHERE finish_pos > 0
              AND comp IS NOT NULL
              AND CAST(comp AS REAL) >= ?
              AND CAST(comp AS REAL) < ?
        """, (lo, hi)).fetchone()
        cnt  = row["cnt"]  or 0
        wins = row["wins"] or 0
        score_dist.append({
            "bucket":   label,
            "count":    cnt,
            "wins":     wins,
            "win_pct":  round(wins / cnt * 100, 1) if cnt else 0,
        })

    # ── track_splits ──────────────────────────────────────────────────────────
    rows = conn.execute("""
        SELECT r.track,
               UPPER(COALESCE(r.surface, 'UNKNOWN')) AS surface,
               COUNT(DISTINCT r.id) AS races,
               SUM(CASE WHEN p.model_rank = 1 AND p.won = 1 THEN 1 ELSE 0 END) AS top_wins,
               COUNT(DISTINCT CASE WHEN p.model_rank <= 3 AND p.won = 1 THEN r.id ELSE NULL END) AS top3
        FROM races r
        JOIN picks p ON p.race_id = r.id
        WHERE r.result_fetched = 1
          AND p.finish_pos != -1
        GROUP BY r.track, UPPER(COALESCE(r.surface, 'UNKNOWN'))
        ORDER BY races DESC, r.track
    """).fetchall()

    track_splits = []
    for row in rows:
        races     = row["races"]
        top_wins  = row["top_wins"] or 0
        top3      = row["top3"]     or 0
        track_splits.append({
            "track":    row["track"],
            "surface":  row["surface"],
            "races":    races,
            "top_wins": top_wins,
            "top_pct":  round(top_wins / races * 100, 1) if races else 0,
            "top3":     top3,
            "top3_pct": round(top3 / races * 100, 1) if races else 0,
        })

    conn.close()
    return jsonify({
        "tier_hits":    tier_hits,
        "val_roi":      val_roi,
        "score_dist":   score_dist,
        "track_splits": track_splits,
    })


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="R5 Web Frontend")
    ap.add_argument("--host",  default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    ap.add_argument("--port",  type=int, default=5050, help="Port (default: 5050)")
    ap.add_argument("--debug", action="store_true",  help="Enable Flask debug mode")
    args = ap.parse_args()

    print(f"\n🏇  R5 Web Frontend")
    print(f"   Claude dir : {CLAUDE_DIR}")
    print(f"   Listening  : http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=args.debug)
