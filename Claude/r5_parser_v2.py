import csv
from collections import defaultdict

# ── TRACK BIAS ────────────────────────────────────────────────────────────────
# How post position is weighted per track: inside / outside / neutral
TRACK_POST_BIAS = {
    'CD':  'inside',
    'DBY': 'inside',   # Kentucky Derby at Churchill
    'KEE': 'inside',
    'AQU': 'inside',
    'OP':  'inside',
    'GP':  'inside',
    'PIM': 'inside',
    'SAR': 'neutral',
    'DMR': 'neutral',
    'MTH': 'neutral',
    'BEL': 'outside',  # wide Belmont turns
}

def pf(row, idx):
    try:
        v = row[idx - 1]
        return v.strip() if v else ""
    except IndexError:
        return ""

def num(row, idx):
    try:
        v = pf(row, idx).replace(',', '')
        return float(v) if v else None
    except:
        return None

def normalize_surf(s):
    s = s.upper().strip()
    if s in ('D', 'DIRT'):                      return 'D'
    if s in ('T', 'TURF'):                      return 'T'
    if s in ('A', 'AW', 'ALL-WEATHER', 'POLY'): return 'A'
    return s

def calc_ws4(speeds):
    weights = [0.4, 0.3, 0.2, 0.1]
    valid = [(w, s) for w, s in zip(weights, speeds) if s and s > 0]
    if not valid: return None
    tw = sum(w for w, s in valid)
    return sum((w / tw) * s for w, s in valid)

def calc_trend(speeds):
    """Continuous trend: each 2 pts of improvement vs recent avg = +1 trend, capped ±5."""
    s = [x for x in speeds if x and x > 0]
    if len(s) < 2: return 0
    avg_rest = sum(s[1:]) / len(s[1:])
    diff = s[0] - avg_rest
    return round(max(-5.0, min(5.0, diff / 2.0)), 1)

def tier(score):
    if score is None: return "SPEC"
    if score >= 8.5:  return "HIGH"
    if score >= 7.5:  return "SOLID"
    if score >= 6.5:  return "FAIR"
    return "SPEC"

