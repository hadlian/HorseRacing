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
| 2 | Tick **Auto Scout** to pull live trainer quotes and official scratches before analysis *(requires API key — see below)* |
| 3 | Tick **Generate PDF** if you want a downloadable PDF report |
| 4 | Click **Analyze Races** |
| 5 | Toggle between **📋 Overview** (card-level table) and **🏇 Race Detail** (tabbed view) |
| 6 | Browse race cards using the numbered tabs; click any Overview row to jump to that race |
| 7 | Mark any late scratches using the **🚨 Mark Scratch** input on each race card |
| 8 | Download **TXT** or **PDF** from the top-right buttons |

### File types accepted

| Type | Notes |
|------|-------|
| `.DRF` | Standard BRIS past-performance file |
| `.ZIP` | BRIS zip download — DRF files are extracted automatically |

Multiple files may be uploaded in one batch (e.g. two tracks on the same card).

---

## Auto Scout

The **Auto Scout** checkbox runs `r5_scout.py` before scoring. It does two things:

1. **Official scratch list** — queries the DRF entries page for the track and date, parses all horses with `scratchIndicator ≠ N`, and feeds them into the engine. Any top-3 horse that was scratched triggers a `🚨 SCRATCH NOTICE` banner in the race card with a revised top pick.
2. **Trainer / sharp-money intel** — scrapes Horse Racing Nation, Blood-Horse, and TDN for trainer quotes, workout notes, and betting-line moves. Claude extracts structured signals and applies small composite score adjustments (capped at ±0.40 per horse).

**Requires:** `ANTHROPIC_API_KEY` set in your environment and a working internet connection.  
**Without it:** uncheck the box and the engine runs on DRF data only — no scratches are pre-loaded.

> Run Auto Scout **race morning** to catch day-of scratches. For high-stakes races, cross-check against the official track scratch list regardless.

---

## Scratch Handling

### Engine-reported scratches (Auto Scout)

When Auto Scout is enabled and a pre-scratch top-3 horse is removed, the engine prints a `🚨 SCRATCH NOTICE` in its output. The web app detects these and displays a red banner on the affected race card:

```
🚨 Scratch — #4 FORT NELSON
Pre-scratch Rank 3 — removed from field
↳ Revised Top Pick: #5 I'M READY TO GO — Comp 6.41
```

The scratched horse is struck-through in the table, the top-pick and value-alt boxes update automatically, and an ⚠️ warning appears on the exotics section reminding you the tickets are pre-scratch.

### Manual scratches (any time)

Every race card has a **🚨 Mark Scratch** bar at the top of the horse table. Type a program number and press **Enter** (or click **Add**):

- The horse row is immediately struck through with a **SCR** badge
- The top-pick box promotes the next active horse, labelled *(revised)*
- The value-alt box recalculates from the remaining field
- The bet recommendation recalculates using only active horses
- Chips appear next to the input — click **×** on any chip to unscratch

Manual scratches are client-side only and clear when you reload the page or run a new analysis.

---

## Tight Cluster Flag

When the engine detects that the top-3 composites are within 1.5 points of each other, it fires a **⚠️ TIGHT CLUSTER** warning. The web app shows this as:

- An orange pill in the race header: `⚠️ TIGHT CLUSTER · 0.95 pts`
- An "Against" bullet in the Bet Recommendation box: *tight speed cluster (top-3 spread 0.95 pts) — low model separation, race is hard to call*

A tight cluster is a signal to reduce bet size or pass the race — the model cannot reliably separate the field.

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

- **📋 Overview** — one-row-per-race summary table: Race, Dist, Purse, Pace, Top Pick / Value Alt, Comp, ML, Verdict.
- **🏇 Race Detail** — full tabbed race card view (default).

Clicking any row in the Overview table jumps directly to that race in the Detail view.

---

## Mobile Layout

The UI is fully responsive at ≤ 639 px (phone screen):

- **Horse table** shows only `#`, `Horse`, `Comp`, `Tier` by default — the 9 detail columns are hidden.
- Each horse row has a **▶ tap-to-expand** button that reveals a 3-column metrics grid (ML, WS4, Trend, FCI, vPar, Ped, T/J, Pce, Val). Tap again to collapse.
- **Race tabs** scroll horizontally instead of wrapping across multiple lines.
- **Overview table** hides Purse, Pace, and ML columns on narrow screens.
- Picks and bet rec stack to single-column layout.

Desktop layout is unchanged.

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
Browser  →  POST /api/analyze  →  Flask  →  run_r5.py [--auto-scout] [--pdf]
                                                ↓
                                         r5_scout.py   ← DRF entries page (official scratches)
                                         (if --auto-scout)  ← HRN / Blood-Horse / TDN
                                                ↓
                                          stdout captured
                                          _R5.pdf written (if --pdf)
         ←  JSON {races, text, job_id}  ←──────────────────────────────────
GET /api/download/txt/<job_id>   →  plain-text report
GET /api/download/pdf/<job_id>   →  PDF (requires reportlab)
```

- `app.py` shells out to `../Claude/run_r5.py` and captures stdout.
- Scratch notices in stdout are pre-scanned across the full output, keyed by race number (`R7:`), and injected into the correct race card — they appear between race blocks in the raw text, not inside them.
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
| Scratch banner not showing | Re-run with **Auto Scout** checked — the engine only fires scratch notices when it has the official scratch list |
| Auto Scout returns no intel | Check that `ANTHROPIC_API_KEY` is set and the track keyword is in `r5_scout.py`'s `TRACK_KEYWORDS` |
| Manual scratch doesn't update picks | Make sure you typed the exact program number (e.g. `4`, not `#4`) |

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
