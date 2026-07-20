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
# Handle both Unix (venv/bin/python3) and Windows (venv\Scripts\python.exe) layouts.
import sys as _sys
_VENV_ROOT = HERE.parent / "venv"
_PROJECT_PYTHON = (
    _VENV_ROOT / "Scripts" / "python.exe"   # Windows
    if (_VENV_ROOT / "Scripts" / "python.exe").exists()
    else _VENV_ROOT / "bin" / "python3"      # macOS / Linux
)
R5_PYTHON = str(_PROJECT_PYTHON) if _PROJECT_PYTHON.exists() else _sys.executable

# ── CompareModels (optional — same project, direct import) ────────────────────
try:
    sys.path.insert(0, str(HERE.parent))
    from comparemodels.comparemodels_engine import score_card as _cm_score
    from comparemodels.comparemodels_tracker import (
        log_card_with_ml as _cm_log_card,
        pull_results     as _cm_pull_results,
        finalize         as _cm_finalize,
    )
    CM_AVAILABLE = True
except ImportError:
    CM_AVAILABLE = False

# ── BRIS summary docx (optional — needs python-docx; separate guard so a
#    missing docx dependency never disables CM scoring/logging) ───────────────
try:
    from comparemodels.bris_summary_docx import generate_bris_summary as _bris_summary
    BRIS_DOCX_AVAILABLE = True
except ImportError:
    BRIS_DOCX_AVAILABLE = False

# ── CM1 (optional — separate guard so a CM1 failure never blocks CM) ──────────
try:
    sys.path.insert(0, str(HERE.parent))
    from comparemodels.cm1_tracker import log_card as _cm1_log_card
    CM1_AVAILABLE = True
except ImportError:
    CM1_AVAILABLE = False

# ── Data locations: single source of truth (Claude/r5_paths.py) ───────────────
sys.path.insert(0, str(HERE.parent / "Claude"))
from r5_paths import R5_DB_PATH  # noqa: E402

# ── Lazy-load R5 modules (avoid circular imports) ──────────────────────────────
import importlib.util as _ilu

def _load_claude(name):
    path = HERE.parent / "Claude" / f"{name}.py"
    spec = _ilu.spec_from_file_location(name, path)
    mod  = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

ALLOWED_EXT = {".drf", ".zip"}

# In-process job store (cleared on restart — fine for local use)
_jobs: dict = {}


# ── Global error handler — always return JSON, never HTML ─────────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return jsonify({
        "error": str(e),
        "type":  type(e).__name__,
        "trace": traceback.format_exc().splitlines()[-3:],
    }), 500


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


