#!/usr/bin/env python3
"""
R5 Web Frontend — Flask server wrapping the R5 handicapping engine.

Run:  python app.py
Then: open http://localhost:5050
"""
import io
import re
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


def run_r5(drf_path: Path, work_dir: Path, want_pdf: bool) -> tuple[str, Path | None]:
    cmd = [R5_PYTHON, str(CLAUDE_DIR / "run_r5.py"), str(drf_path)]
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

    pdf_path = None
    if want_pdf:
        candidate = work_dir / (drf_path.stem + "_R5.pdf")
        if candidate.exists():
            pdf_path = candidate

    return text, pdf_path


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


def parse_output(text: str) -> list[dict]:
    # Split into race blocks at each ====...==== line that precedes a 🏇 header
    blocks = re.split(r'(?=={60,}\n\s*🏇)', text)
    races = []
    for block in blocks:
        if "🏇" not in block:
            continue
        race = _parse_race_block(block)
        if race:
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


@app.route("/api/analyze", methods=["POST"])
def analyze():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files provided"}), 400

    want_pdf = request.form.get("pdf", "false").lower() == "true"

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
                text, pdf_path = run_r5(drf, work_dir, want_pdf)
                all_text += text + "\n"
                all_races.extend(parse_output(text))
                if pdf_path:
                    pdf_paths.append(str(pdf_path))
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
