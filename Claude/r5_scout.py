#!/usr/bin/env python3
"""
R5 Scout — Daily Racing Intelligence Scraper
Runs on your local Mac. Scrapes key sources, uses Claude to extract 
structured intel, saves JSON to Google Drive HorseRacing folder.

Usage:
    python3 r5_scout.py                        # today's races, all tracks
    python3 r5_scout.py --track CD             # Churchill Downs only
    python3 r5_scout.py --track CD --date 20260502
    python3 r5_scout.py --horses "Renegade,Commandment,Further Ado"

Requirements:
    pip install requests beautifulsoup4 anthropic google-auth google-api-python-client
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── CONFIG ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GDRIVE_OUTPUT_FOLDER = "HorseRacing"
HORSE_RACING_ROOT = Path("/Users/harryadalian/Documents/HorseRacing")
LOCAL_OUTPUT_DIR = HORSE_RACING_ROOT / "scout"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── TRACK CODE → KEYWORD EXPANSION ──────────────────────────────────────────
# Maps BRIS track codes to natural-language search terms used in news articles
TRACK_KEYWORDS = {
    "DBY": ["Kentucky Derby", "Derby", "Churchill"],
    "CD":  ["Churchill Downs", "Churchill"],
    "CDX": ["Churchill Downs", "Churchill"],
    "KEE": ["Keeneland"],
    "SAR": ["Saratoga"],
    "AQU": ["Aqueduct"],
    "BAQ": ["Aqueduct", "Belmont at the Big A", "Big A"],
    "BEL": ["Belmont", "Belmont Park"],
    "DMR": ["Del Mar"],
    "GP":  ["Gulfstream"],
    "OP":  ["Oaklawn"],
    "PIM": ["Pimlico", "Preakness"],
    "LRL": ["Laurel Park", "Laurel"],
    "MTH": ["Monmouth"],
    "AP":  ["Arlington"],
    "SAX": ["Santa Anita", "Santa Anita Park"],
}

# ── SOURCES ──────────────────────────────────────────────────────────────────
# Status as of 2026-05: Paulick blocks scrapers (403/404). HRN RSS redirects
# to HTML. Blood-Horse RSS is 404. TDN RSS and HRN/BH HTML scrapes work.
SOURCES = {
    "hrn": {
        "name": "Horse Racing Nation",
        "url": "https://www.horseracingnation.com/news",
        "rss": None,  # RSS redirects to HTML — use HTML scrape
        "selectors": {"items": "article", "title": "h3", "body": "small"},
        "base_url": "https://www.horseracingnation.com",
    },
    "tdn": {
        "name": "Thoroughbred Daily News",
        "url": "https://www.thoroughbreddailynews.com/",
        "rss": "https://www.thoroughbreddailynews.com/feed/",
        "selectors": {"items": "article", "title": "h2", "body": ".post-content"},
        "base_url": "https://www.thoroughbreddailynews.com",
    },
    "bloodhorse": {
        "name": "Blood-Horse",
        "url": "https://www.bloodhorse.com/horse-racing/articles",
        "rss": None,  # RSS is 404 — use HTML scrape
        "selectors": {"items": "article", "title": "h4", "body": "p"},
        "base_url": "https://www.bloodhorse.com",
    },
}

# ── TRACK CODE → DRF TRACK ID ────────────────────────────────────────────────
# DRF entry URLs use their own track IDs — map BRIS codes where they differ
DRF_TRACK_MAP = {
    "CDX": "CD",   # Churchill Downs regular meet uses CD in DRF
    "DBY": "CD",   # Kentucky Derby day
    "BAQ": "BAQ",  # Belmont at the Big A — DRF uses BAQ
    "BEL": "BEL",
    "SAR": "SAR",
    "KEE": "KEE",
    "PIM": "PIM",
    "GP":  "GP",
    "DMR": "DMR",
    "OP":  "OP",
    "MTH": "MTH",
    "LRL": "LRL",
    "SAX": "SA",   # Santa Anita — DRF uses SA
}

# ── EQUIBASE / DRF OFFICIAL SCRATCH FETCHER ──────────────────────────────────
def fetch_official_scratches(track, date_str):
    """
    Fetch official scratch list from DRF entries page for a given track/date.

    Args:
        track    : BRIS track code (e.g. 'BAQ', 'CDX', 'PIM')
        date_str : date in YYYYMMDD format (e.g. '20260510')

    Returns:
        Tuple (scratches, also_eligibles):
          scratches      : list of confirmed scratches (scratchIndicator == 'Y')
          also_eligibles : list of AE horses (scratchIndicator == 'A')
            AEs are on the waiting list — they draw in to start if scratches occur.
            They are NOT scratched and MUST be scored.
        Each list entry: {"race": 7, "pgm": "4", "name": "FORT NELSON", "source": "DRF official"}
        Returns ([], []) on any error — never raises.

        Backwards-compat note: callers expecting a flat list will break. Update them
        to unpack the tuple. See Scout-3 fix (TODO.md) for the CDX0528 R7 incident
        that motivated this change.
    """
    drf_track = DRF_TRACK_MAP.get(track.upper(), track.upper())
    # Convert YYYYMMDD → MM-DD-YYYY for DRF URL
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        drf_date = dt.strftime("%m-%d-%Y")
    except ValueError:
        print(f"  [scratch] Bad date format: {date_str}")
        return []

    url = f"https://www.drf.com/entries/entryDetails/id/{drf_track}/country/USA/date/{drf_date}"
    print(f"  [scratch] Fetching: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  [scratch] HTTP {r.status_code} — no scratch data available")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        # DRF embeds full race JSON in a text node containing "raceKey"
        json_node = soup.find(string=lambda t: t and '"raceKey"' in t)
        if not json_node:
            print(f"  [scratch] No race JSON found on page")
            return [], []

        data = json.loads(json_node.string)
        scratches      = []
        also_eligibles = []
        unknown_inds   = []  # any value other than N/Y/A — log for visibility, do not auto-scratch
        for race in data.get("races", []):
            rnum = race["raceKey"]["raceNumber"]
            for runner in race.get("runners", []):
                ind  = runner.get("scratchIndicator", "N")
                pgm  = str(runner.get("programNumberStripped",
                           runner.get("programNumber", "?"))).strip()
                name = runner.get("horseName", "?").upper()
                entry = {"race": rnum, "pgm": pgm, "name": name, "source": "DRF official"}
                if ind == "Y":
                    scratches.append(entry)
                elif ind == "A":
                    also_eligibles.append(entry)
                elif ind != "N":
                    # Unknown indicator — record but do not treat as scratch (Scout-3 lesson).
                    unknown_inds.append({**entry, "indicator": ind})

        print(f"  [scratch] Found {len(scratches)} official scratch(es)")
        for s in scratches:
            print(f"    ✗ R{s['race']} #{s['pgm']} {s['name']}")
        if also_eligibles:
            print(f"  [scratch] Found {len(also_eligibles)} Also-Eligible (AE) horse(s) — NOT scratched, will be scored")
            for s in also_eligibles:
                print(f"    ⏳ R{s['race']} #{s['pgm']} {s['name']} (AE)")
        if unknown_inds:
            print(f"  [scratch] {len(unknown_inds)} runner(s) with unknown scratchIndicator — kept in field:")
            for s in unknown_inds:
                print(f"    ? R{s['race']} #{s['pgm']} {s['name']} (indicator={s['indicator']!r})")
        return scratches, also_eligibles

    except Exception as e:
        print(f"  [scratch] Error fetching scratch list: {e}")
        return [], []


# ── SCRAPER ───────────────────────────────────────────────────────────────────
def fetch(url, timeout=12):
    """Fetch URL with retries"""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.text
            print(f"  [{r.status_code}] {url}")
            return None
        except Exception as e:
            if attempt == 2:
                print(f"  [ERR] {url} — {e}")
            time.sleep(1)
    return None


def scrape_rss(rss_url, keyword_filter=None):
    """Parse RSS feed, return list of {title, link, pubdate, summary}"""
    html = fetch(rss_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml-xml")
    items = soup.find_all("item")
    results = []
    for item in items[:20]:
        title = item.find("title")
        link  = item.find("link")
        desc  = item.find("description")
        pub   = item.find("pubDate")

        title_text = title.get_text(strip=True) if title else ""
        desc_text  = BeautifulSoup(desc.get_text() if desc else "", "html.parser").get_text()[:500]

        if keyword_filter:
            combined = (title_text + " " + desc_text).lower()
            if not any(k.lower() in combined for k in keyword_filter):
                continue

        results.append({
            "title":   title_text,
            "url":     link.get_text(strip=True) if link else "",
            "date":    pub.get_text(strip=True) if pub else "",
            "summary": desc_text.strip(),
        })
    return results


def scrape_page(url, selectors, keyword_filter=None, base_url=None):
    """Scrape HTML page for articles"""
    html = fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(selectors["items"])
    results = []
    _base = base_url or url.split("/")[0] + "//" + url.split("/")[2]

    for item in items[:15]:
        title_el = item.select_one(selectors["title"])
        body_el  = item.select_one(selectors["body"])
        link_el  = item.select_one("a[href]")

        title_text = title_el.get_text(strip=True) if title_el else ""
        body_text  = body_el.get_text(strip=True)[:600] if body_el else ""
        link       = link_el["href"] if link_el else ""
        if link and link.startswith("/"):
            link = _base.rstrip("/") + link

        if keyword_filter:
            combined = (title_text + " " + body_text).lower()
            if not any(k.lower() in combined for k in keyword_filter):
                continue

        if title_text:
            results.append({
                "title":   title_text,
                "url":     link,
                "date":    "",
                "summary": body_text,
            })

    return results


def gather_raw_intel(track=None, horses=None, race_date=None):
    """Scrape all sources and return raw article list"""
    keywords = []
    if track:
        # Expand track code to natural-language terms (e.g. DBY → Kentucky Derby, Derby, Churchill)
        keywords.extend(TRACK_KEYWORDS.get(track.upper(), [track]))
    if horses:
        keywords.extend([h.strip() for h in horses.split(",")])
    if not keywords:
        keywords = ["Derby", "Churchill", "Keeneland", "Saratoga",
                    "scratch", "workout", "trainer", "jockey"]

    all_articles = []
    print(f"\n📡 Scraping {len(SOURCES)} sources...")
    print(f"   Keywords: {keywords}")

    for key, source in SOURCES.items():
        print(f"  → {source['name']}...", end=" ", flush=True)
        articles = []

        # Try RSS first (cleaner)
        if source["rss"]:
            articles = scrape_rss(source["rss"], keyword_filter=keywords)

        # Fall back to HTML scrape
        if not articles:
            articles = scrape_page(
                source["url"], source["selectors"],
                keyword_filter=keywords,
                base_url=source.get("base_url"),
            )

        print(f"{len(articles)} articles")
        for a in articles:
            a["source"] = source["name"]
        all_articles.extend(articles)

    print(f"\n  Total: {len(all_articles)} articles gathered\n")
    return all_articles


# ── CLAUDE INTEL EXTRACTION ──────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are an expert horse racing analyst. I will give you raw scraped 
articles from horse racing news sites. Extract ALL actionable intelligence in structured JSON.

Focus on:
1. SCRATCHES — any horse withdrawn from a race
2. EQUIPMENT CHANGES — blinkers on/off, new shoes, tongue tie, etc.
3. TRAINER QUOTES — direct quotes about horse's condition, race plan, confidence level
4. WORKOUT NOTES — notable morning works, bullet workouts, concerns
5. TRACK CONDITIONS — bias reports, surface changes, weather impact
6. JOCKEY SWITCHES — rider changes and reason if given
7. SHARP MONEY — unusual betting activity, steam moves, value plays
8. INJURY/HEALTH — any reported health concerns
9. RACE NOTES — pace scenarios, traffic concerns, post position impact

Return ONLY valid JSON in this exact structure:
{
  "scraped_date": "YYYY-MM-DD",
  "sources_checked": ["source1", "source2"],
  "scratches": [
    {"horse": "Horse Name", "track": "CD", "race": "Race 1", "reason": "bruised foot", "source": "DRF"}
  ],
  "equipment_changes": [
    {"horse": "Horse Name", "change": "blinkers added", "expected_effect": "more focus", "source": "Paulick"}
  ],
  "trainer_quotes": [
    {"horse": "Horse Name", "trainer": "Trainer Name", "quote": "...", "sentiment": "positive|neutral|negative", "source": "HRN"}
  ],
  "workout_notes": [
    {"horse": "Horse Name", "date": "Apr 28", "distance": "5f", "time": "59.2", "note": "bullet work", "concern": false, "source": "TDN"}
  ],
  "track_conditions": [
    {"track": "CD", "condition": "fast", "bias": "inside speed favored", "weather": "clear 68F", "source": "Paulick"}
  ],
  "jockey_switches": [
    {"horse": "Horse Name", "old_jockey": "Smith", "new_jockey": "Jones", "reason": "...", "source": "DRF"}
  ],
  "sharp_money": [
    {"horse": "Horse Name", "note": "heavy early betting action, dropped from 20-1 to 12-1", "source": "HRN"}
  ],
  "health_concerns": [
    {"horse": "Horse Name", "concern": "minor heat in ankle", "status": "cleared to run", "source": "Paulick"}
  ],
  "key_insights": [
    "One-line insight that would change how you bet this card"
  ]
}

If a category has no data, return an empty array [].
Do not invent anything. Only include what is explicitly stated in the articles.

ARTICLES TO ANALYZE:
"""