def run_r5(drf_path: Path, work_dir: Path, want_pdf: bool, want_scout: bool = False,
           log_to_db: bool = False, want_wet: bool = False,
           year_override: int | None = None) -> tuple[str, Path | None, str]:
    """Returns (stdout_text, pdf_path_or_None, warning_string)."""
    cmd = [R5_PYTHON, str(CLAUDE_DIR / "run_r5.py"), str(drf_path)]
    if want_scout:
        cmd.append("--auto-scout")
    if want_pdf:
        cmd.append("--pdf")
    if log_to_db:
        cmd.append("--track")
    if want_wet:
        cmd.append("--wet")
    if year_override:
        cmd += ["--year", str(year_override)]
        cmd.append("--backtest")  # non-current-year cards are always backtest

    # PYTHONUTF8=1 forces UTF-8 stdout/stderr on Windows (avoids cp1252 emoji crash)
    import os as _os
    _env = {**_os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(work_dir),
        timeout=180,
        env=_env,
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
    results = _cm_score(str(drf_path))

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
# The R5 text output is fixed-width. Column positions come from
# r5_parser_v2.report()'s print statement (Session 2 Task 6 format —
# tier ladder retired, P(win)/fair/edge appended):
#   f"{pgm:<4} {name:<22} {ml:>5}  {s4:>22}  {ws:>5}  {tr:>4}  {fc:>5}
#      {vp:>5}  {ped:>4}  {tj:>4}  {pce:>4}  {bdn:>4}  {ppn:>4}  {val:>4}
#      {comp:>5.2f}  {pw:>6}  {fo:>6}  {ed:>6}" + flag tags

# Session 3A layout: name widened to 29 ("Name (E/P)" carries BRIS run
# style), Quirin "Q" column added after Pce. Positions verified empirically.
_HORSE_COLS = {
    "pgm":   (0,   4),
    "name":  (5,   34),
    "ml":    (35,  40),
    "s4":    (42,  64),
    "ws4":   (66,  71),
    "tr":    (73,  77),
    "fci":   (79,  84),
    "vpar":  (86,  91),
    "ped":   (93,  97),
    "tj":    (99,  103),
    "pce":   (105, 109),
    "q":     (111, 113),
    "bdn":   (115, 119),
    "ppn":   (121, 125),
    "val":   (127, 131),
    "comp":  (133, 138),
    "p_win": (140, 146),
    "fair":  (148, 154),
    "edge":  (156, 162),
}

_RACE_HDR_RE = re.compile(
    r'🏇\s+R5[^—]*—\s+(\w+)\s+Race\s+(\d+)\s*\|'
    # surface is a single letter, any case — 'D', 'T', 't' (inner turf), 'A' (AW)
    r'\s*(\d+)\s*\|\s*([\d.]+f)\s+([A-Za-z])\s*\|\s*Purse\s*\$([\d,]+)\s*\|\s*(.+)',
)
_TOP_PICK_RE = re.compile(
    r'🏆\s+TOP WIN PICK:\s+#(\S+)\s+(.+?)\s+\[([^\]]+)\]\s+\|\s+Composite\s+(\S+)(.*)'
)
_VAL_ALT_RE = re.compile(
    r'💰\s+VALUE ALT:\s+#(\S+)\s+(.+?)\s+\[([^\]]+)\]\s+\|\s+Composite\s+(\S+)(.*)'
)
# Session 2 race header: "R5 | top-3 cum P(win) 47% | spread(r1−r3) 0.85 DEFAULT"
_PWIN_HDR_RE = re.compile(
    r'R5\s*\|\s*top-3 cum P\(win\)\s*(\d+)%'
    r'(?:\s*\|\s*spread\(r1.r3\)\s*([\d.]+)\s*(TIGHT|STANDOUT|DEFAULT))?'
)
_PWIN_TAIL_RE = re.compile(r'P\(win\)\s*(\d+)%(?:.*?fair\s*([\d.]+-1))?'
                           r'(?:.*?edge\s*([+\-]\d+)%)?')
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
                "surface":   ("Dirt" if m.group(5).upper() == "D"
                              else "AW" if m.group(5).upper() == "A" else "Turf"),
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

    # ── P(win) race header (Session 2) ──────────────────────────────────────
    for line in lines:
        m = _PWIN_HDR_RE.search(line)
        if m:
            race["top3_cum_pwin"] = int(m.group(1))
            if m.group(2):
                race["spread_r1_r3"] = float(m.group(2))
                race["race_shape"]   = m.group(3)
            break

    def _pwin_tail(tail):
        mt = _PWIN_TAIL_RE.search(tail or "")
        if not mt:
            return {}
        return {"p_win": mt.group(1), "fair": mt.group(2),
                "edge": mt.group(3),
                "overlay": "OVERLAY" in (tail or "")}

    # ── Top pick ────────────────────────────────────────────────────────────
    for line in lines:
        m = _TOP_PICK_RE.search(line)
        if m:
            race["top_pick"] = {
                "pgm": m.group(1), "name": m.group(2).strip(),
                "ml": m.group(3), "composite": m.group(4),
                **_pwin_tail(m.group(5)),
            }
            break

    # ── Value alt ───────────────────────────────────────────────────────────
    for line in lines:
        m = _VAL_ALT_RE.search(line)
        if m:
            race["value_alt"] = {
                "pgm": m.group(1), "name": m.group(2).strip(),
                "ml": m.group(3), "composite": m.group(4),
                **_pwin_tail(m.group(5)),
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

    # ── Wet-form lines (Session 3A Task 4 — emitted only with --wet) ────────
    wet = {}
    for line in lines:
        mw = re.search(r"#(\S+)\s+(.+?):\s+(WET .+)$", line)
        if mw and ("WET" in line):
            wet[mw.group(1)] = mw.group(3).strip()
    if wet:
        race["wet_form"] = wet
        for h in race["horses"]:
            if h["pgm"] in wet:
                h["wet"] = wet[h["pgm"]]

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

    name = col(5, 34)
    if not name:
        return None

    s4_raw = col(42, 64)
    speeds = s4_raw.split() if s4_raw else []

    # name cell may carry the BRIS run style: "DI NATALE (E/P)"
    mstyle = re.search(r"\((E|E/P|P|S)\)\s*$", name)
    run_style = mstyle.group(1) if mstyle else None
    if mstyle:
        name = name[:mstyle.start()].strip()

    tail = line[162:] if len(line) > 162 else ""
    mlay = re.search(r"\[LAYOFF (\d+)\+\]", tail)
    return {
        "pgm":   pgm,
        "name":  name,
        "run_style": run_style,
        "ml":    col(35, 40),
        "speeds": speeds,
        "ws4":   col(66, 71),
        "trend": col(73, 77),
        "fci":   col(79, 84),
        "vpar":  col(86, 91),
        "ped":   col(93, 97),
        "tj":    col(99, 103),
        "pce":   col(105, 109),
        "q":     col(111, 113),
        "bdn":   col(115, 119),
        "ppn":   col(121, 125),
        "val":   col(127, 131),
        "comp":  col(133, 138),
        "p_win": col(140, 146),
        "fair":  col(148, 154),
        "edge":  col(156, 162),
        "overlay":   "OVERLAY" in tail,
        "val_watch": "VAL WATCH" in tail,
        "debut":     "[DEBUT]" in tail,
        "also_elig": "[AE]" in tail,
        "layoff":    mlay.group(1) + "+" if mlay else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    db_path = R5_DB_PATH
    return jsonify({
        "cm_available": CM_AVAILABLE,
        "db_available":  db_path.exists(),
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files provided"}), 400

    want_pdf    = request.form.get("pdf",      "false").lower() == "true"
    want_scout  = request.form.get("scout",   "false").lower() == "true"
    want_cm     = request.form.get("cm",      "false").lower() == "true" and CM_AVAILABLE
    log_to_db   = request.form.get("log_db",  "false").lower() == "true"
    want_wet    = request.form.get("wet",     "false").lower() == "true"
    _yr_raw     = request.form.get("year_override", "").strip()
    year_override = int(_yr_raw) if _yr_raw.isdigit() and len(_yr_raw) == 4 else None

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
                text, pdf_path, warning = run_r5(drf, work_dir, want_pdf, want_scout, log_to_db, want_wet, year_override)
                drf_races = parse_output(text)

                # Extract track/date from DRF stem for DB ops
                drf_stem  = drf.stem.upper()            # e.g. SAX0525
                drf_track = drf_stem[:3]
                drf_mmdd  = drf_stem[3:7]
                from datetime import date as _date_cls
                drf_date  = str(_date_cls.today().year) + drf_mmdd

                # Merge CompareModels picks into each race + optionally log to CM DB
                if want_cm:
                    try:
                        cm_score_data = run_cm(drf, work_dir)
                        for race in drf_races:
                            rn = race.get("race_num")
                            if rn and rn in cm_score_data:
                                race["cm"] = cm_score_data[rn]
                        # Log CM picks to DB if requested
                        if log_to_db and CM_AVAILABLE:
                            try:
                                # Build ML map from parsed R5 races
                                ml_map = {}
                                for race in drf_races:
                                    rn = race.get("race_num")
                                    for h in race.get("horses", []):
                                        try:
                                            ml_map[(str(rn), str(h["pgm"]))] = float(h.get("ml") or 0)
                                        except (ValueError, TypeError):
                                            pass
                                # Get raw CM score dict — direct DRF read
                                from comparemodels.comparemodels_engine import score_card as _sc
                                cm_raw = _sc(str(drf))
                                _cm_log_card(cm_raw, drf_track, drf_date, ml_map)
                            except Exception as cm_log_exc:
                                errors.append(f"{drf.name} (CM log): {cm_log_exc}")
                    except Exception as cm_exc:
                        errors.append(f"{drf.name} (CM): {cm_exc}")

                # Log CM1 picks (third model) whenever picks are logged to DB.
                # Independent of the CM toggle; flags are deterministic from the DRF.
                if log_to_db and CM1_AVAILABLE:
                    try:
                        _cm1_log_card(str(drf),
                                      year=year_override,
                                      is_backtest=bool(year_override))
                    except Exception as cm1_exc:
                        errors.append(f"{drf.name} (CM1 log): {cm1_exc}")

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
        "logged_to_db":  log_to_db,
        "wet_track":     want_wet,
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


@app.route("/api/results", methods=["POST"])
def log_results():
    """
    POST /api/results
    Accepts a BRIS results PDF (or manual finish data) and runs the full
    post-race pipeline: parse → R5 log → R5 finalize → CM results → CM finalize.

    Form fields:
        track      (str)   e.g. "SAX"
        date       (str)   e.g. "20260525"
        pdf        (file)  BRIS chart PDF  (optional if manual provided)
        manual     (JSON)  {"1": "6,5,4,7", "2": "3,1,8,2", ...}  (optional)

    Returns JSON summary.
    """
    try:
        tracker    = _load_claude("r5_tracker")
        pdf_parser = _load_claude("r5_pdf_results")
    except Exception as e:
        return jsonify({"error": f"Server setup error: {e}. Check webapp venv dependencies."}), 500

    track    = (request.form.get("track") or "").strip().upper()
    date_str = (request.form.get("date")  or "").strip()

    if not track or not date_str:
        return jsonify({"error": "track and date are required"}), 400

    results_by_race: dict = {}   # {race_num (int): {"finish": [...], "sp": float|None}}
    parse_errors: list   = []

    # ── Parse PDF — prefer disk path, fall back to file upload ───────────────
    pdf_path_str = (request.form.get("pdf_path") or "").strip()
    pdf_file     = request.files.get("pdf")

    if pdf_path_str:
        # Server reads directly from local path — avoids browser upload I/O issues
        p = Path(pdf_path_str)
        if not p.exists():
            p = HERE.parent / pdf_path_str          # try relative to HorseRacing root
        if not p.exists():
            # Charts live under RacingData (r5_paths.CHART_DIRS) since 2026-07 —
            # resolve by basename so stale absolute paths still find the chart.
            try:
                _r5_paths = _load_claude("r5_paths")
                _cand = _r5_paths.find_chart_pdf_by_name(Path(pdf_path_str).name)
                if _cand:
                    p = _cand
            except Exception:
                pass
        if not p.exists() and len(track) == 3:
            # BRIS sometimes uses 2-char track code in filename (e.g. SA not SAX)
            p2 = Path(str(p).replace(track, track[:2], 1))
            if not p2.exists():
                p2 = Path(str(p).replace(track, track[:2]))  # all occurrences
            if p2.exists():
                p = p2
        if not p.exists():
            # PDF may be stored under a different year folder (e.g. user saved 2026 card to 2025/)
            import re as _re
            for alt_year in ("2025", "2026", "2027"):
                p_alt = Path(_re.sub(r'/\d{4}/', f'/{alt_year}/', str(p), count=1))
                if p_alt != p and p_alt.exists():
                    p = p_alt
                    break
        try:
            if not p.exists():
                raise FileNotFoundError(f"No such file or directory: '{p}'")
            parsed = pdf_parser.parse_results_pdf(str(p))
            results_by_race.update(parsed)
        except Exception as e:
            parse_errors.append(f"PDF parse error ({p.name}): {e}")

    elif pdf_file and pdf_file.filename:
        try:
            import tempfile
            pdf_bytes = pdf_file.read()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
            parsed = pdf_parser.parse_results_pdf(tmp_path)
            results_by_race.update(parsed)
            Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            parse_errors.append(f"PDF parse error: {e}")

    # ── Accept manual finish orders as override / supplement ─────────────────
    import json as _json
    manual_raw = request.form.get("manual", "")
    if manual_raw:
        try:
            manual = _json.loads(manual_raw)
            for rnum_str, finish_str in manual.items():
                rnum   = int(rnum_str)
                pgms   = [p.strip() for p in str(finish_str).split(",") if p.strip()]
                sp_raw = request.form.get(f"sp_{rnum_str}")
                sp     = float(sp_raw) if sp_raw else None
                results_by_race[rnum] = {"finish": pgms, "sp": sp}
        except Exception as e:
            parse_errors.append(f"Manual parse error: {e}")

    if not results_by_race:
        return jsonify({"error": "No results data — provide a PDF or manual finish orders",
                        "details": parse_errors}), 400

    # ── Log to R5 DB ──────────────────────────────────────────────────────────
    logged, skipped = 0, 0
    race_log = []
    for race_num in sorted(results_by_race):
        r      = results_by_race[race_num]
        finish = r["finish"]
        sp     = r.get("sp")
        if not finish:
            skipped += 1
            continue
        ok = tracker.apply_result(track, date_str, str(race_num), finish, sp)
        if ok:
            logged += 1
            winner = finish[0] if finish else "?"
            race_log.append({
                "race":   race_num,
                "finish": finish[:4],
                "winner": winner,
                "sp":     sp,
            })
        else:
            skipped += 1
            parse_errors.append(f"R{race_num}: no picks logged — run analysis with Log to DB first")

    # ── Finalize R5 ───────────────────────────────────────────────────────────
    try:
        tracker.finalize_card(track, date_str)
    except Exception as e:
        parse_errors.append(f"R5 finalize error: {e}")

    # ── CM results + finalize ─────────────────────────────────────────────────
    cm_done = False
    if CM_AVAILABLE:
        try:
            _cm_pull_results(track, date_str)
            _cm_finalize(track, date_str)
            cm_done = True
        except Exception as e:
            parse_errors.append(f"CM results error: {e}")

    return jsonify({
        "ok":        True,
        "track":     track,
        "date":      date_str,
        "logged":    logged,
        "skipped":   skipped,
        "cm_done":   cm_done,
        "race_log":  race_log,
        "errors":    parse_errors,
    })


@app.route("/api/report", methods=["POST"])
def generate_report():
    """Run r5_analyze.py and return the path of the generated Excel file."""
    import subprocess, json as _json

    analyze_script = CLAUDE_DIR / "r5_analyze.py"
    if not analyze_script.exists():
        return jsonify({"error": "r5_analyze.py not found"}), 500

    track_filter = (request.form.get("track") or "").strip().upper() or None
    cmd = [R5_PYTHON, str(analyze_script)]
    if track_filter:
        cmd += ["--track", track_filter]

    try:
        import os as _os
        _env = {**_os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            cmd,
            cwd=str(HERE.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env=_env,
        )
        output = result.stdout + result.stderr

        # Extract saved path from output line "💾 Saved → /path/to/file.xlsx"
        saved_path = None
        for line in output.splitlines():
            if "Saved" in line and ".xlsx" in line:
                # grab everything after the arrow
                parts = line.split("→")
                if len(parts) > 1:
                    saved_path = parts[-1].strip()
                break

        if result.returncode != 0 and not saved_path:
            return jsonify({"error": output or "r5_analyze.py failed"}), 500

        return jsonify({
            "ok":         True,
            "path":       saved_path,
            "filename":   saved_path.split("/")[-1] if saved_path else None,
            "output":     output,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Report generation timed out (>60s)"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bris-summary", methods=["POST"])
def bris_summary():
    """Generate a BRIS Summary Handicap Report .docx (Dennis format) from uploaded DRF(s)."""
    if not (CM_AVAILABLE and BRIS_DOCX_AVAILABLE):
        return jsonify({"error": "CompareModels/python-docx not available"}), 500

    files_up = request.files.getlist("files")
    if not files_up or all(f.filename == "" for f in files_up):
        return jsonify({"error": "No files provided"}), 400

    job_id   = str(uuid.uuid4())
    work_dir = WORK_BASE / job_id
    work_dir.mkdir()

    all_results: dict = {}
    card_name: str | None = None
    errors: list = []

    for f in files_up:
        fname = safe_filename(f.filename)
        ext   = Path(fname).suffix.lower()
        if ext not in ALLOWED_EXT:
            errors.append(f"{fname}: unsupported type")
            continue

        save_path = work_dir / fname
        f.save(str(save_path))

        drfs = extract_drfs(save_path, work_dir) if ext == ".zip" else [save_path]
        if not drfs:
            errors.append(f"{fname}: no DRF files found in zip")
            continue

        for drf in drfs:
            try:
                results = _cm_score(str(drf))
                all_results.update(results)
                if card_name is None:
                    card_name = drf.stem.upper()
            except Exception as exc:
                errors.append(f"{drf.name}: {exc}")

    if not all_results:
        msg = "; ".join(errors) if errors else "No race data found"
        return jsonify({"error": msg}), 400

    card_name = card_name or "CARD"
    docx_name = f"{card_name}_BRIS_Summary_Report.docx"
    docx_path = work_dir / docx_name

    try:
        _bris_summary(all_results, card_name, str(docx_path))
    except Exception as exc:
        return jsonify({"error": f"Report generation failed: {exc}"}), 500

    return send_file(
        str(docx_path),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=docx_name,
    )


@app.route("/api/analytics")
def analytics():
    db_path = R5_DB_PATH
    if not db_path.exists():
        return jsonify({"error": "no_db"})

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # ── rank_hits (tier ladder retired 2026-06-11; win%/ROI by model rank) ────
    # ROI convention (corrected baseline): $2 flat, profit = sp_odds − 2 on a
    # win, −2 on a loss. sp_odds stores the $2 mutuel payoff.
    rank_hits = []
    for rank in (1, 2, 3):
        row = conn.execute("""
            SELECT COUNT(*) AS races, SUM(p.won) AS wins,
                   SUM(CASE WHEN p.won = 1 THEN COALESCE(p.sp_odds, 2) - 2
                            ELSE -2 END) AS profit
            FROM picks p
            JOIN races r ON p.race_id = r.id
            WHERE p.model_rank = ?
              AND r.result_fetched = 1
              AND r.is_backtest = 0
              AND p.finish_pos != -1
              AND p.finish_pos IS NOT NULL
        """, (rank,)).fetchone()
        races = row["races"] or 0
        wins  = row["wins"] or 0
        rank_hits.append({
            "rank":    rank,
            "races":   races,
            "wins":    wins,
            "win_pct": round(wins / races * 100, 1) if races else 0,
            "roi":     round((row["profit"] or 0) / (2 * races) * 100, 1) if races else None,
        })

    # ── val_roi ───────────────────────────────────────────────────────────────
    val_roi = []
    threshold = 6.0
    while threshold <= 10.01:
        row = conn.execute("""
            SELECT COUNT(*) AS plays,
                   SUM(p.won) AS wins,
                   SUM(CASE WHEN p.won = 1 THEN COALESCE(p.sp_odds, 2) - 2
                            ELSE -2 END) AS profit
            FROM picks p
            JOIN races r ON p.race_id = r.id
            WHERE p.val_n >= ?
              AND p.model_rank <= 5
              AND r.result_fetched = 1
              AND r.is_backtest = 0
              AND p.finish_pos != -1
              AND p.finish_pos IS NOT NULL
        """, (threshold,)).fetchone()
        plays  = row["plays"] or 0
        wins   = row["wins"]  or 0
        # corrected convention: $2 flat, profit = payoff − 2 / −2
        roi    = round((row["profit"] or 0) / (2 * plays) * 100, 1) if plays else None
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
            SELECT COUNT(*) AS cnt, SUM(p.won) AS wins
            FROM picks p
            JOIN races r ON p.race_id = r.id
            WHERE p.finish_pos > 0
              AND p.comp IS NOT NULL
              AND CAST(p.comp AS REAL) >= ?
              AND CAST(p.comp AS REAL) < ?
              AND r.is_backtest = 0
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
          AND r.is_backtest = 0
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
        "rank_hits":    rank_hits,
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
