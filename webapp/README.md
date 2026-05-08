# R5 Web Frontend

A local web UI for the R5 horse racing handicapping engine.
Upload a BRIS DRF or ZIP file, click **Analyze**, and view race-by-race results in your browser.

---

## Quick start

### 1. Create a virtual environment

```bash
cd /Users/harryadalian/Documents/HorseRacing/webapp
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
python app.py
```

Open **http://localhost:5050** in your browser.

---

## Usage

| Step | Action |
|------|--------|
| 1 | Drop one or more `.DRF` or `.ZIP` files onto the upload zone (or click to browse) |
| 2 | Tick **Generate PDF** if you want a downloadable PDF report |
| 3 | Click **Analyze Races** |
| 4 | Toggle between **📋 Overview** (card-level table) and **🏇 Race Detail** (tabbed view) |
| 5 | Browse race cards using the numbered tabs; click any Overview row to jump to that race |
| 6 | Download **TXT** or **PDF** from the top-right buttons |

### File types accepted

| Type | Notes |
|------|-------|
| `.DRF` | Standard BRIS past-performance file |
| `.ZIP` | BRIS zip download — DRF files are extracted automatically |

Multiple files may be uploaded in one batch (e.g. two tracks on the same card).

---

## Bet Recommendation

Every race card includes a **Bet Recommendation** box driven entirely by the R5 composite score:

| Composite | Verdict | Meaning |
|-----------|---------|---------|
| ≥ 6.0 | **PLAY** | Model has sufficient edge — viable bet |
| 5.5 – 5.99 | **NEAR** | Borderline — consider only with strong supporting factors |
| < 5.5 | **SKIP** | Insufficient edge — pass the race |

The box also lists **For** and **Against** bullets drawn from secondary factors:

| Factor | Signal |
|--------|--------|
| Trend ≥ +1.0 | Positive — horse improving |
| vPar ≥ 6.5 | Positive — beats class par |
| T/J ≥ 6.5 | Positive — strong connections |
| HOT pace + speed horse | Negative — pace scenario risk |
| HOT pace + closer | Positive — closer gets a pace target |
| Min odds warning | Negative — ML odds too short for value |

**Min acceptable odds** = `max(ML − 1, 1)` (e.g. 3-1 ML → minimum 2-1 on board).

These secondary bullets are informational only — the composite score is the sole gate for PLAY / NEAR / SKIP.

---

## Overview Toggle

After analysis completes, two view buttons appear at the top of the results:

- **📋 Overview** — one-row-per-race summary table with columns: Race, Class, Distance, Top Pick, Composite, Tier, Verdict (PLAY / NEAR / SKIP), and Value Alt.
- **🏇 Race Detail** — full tabbed race card view (default).

Clicking any row in the Overview table jumps directly to that race in the Detail view.

---

## Options

### `--port`
Run on a different port:
```bash
python app.py --port 8080
```

### `--host 0.0.0.0`
Expose to other machines on your local network (use with care):
```bash
python app.py --host 0.0.0.0
```

### `--debug`
Enable Flask debug mode (auto-reloads on code changes):
```bash
python app.py --debug
```

---

## How it works

```
Browser  →  POST /api/analyze  →  Flask  →  run_r5.py  →  stdout captured
                                                        →  _R5.pdf written (if --pdf)
         ←  JSON {races, text, job_id}  ←─────────────────────────────────
GET /api/download/txt/<job_id>   →  plain-text report
GET /api/download/pdf/<job_id>   →  PDF (requires reportlab, already installed)
```

- `app.py` shells out to `../Claude/run_r5.py` and captures stdout.
- The text output is both parsed into structured race cards **and** preserved verbatim in the "Raw text" collapsible.
- Job results are kept in memory; they clear when the server restarts.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: flask` | Run `pip install -r requirements.txt` inside the venv |
| "Analysis produced no output" | Confirm `../Claude/run_r5.py` works from the command line |
| Horse table shows "could not be parsed" | Raw text is still shown below — file a bug with the output |
| PDF button stays greyed out | Uncheck and recheck "Generate PDF", or run without it |

---

## Project layout

```
webapp/
├── app.py               Flask server + R5 output parser
├── requirements.txt     Python dependencies (just Flask)
├── README.md            This file
└── templates/
    └── index.html       Single-page UI (CSS + JS inline)
```