def extract_intel_with_claude(articles, api_key):
    """Send articles to Claude for structured extraction"""
    if not api_key:
        print("⚠️  No ANTHROPIC_API_KEY set — skipping Claude extraction")
        print("   Set it with: export ANTHROPIC_API_KEY=your_key")
        return None

    # Build article text
    article_text = ""
    for i, a in enumerate(articles[:30], 1):  # cap at 30
        article_text += f"\n--- Article {i}: {a['source']} ---\n"
        article_text += f"Title: {a['title']}\n"
        article_text += f"Date: {a.get('date','')}\n"
        article_text += f"Summary: {a['summary']}\n"

    prompt = EXTRACTION_PROMPT + article_text

    print("🧠 Sending to Claude for intel extraction...")
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )

        if r.status_code != 200:
            print(f"  Claude API error: {r.status_code} — {r.text[:200]}")
            return None

        data = r.json()
        text = data["content"][0]["text"].strip()

        # Strip markdown fences if present
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"```$", "", text.rstrip())

        # Extract just the JSON object (handles trailing text after closing brace)
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in response")
        text = text[start:end]

        intel = json.loads(text)
        intel["raw_article_count"] = len(articles)
        return intel

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw response: {text[:500]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


# ── R5 INTEGRATION FORMAT ─────────────────────────────────────────────────────
def format_for_r5(intel, horses_list=None):
    """
    Convert intel JSON into a text block that can be prepended to R5 analysis.
    When running R5, paste this block before the CSV data.
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"🔍 R5 SCOUT INTEL — {intel.get('scraped_date', 'Today')}")
    lines.append("=" * 70)

    # Filter to relevant horses if specified
    def relevant(horse_name):
        if not horses_list:
            return True
        return any(h.lower() in horse_name.lower() for h in horses_list)

    # SCRATCHES — highest priority
    scratches = intel.get("scratches", [])
    if scratches:
        lines.append("\n🚨 SCRATCHES:")
        for s in scratches:
            lines.append(f"  ✗ {s['horse']} ({s.get('track','')} R{s.get('race','?')}) — {s.get('reason','unknown reason')}")

    # EQUIPMENT
    equip = [e for e in intel.get("equipment_changes", []) if relevant(e["horse"])]
    if equip:
        lines.append("\n🔧 EQUIPMENT CHANGES:")
        for e in equip:
            lines.append(f"  #{e['horse']}: {e['change']} — {e.get('expected_effect','')}")

    # TRACK CONDITIONS
    conds = intel.get("track_conditions", [])
    if conds:
        lines.append("\n🏟️  TRACK CONDITIONS:")
        for c in conds:
            lines.append(f"  {c.get('track','?')}: {c.get('condition','')} | Bias: {c.get('bias','')} | {c.get('weather','')}")

    # TRAINER QUOTES (positive/negative signals)
    quotes = [q for q in intel.get("trainer_quotes", []) if relevant(q["horse"])]
    if quotes:
        lines.append("\n💬 TRAINER SIGNALS:")
        for q in quotes:
            emoji = "✅" if q.get("sentiment") == "positive" else ("⚠️" if q.get("sentiment") == "negative" else "•")
            lines.append(f"  {emoji} {q['horse']} ({q.get('trainer','')}): \"{q.get('quote','')}\"")

    # WORKOUT NOTES
    works = [w for w in intel.get("workout_notes", []) if relevant(w["horse"])]
    if works:
        lines.append("\n🏃 WORKOUT NOTES:")
        for w in works:
            concern = " ⚠️ CONCERN" if w.get("concern") else ""
            lines.append(f"  {w['horse']}: {w.get('date','')} {w.get('distance','')} in {w.get('time','')} — {w.get('note','')}{concern}")

    # JOCKEY SWITCHES
    switches = [j for j in intel.get("jockey_switches", []) if relevant(j["horse"])]
    if switches:
        lines.append("\n🏇 JOCKEY SWITCHES:")
        for j in switches:
            lines.append(f"  {j['horse']}: {j.get('old_jockey','?')} → {j.get('new_jockey','?')} ({j.get('reason','')})")

    # SHARP MONEY
    sharp = [s for s in intel.get("sharp_money", []) if relevant(s["horse"])]
    if sharp:
        lines.append("\n💰 SHARP MONEY:")
        for s in sharp:
            lines.append(f"  {s['horse']}: {s.get('note','')}")

    # HEALTH
    health = [h for h in intel.get("health_concerns", []) if relevant(h["horse"])]
    if health:
        lines.append("\n🏥 HEALTH NOTES:")
        for h in health:
            lines.append(f"  ⚠️ {h['horse']}: {h.get('concern','')} — Status: {h.get('status','unknown')}")

    # KEY INSIGHTS
    insights = intel.get("key_insights", [])
    if insights:
        lines.append("\n⚡ KEY INSIGHTS:")
        for ins in insights:
            lines.append(f"  → {ins}")

    lines.append("\n" + "=" * 70)
    lines.append("R5 SCOUT ADJUSTMENTS (applied automatically by run_r5.py):")
    lines.append("  • Positive trainer quote:          +0.20")
    lines.append("  • Negative trainer quote:          -0.30")
    lines.append("  • Health concern:                  -0.30")
    lines.append("  • Sharp money move:                +0.15")
    lines.append("  • Bullet workout (last 7 days):    +0.10")
    lines.append("  • Workout concern:                 -0.15")
    lines.append("  • First-time blinkers:             +0.10")
    lines.append("  • Elite jockey upgrade:            +0.10")
    lines.append("  ⚡ Total scout adjustment capped at ±0.40 per horse")
    lines.append("=" * 70)

    return "\n".join(lines)


# ── OUTPUT ────────────────────────────────────────────────────────────────────
def save_output(intel, r5_text, track, run_date):
    """Save JSON and text outputs locally (and optionally to Google Drive)"""
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"{track or 'ALL'}_{run_date}"

    # JSON
    json_path = LOCAL_OUTPUT_DIR / f"scout_{slug}.json"
    with open(json_path, "w") as f:
        json.dump(intel, f, indent=2)
    print(f"\n💾 JSON saved: {json_path}")

    # R5 text block
    txt_path = LOCAL_OUTPUT_DIR / f"scout_{slug}_r5.txt"
    with open(txt_path, "w") as f:
        f.write(r5_text)
    print(f"📄 R5 block saved: {txt_path}")

    # Also save to Google Drive folder if pydrive2 available
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        import pickle

        token_path = Path.home() / ".r5_gdrive_token.pickle"
        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)
            service = build("drive", "v3", credentials=creds)

            # Find HorseRacing folder
            results = service.files().list(
                q=f"name='{GDRIVE_OUTPUT_FOLDER}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id)"
            ).execute()
            folders = results.get("files", [])
            if folders:
                folder_id = folders[0]["id"]

                # Upload JSON
                from googleapiclient.http import MediaFileUpload
                meta = {"name": f"scout_{slug}.json", "parents": [folder_id]}
                media = MediaFileUpload(str(json_path), mimetype="application/json")
                service.files().create(body=meta, media_body=media).execute()
                print(f"☁️  Uploaded to Google Drive: scout_{slug}.json")
    except Exception:
        pass  # Google Drive upload is optional

    return json_path, txt_path


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="R5 Scout — Racing Intelligence Scraper")
    parser.add_argument("--track", help="Track code to focus on (e.g. CD, SAR, KEE)")
    parser.add_argument("--date",  help="Race date YYYYMMDD (default: today)")
    parser.add_argument("--horses", help="Comma-separated horse names to focus on")
    parser.add_argument("--no-claude", action="store_true", help="Skip Claude extraction (raw only)")
    parser.add_argument("--output-only", help="Just print from existing JSON file")
    args = parser.parse_args()

    run_date = args.date or date.today().strftime("%Y%m%d")
    horses_list = [h.strip() for h in args.horses.split(",")] if args.horses else None

    print(f"\n🏇 R5 SCOUT v1.0 — {run_date}")
    print(f"   Track: {args.track or 'All'}")
    print(f"   Horses: {args.horses or 'All'}")

    # If just formatting existing file
    if args.output_only:
        with open(args.output_only) as f:
            intel = json.load(f)
        r5_text = format_for_r5(intel, horses_list)
        print(r5_text)
        return

    # Scrape
    articles = gather_raw_intel(
        track=args.track,
        horses=args.horses,
        race_date=run_date
    )

    if not articles:
        print("⚠️  No articles found. Check your internet connection and source availability.")
        sys.exit(1)

    # Extract with Claude
    intel = None
    if not args.no_claude:
        api_key = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
        intel = extract_intel_with_claude(articles, api_key)

    # Fallback: build minimal intel from raw articles
    if not intel:
        print("ℹ️  Building minimal intel from raw articles...")
        intel = {
            "scraped_date": run_date,
            "sources_checked": list(SOURCES.keys()),
            "raw_article_count": len(articles),
            "scratches": [],
            "equipment_changes": [],
            "trainer_quotes": [],
            "workout_notes": [],
            "track_conditions": [],
            "jockey_switches": [],
            "sharp_money": [],
            "health_concerns": [],
            "key_insights": [f"Raw articles collected: {len(articles)}. Run with ANTHROPIC_API_KEY set for full extraction."],
            "raw_articles": articles[:20],
        }

    # Merge official scratch list + AE list — always runs if track is specified
    if args.track:
        print("\n🔍 Fetching official scratch list...")
        official_scratches, official_aes = fetch_official_scratches(args.track, run_date)
        if official_scratches:
            # Deduplicate against any scratches Claude already found from articles
            existing_names = {s["horse"].upper() for s in intel.get("scratches", [])}
            for s in official_scratches:
                if s["name"] not in existing_names:
                    intel.setdefault("scratches", []).append({
                        "horse":  s["name"],
                        "track":  args.track.upper(),
                        "race":   str(s["race"]),
                        "pgm":    s["pgm"],
                        "reason": "official scratch",
                        "source": "DRF official"
                    })
            print(f"  ✓ {len(official_scratches)} official scratch(es) merged into intel")

        # Also-Eligibles: surface as a separate intel key so run_r5 can flag them
        # in the report without removing them from the field. Scout-3 fix (2026-05-28).
        if official_aes:
            for ae in official_aes:
                intel.setdefault("also_eligibles", []).append({
                    "horse":  ae["name"],
                    "track":  args.track.upper(),
                    "race":   str(ae["race"]),
                    "pgm":    ae["pgm"],
                    "source": "DRF official"
                })
            print(f"  ✓ {len(official_aes)} Also-Eligible(s) recorded in intel (will be scored, not scratched)")

    # Format for R5
    r5_text = format_for_r5(intel, horses_list)
    print(r5_text)

    # Save
    save_output(intel, r5_text, args.track, run_date)


if __name__ == "__main__":
    main()