def parse_drf(path):
    horses = []
    elite_t = ['PLETCHER', 'BAFFERT', 'ASMUSSEN', 'BROWN', 'COX', 'MCPEEK',
               'MOTT', 'WALSH', 'MOTION', 'ATTFIELD', 'SADLER', 'SHIRREFFS']
    elite_j = ['ORTIZ', 'VELAZQUEZ', 'SAEZ', 'FRANCO', 'CASTELLANO',
               'ROSARIO', 'GAFFALIONE', 'GEROUX', 'PRAT', 'ESPINOZA',
               'GUTIERREZ', 'HERNANDEZ', 'TALAMO']
    classic_sires = ['INTO MISCHIEF', 'CURLIN', 'TAPIT', 'MEDAGLIA',
                     'WAR FRONT', 'QUALITY ROAD', 'AMERICAN PHAROAH',
                     'JUSTIFY', 'UNCLE MO', 'STREET SENSE', 'HONOR CODE',
                     'PIONEEROF', 'GUNNEVERA', 'NYQUIST', 'GORMLEY']

    with open(path) as f:
        for row in csv.reader(f):
            if not row: continue
            h = {}

            # === RACE INFO ===
            h['track']     = pf(row, 1)
            h['date']      = pf(row, 2)
            h['race']      = pf(row, 3)
            h['pgm']       = pf(row, 4)
            h['dist_y']    = num(row, 6)
            h['surface']   = pf(row, 7)
            h['race_type'] = pf(row, 9)
            h['purse']     = num(row, 12)

            # === TODAY'S CONNECTIONS ===
            h['trainer']        = pf(row, 28)
            h['trainer_starts'] = num(row, 29) or 0
            h['trainer_wins']   = num(row, 30) or 0
            h['jockey']         = pf(row, 33)
            h['jockey_starts']  = num(row, 35) or 0
            h['jockey_wins']    = num(row, 36) or 0
            h['ml_odds']        = num(row, 44)
            h['name']           = pf(row, 45)
            h['sex']            = pf(row, 49)
            h['weight']         = pf(row, 51)
            h['sire']           = pf(row, 52)
            h['sire_sire']      = pf(row, 53)
            h['dam_sire']       = pf(row, 55)

            # === LIFETIME STATS ===
            h['life_starts'] = num(row, 97) or 0
            h['life_wins']   = num(row, 98) or 0
            h['life_earn']   = num(row, 101) or 0

            # === TODAY'S RACE PARS ===
            h['par_2f']    = num(row, 214)
            h['par_4f']    = num(row, 215)
            h['par_6f']    = num(row, 216)
            h['speed_par'] = num(row, 217)
            h['par_late']  = num(row, 218)

            # === T/J COMBO ===
            h['tj_starts'] = num(row, 219) or 0
            h['tj_wins']   = num(row, 220) or 0
            h['tj_roi']    = num(row, 223)

            # === PRIME POWER ===
            h['prime_power'] = num(row, 251)

            # === PAST 10 RACES ===
            h['past_dates']     = [pf(row, 256 + i)  for i in range(10)]
            h['past_tracks']    = [pf(row, 276 + i)  for i in range(10)]
            h['past_cond']      = [pf(row, 306 + i)  for i in range(10)]
            h['past_dist']      = [num(row, 316 + i) for i in range(10)]
            h['past_surface']   = [pf(row, 326 + i)  for i in range(10)]
            h['past_entrants']  = [num(row, 346 + i) for i in range(10)]
            h['past_post']      = [num(row, 356 + i) for i in range(10)]
            h['past_race_name'] = [pf(row, 376 + i)  for i in range(10)]
            h['past_trip']      = [pf(row, 396 + i)  for i in range(10)]
            h['past_winner']    = [pf(row, 406 + i)  for i in range(10)]
            h['past_finish']    = [num(row, 616 + i) for i in range(10)]

            # === PACE FIGURES ===
            h['pace_2f']   = [num(row, 766 + i) for i in range(10)]
            h['pace_4f']   = [num(row, 776 + i) for i in range(10)]
            h['pace_late'] = [num(row, 816 + i) for i in range(10)]

            # === SPEED FIGURES ===
            h['bris_speed'] = [num(row, 846 + i) for i in range(10)]
            h['eq_speed']   = [num(row, 856 + i) for i in range(10)]

            # === TRAINER/JOCKEY HISTORY ===
            h['past_trainer']   = [pf(row, 1056 + i) for i in range(10)]
            h['past_jockey']    = [pf(row, 1066 + i) for i in range(10)]
            h['past_race_type'] = [pf(row, 1086 + i) for i in range(10)]

            # === PEDIGREE ===
            h['ped_dirt'] = num(row, 1264)
            h['ped_mud']  = num(row, 1265)
            h['ped_turf'] = num(row, 1266)
            h['ped_dist'] = num(row, 1267)

            # === BEST SPEEDS ===
            h['best_life'] = num(row, 1328)
            h['best_fast'] = num(row, 1178)
            h['best_off']  = num(row, 1180)
            h['best_dist'] = num(row, 1181)

            # === TRAINER SITUATIONAL STATS ===
            h['trnr_stats'] = []
            for i in range(6):
                base  = 1337 + i * 5
                cat   = pf(row, base)
                sts   = num(row, base + 1) or 0
                win_p = num(row, base + 2)
                itm   = num(row, base + 3)
                roi   = num(row, base + 4)
                if cat:
                    h['trnr_stats'].append(
                        {'cat': cat, 'starts': sts, 'win_pct': win_p, 'itm': itm, 'roi': roi})

            # === JOCKEY AT DISTANCE ===
            h['jky_dis_starts'] = num(row, 1368) or 0
            h['jky_dis_wins']   = num(row, 1369) or 0
            h['jky_dis_roi']    = num(row, 1372)

            # === EXTENDED TRIP NOTES ===
            h['ext_trip'] = [pf(row, 1383 + i) for i in range(5)]

            # ── R5 CALCULATIONS ──────────────────────────────────────────────

            # WS4: filter to today's surface only, fall back if < 2 same-surface races
            surf_today = normalize_surf(h['surface'])
            same_surf  = [s for s, surf in zip(h['bris_speed'], h['past_surface'])
                          if normalize_surf(surf) == surf_today and s and s > 0]
            if len(same_surf) < 2:
                same_surf = [s for s in h['bris_speed'] if s and s > 0]

            ws4   = calc_ws4(same_surf[:4])
            trend = calc_trend(same_surf[:4])
            fci   = (ws4 + trend) if ws4 else None

            fci_n = max(0.0, min(10.0, (fci - 60) / 6)) if fci else 0.0

            # CLASS vs speed par
            par = h['speed_par']
            h['debut'] = ws4 is None  # no BRIS speed figures on any surface
            if par and ws4:
                par_diff = ws4 - par
                class_n  = max(0.0, min(10.0, 5.0 + par_diff / 3))
            elif ws4 is None:
                # No speed figures — first-timer or debut on surface; class unknown
                class_n = 0.0
            else:
                # Has speed figures but no par (unclassified race type)
                g1_hist = any('G1' in r or 'Derby' in r or 'Oaks' in r
                              for r in h['past_race_name'] if r)
                class_n = 9.0 if g1_hist else 7.0

            # POST POSITION: track-aware scoring
            bias_style = TRACK_POST_BIAS.get(h['track'].upper(), 'neutral')
            try:
                post = int(h['pgm'])
                if bias_style == 'inside':
                    post_score = 8.0 if post <= 5 else (7.0 if post <= 9 else (6.0 if post <= 14 else 5.0))
                elif bias_style == 'outside':
                    post_score = 5.0 if post <= 4 else (7.0 if post <= 10 else 8.0)
                else:
                    post_score = 7.0 if post <= 9 else 6.0
            except:
                post_score = 6.0

            # TRAINER/JOCKEY: use actual win% from DRF data, fall back to elite list
            tj_n = 3.0
            t_starts = h['trainer_starts']
            t_wins   = h['trainer_wins']
            if t_starts >= 20:
                t_wp  = t_wins / t_starts
                tj_n += min(3.5, t_wp * 12)   # 30% win → +3.6, 20% → +2.4
            elif any(t in h['trainer'].upper() for t in elite_t):
                tj_n += 2.5

            j_starts = h['jockey_starts']
            j_wins   = h['jockey_wins']
            if j_starts >= 20:
                j_wp  = j_wins / j_starts
                tj_n += min(3.5, j_wp * 12)
            elif any(j in h['jockey'].upper() for j in elite_j):
                tj_n += 2.5

            if h['tj_starts'] >= 5 and h['tj_wins'] / max(h['tj_starts'], 1) > 0.2:
                tj_n = min(tj_n + 0.5, 10.0)
            tj_n = min(tj_n, 10.0)

            # FORM ANGLE: most recent same-surface figure
            recent = [s for s in same_surf[:3] if s > 0]
            form_n = 5.0
            if recent:
                if   recent[0] >= 100: form_n = 9.5
                elif recent[0] >= 95:  form_n = 8.5
                elif recent[0] >= 90:  form_n = 7.0
                elif recent[0] >= 85:  form_n = 6.0

            # PEDIGREE
            ped_n = 5.0
            if h['ped_dist'] and h['ped_dist'] > 0:
                ped_n = min(10.0, 4.0 + h['ped_dist'] / 25)
            elif h['ped_dirt'] and h['ped_dirt'] > 0:
                ped_n = min(10.0, 3.0 + h['ped_dirt'] / 30)
            else:
                if any(s in h['sire'].upper() for s in classic_sires):
                    ped_n = 7.0

            # Store all components (bias_n and val_n finalized in finalize_field)
            h['ws4']        = round(ws4, 1) if ws4 else None
            h['trend']      = trend
            h['fci']        = round(fci, 1) if fci else None
            h['fci_n']      = round(fci_n, 2)
            h['class_n']    = round(class_n, 2)
            h['par_diff']   = round(ws4 - par, 1) if (ws4 and par) else None
            h['post_score'] = post_score
            h['bias_n']     = post_score       # updated in finalize_field
            h['tj_n']       = round(tj_n, 1)
            h['form_n']     = round(form_n, 1)
            h['ped_n']      = round(ped_n, 1)
            h['val_n']      = 5.0              # updated in finalize_field
            h['pace_style'] = 'unknown'
            h['pace_fit']   = 5.0

            # Pre-finalize composite (val_n=5, bias_n=post only)
            pre = (fci_n       * 0.25 + class_n * 0.20 + post_score * 0.15 +
                   tj_n        * 0.10 + form_n  * 0.10 + ped_n      * 0.10 +
                   5.0         * 0.10)
            h['pre_comp'] = round(pre, 2)
            h['comp']     = h['pre_comp']
            h['tier']     = tier(h['comp'])

            horses.append(h)

    return horses


