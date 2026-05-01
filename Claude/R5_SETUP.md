# R5 Racing System — Setup Guide

## What's in this package

| File | Purpose |
|------|---------|
| `r5_parser_v2.py` | Core parser — reads BRIS DRF files, calculates WS4/FCI/Composite |
| `r5_scout.py` | Daily scraper — pulls news from Paulick, HRN, TDN, DRF, Blood-Horse |
| `run_r5.py` | Master runner — combines scout intel + parser into full analysis |
| `R5_SETUP.md` | This file |

---

## One-time setup (Mac)

```bash
# 1. Install Python dependencies
pip3 install requests beautifulsoup4 lxml anthropic

# 2. Set your Anthropic API key (Claude extracts intel from articles)
export ANTHROPIC_API_KEY=your_key_here
# Add to ~/.zshrc to make permanent:
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc

# 3. Create output folders
mkdir -p /Users/harryadalian/Documents/HorseRacing/scout
mkdir -p "/Users/harryadalian/Documents/HorseRacing/files 2"
mkdir -p /Users/harryadalian/Documents/HorseRacing/Claude
cp r5_parser_v2.py /Users/harryadalian/Documents/HorseRacing/claude/
cp r5_scout.py /Users/harryadalian/Documents/HorseRacing/claude/
cp run_r5.py /Users/harryadalian/Documents/HorseRacing/claude/
```

---

## Daily workflow

### Step 1 — Buy and download the BRIS file
1. Go to brisnet.com → Data Files → PP Data Files (single)
2. Select track + date, download the .DRF zip
3. Extract to `~/HorseRacing/files 2/`

### Step 2 — Run the full analysis
```bash
cd /Users/harryadalian/Documents/HorseRacing/Claude

# Full card with auto-scout (recommended)
python3 run_r5.py "../files 2/CD0502.DRF" --auto-scout

# Single race
python3 run_r5.py "../files 2/CD0502.DRF" --race 5 --auto-scout

# Save output to file
python3 run_r5.py "../files 2/CD0502.DRF" --auto-scout --save

# Manual scout for specific horses
python3 r5_scout.py --track CD --horses "Renegade,Commandment,Further Ado"
```

### Step 3 — Feed to Claude (this project)
Upload the output file here, or just paste the R5 block. Claude will have
the scout intel and can answer questions, refine picks, or adjust weights.

---

## R5 Composite Score Guide

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| FCI (WS4 + Trend) | 25% | Speed + direction |
| Class vs Par | 20% | How horse compares to today's class level |
| Bias Fit | 15% | Post position / running style vs track bias |
| Trainer/Jockey | 10% | Connection quality + T/J combo ROI |
| Form Angle | 10% | Recent figure quality |
| Pedigree | 10% | Distance/surface suitability |
| Value (Odds) | 10% | Overlay vs morning line |

## Scout Adjustment Scale

| Signal | Adj |
|--------|-----|
| Positive trainer quote | +0.20 |
| Sharp money move | +0.15 |
| Bullet workout (last 7d) | +0.10 |
| First-time blinkers | +0.10 |
| Jockey upgrade to elite | +0.10 |
| Health concern / vet scratch | -0.30 |
| Negative trainer signal | -0.30 |
| Workout concern | -0.15 |
| Equipment removed | -0.05 |

## Confidence Tiers

| Score | Tier | Meaning |
|-------|------|---------|
| ≥ 8.5 | HIGH | Strong play, bet confidently |
| 7.5–8.4 | SOLID | Good play, normal stake |
| 6.5–7.4 | FAIR | Use in exotics, small win bet |
| < 6.5 | SPEC | Exotics only or pass |

---

## Running with Claude
Once you have results, upload the .DRF file or analysis output here and ask:
- "Run R5 on this file"
- "Which horses should I use in the Pick 4?"
- "Adjust weights for a turf sprint"
- "Show me the value plays only"