def finalize_field(horses):
    """
    Two-pass field-context scoring. Call once per race after parse_drf.
      Pass 1 — Pace fit: classify each horse's style, score vs field scenario.
               Blended 50/50 with post score into bias_n (15% weight).
      Pass 2 — Value: rank divergence between pre-composite model rank and ML odds.
      Final  — Recompute composite and tier.
    """
    if not horses:
        return horses

    # ── PASS 1: PACE FIT ─────────────────────────────────────────────────────
    for h in horses:
        e2   = [p for p in h['pace_2f'][:3]   if p and p > 0]
        late = [p for p in h['pace_late'][:3] if p and p > 0]
        if e2 and late:
            e_avg = sum(e2)   / len(e2)
            l_avg = sum(late) / len(late)
            if   e_avg > l_avg + 4: h['pace_style'] = 'speed'
            elif l_avg > e_avg + 4: h['pace_style'] = 'closer'
            else:                   h['pace_style'] = 'mid'
        else:
            h['pace_style'] = 'unknown'

    speed_ct = sum(1 for h in horses if h['pace_style'] == 'speed')

    for h in horses:
        style = h['pace_style']
        if speed_ct >= 5:       # hot pace — closers land
            pf_map = {'speed': 3.0, 'mid': 6.0, 'closer': 9.0, 'unknown': 5.0}
        elif speed_ct <= 1:     # slow pace — on-pace wins
            pf_map = {'speed': 9.0, 'mid': 6.5, 'closer': 4.0, 'unknown': 5.0}
        else:                   # normal pace
            pf_map = {'speed': 6.0, 'mid': 6.5, 'closer': 6.5, 'unknown': 5.0}

        h['pace_fit'] = pf_map[style]
        h['bias_n']   = round(0.5 * h['post_score'] + 0.5 * h['pace_fit'], 1)

    # ── PASS 2: VALUE = RANK DIVERGENCE ──────────────────────────────────────
    n       = len(horses)
    by_pre  = sorted(horses, key=lambda h: h['pre_comp'], reverse=True)
    model_rank = {h['name']: i + 1 for i, h in enumerate(by_pre)}

    with_odds  = [h for h in horses if h['ml_odds'] and h['ml_odds'] > 0]
    by_odds    = sorted(with_odds, key=lambda h: h['ml_odds'])
    odds_rank  = {h['name']: i + 1 for i, h in enumerate(by_odds)}

    for h in horses:
        mr  = model_rank.get(h['name'], n)
        or_ = odds_rank.get(h['name'], n // 2 + 1)
        diff = or_ - mr                             # positive = overlay (model ranks higher than market)
        # Floor at 5.0: overlays rewarded, underlays neutral — never penalise market favourites model ranks low
        h['val_n'] = round(max(5.0, min(10.0, 5.0 + diff * 0.7)), 1)

    # ── FINAL COMPOSITE ───────────────────────────────────────────────────────
    for h in horses:
        h['comp'] = round(
            h['fci_n']   * 0.25 +
            h['class_n'] * 0.20 +
            h['bias_n']  * 0.15 +
            h['tj_n']    * 0.10 +
            h['form_n']  * 0.10 +
            h['ped_n']   * 0.10 +
            h['val_n']   * 0.10, 2)
        h['tier'] = tier(h['comp'])

    return horses


def report(horses):
    ranked   = sorted(horses, key=lambda h: h['comp'], reverse=True)
    dist_f   = round(horses[0]['dist_y'] / 220, 1) if horses[0]['dist_y'] else '?'
    speed_ct = sum(1 for h in horses if h.get('pace_style') == 'speed')
    pace_label = (
        f"HOT PACE ({speed_ct} speed)" if speed_ct >= 5 else
        f"SLOW PACE ({speed_ct} speed)" if speed_ct <= 1 else
        f"NORMAL PACE ({speed_ct} speed)"
    )

    print("=" * 104)
    print(f"  🏇  R5 v3.4 — {horses[0]['track']}  Race {horses[0]['race']}  |  "
          f"{horses[0]['date']}  |  {dist_f}f  {horses[0]['surface']}  |  "
          f"Purse ${horses[0]['purse']:,.0f}  |  {pace_label}")
    print("=" * 104)
    print(f"\n{'#':<4} {'Horse':<22} {'ML':>5}  {'Spd 1-4':>22}  "
          f"{'WS4':>5}  {'T':>4}  {'FCI':>5}  {'vPar':>5}  "
          f"{'Ped':>4}  {'TJ':>4}  {'Pce':>4}  {'Val':>4}  {'Comp':>5}  Tier")
    print("-" * 104)

    for h in ranked:
        s4  = " ".join(f"{s:.0f}" if s else "--" for s in h['bris_speed'][:4])
        ml  = f"{h['ml_odds']:.0f}-1" if h['ml_odds'] else "?"
        ws  = f"{h['ws4']:.1f}"  if h['ws4']  else "N/A"
        fc  = f"{h['fci']:.1f}"  if h['fci']  else "N/A"
        vp  = f"{h['par_diff']:+.1f}" if h['par_diff'] is not None else "  ?"
        tr  = f"{h['trend']:+.1f}"
        pce = h.get('pace_style', '?')[:3].upper()
        debut_tag = "  [DEBUT]" if h.get('debut') else ""
        print(f"{h['pgm']:<4} {h['name']:<22} {ml:>5}  {s4:>22}  "
              f"{ws:>5}  {tr:>4}  {fc:>5}  {vp:>5}  "
              f"{h['ped_n']:>4.1f}  {h['tj_n']:>4.1f}  {pce:>4}  "
              f"{h['val_n']:>4.1f}  {h['comp']:>5.2f}  {h['tier']}{debut_tag}")

    print()

    # ── DEBUT WARNING ──
    debut_horses = [h for h in ranked if h.get('debut')]
    if debut_horses:
        names = ", ".join(f"#{h['pgm']} {h['name']}" for h in debut_horses)
        print(f"⚠️   DEBUT FLAG: {names} — no BRIS speed figures, class_n=0.0. Do not bet on class score alone.")
        print()

    # ── TIGHT CLUSTER WARNING ──
    if len(ranked) >= 3:
        cluster_spread = round(ranked[0]['comp'] - ranked[2]['comp'], 2)
        if cluster_spread <= 1.5:
            print(f"⚠️   TIGHT CLUSTER: top 3 within {cluster_spread} pts "
                  f"(#{ranked[0]['pgm']} {ranked[0]['comp']} / "
                  f"#{ranked[1]['pgm']} {ranked[1]['comp']} / "
                  f"#{ranked[2]['pgm']} {ranked[2]['comp']}) — "
                  f"low model conviction. Consider value alt over top pick.")
            print()

    # ── TOP WIN PICK ──
    top = ranked[0]
    print("=" * 104)
    print(f"🏆  TOP WIN PICK:  #{top['pgm']} {top['name']}  "
          f"[{top['ml_odds']:.0f}-1 ML]  |  Composite {top['comp']}  |  {top['tier']}")
    print(f"    Trainer: {top['trainer']}  |  Jockey: {top['jockey']}")
    print(f"    BRIS Speeds (last 4): {top['bris_speed'][:4]}  |  "
          f"WS4: {top['ws4']}  Trend: {top['trend']:+.1f}  FCI: {top['fci']}")
    if top['speed_par'] and top['par_diff'] is not None:
        print(f"    Speed Par for class: {top['speed_par']:.0f}  →  WS4 vs Par: {top['par_diff']:+.1f}")
    if top['prime_power']:
        print(f"    Prime Power Rating: {top['prime_power']:.1f}")
    if top['best_dist']:
        print(f"    Best BRIS @ distance: {top['best_dist']:.0f}")
    print(f"    Sire: {top['sire']}  |  Dist Ped: {top['ped_dist']}  |  Dirt Ped: {top['ped_dirt']}")
    print(f"    Pace style: {top.get('pace_style','?').upper()}  |  "
          f"Pace fit score: {top.get('pace_fit', 5):.1f}  |  Value score: {top['val_n']:.1f}")
    if top['trnr_stats']:
        print(f"    Key Trainer Situations:")
        for ts in top['trnr_stats'][:3]:
            wp  = f"{ts['win_pct']:.1f}%" if ts['win_pct'] else "?"
            roi = f"${ts['roi']:.2f}"     if ts['roi']     else "?"
            print(f"      • {ts['cat']}: {ts['starts']:.0f} starts  {wp} win  ROI {roi}")
    if top['past_race_name'][0]:
        print(f"    Last race: {top['past_race_name'][0]}  ({top['past_dates'][0]})")
    if top['ext_trip'][0]:
        print(f"    Trip note: {top['ext_trip'][0]}")
    print(f"    Min acceptable odds: {max((top['ml_odds'] or 2) - 1, 1):.0f}-1")

    print()

    # ── VALUE ALTERNATIVE (≥6-1 and ranked top-5) ──
    value_picks = [h for h in ranked[:8] if h['ml_odds'] and h['ml_odds'] >= 6
                   and h['name'] != top['name']]
    if value_picks:
        vp = value_picks[0]
        print(f"💰  VALUE ALT:  #{vp['pgm']} {vp['name']}  "
              f"[{vp['ml_odds']:.0f}-1 ML]  |  Composite {vp['comp']}  |  {vp['tier']}")
        print(f"    Trainer: {vp['trainer']}  |  Jockey: {vp['jockey']}")
        print(f"    Angle: {vp['ml_odds']:.0f}-1 ML with FCI {vp['fci']} vs par {vp['speed_par']} "
              f"| Pace: {vp.get('pace_style','?').upper()} | Val: {vp['val_n']:.1f}")
        if vp['prime_power']:
            print(f"    Prime Power: {vp['prime_power']:.1f}")
        if vp['trnr_stats']:
            ts = vp['trnr_stats'][0]
            wp = f"{ts['win_pct']:.1f}%" if ts['win_pct'] else "?"
            print(f"    Key stat: {ts['cat']} — {wp} win rate")
        if vp['ext_trip'][0]:
            print(f"    Trip: {vp['ext_trip'][0]}")

    print()

    # ── CONFIDENCE TIERS ──
    for t_label in ['HIGH', 'SOLID', 'FAIR', 'SPEC']:
        group = [h for h in ranked if h['tier'] == t_label]
        if group:
            names = "  ".join(f"#{h['pgm']}{h['name'][:10]}" for h in group)
            print(f"  {t_label:<6}: {names}")

    print()

    # ── PRIME POWER TOP 5 ──
    pp_ranked = sorted([h for h in horses if h['prime_power']],
                       key=lambda h: h['prime_power'], reverse=True)[:5]
    if pp_ranked:
        print("  PRIME POWER TOP 5:")
        for h in pp_ranked:
            print(f"    #{h['pgm']} {h['name']:<22} PP={h['prime_power']:.1f}  "
                  f"Comp={h['comp']:.2f}  Style={h.get('pace_style','?').upper()}")

    print()

    # ── EXOTICS ──
    t3pgm = [h['pgm'] for h in ranked[:3]]
    t6pgm = [h['pgm'] for h in ranked[3:6]]
    t6str = "  ".join(f"#{p}" for p in t6pgm)
    print("=" * 104)
    print("🎟️   EXOTICS STRUCTURE:")
    print(f"    WIN:        #{t3pgm[0]} {ranked[0]['name']}")
    print(f"    EXACTA:     #{t3pgm[0]} / #{t3pgm[1]}")
    print(f"    TRIFECTA:   #{t3pgm[0]} / #{t3pgm[1]} / #{t3pgm[2]}")
    print(f"    SUPERFECTA: #{t3pgm[0]} / #{t3pgm[1]} / #{t3pgm[2]} / {t6str}")
    print("=" * 104)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        _horses = parse_drf(sys.argv[1])
        _by_race = defaultdict(list)
        for _h in _horses:
            _by_race[_h['race']].append(_h)
        for _rh in _by_race.values():
            report(finalize_field(_rh))
    else:
        print("Usage: python3 r5_parser_v2.py <path_to_file.DRF>")
