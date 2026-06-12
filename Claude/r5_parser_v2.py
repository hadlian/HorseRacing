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
            h['ae_indicator']   = pf(row, 41)   # 'A'=also-eligible, 'M'=MTO
            h['ml_odds']        = num(row, 44)
            h['name']           = pf(row, 45)
            h['sex']            = pf(row, 49)
            h['weight']         = pf(row, 51)
            h['sire']           = pf(row, 52)
            h['sire_sire']      = pf(row, 53)
            h['dam_sire']       = pf(row, 55)
            h['program_post']   = pf(row, 58)   # updated post after early scratches
            h['medication']     = num(row, 62)  # 4=1st-time Lasix, 5=Bute+1st Lasix
            h['equipment_change'] = num(row, 64)  # 1=blinkers on, 2=blinkers off

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

            # === SESSION 3A DISPLAY FIELDS (parse/show/log only — never scored) ===
            dsl = num(row, 224)
            h['days_since_last'] = int(dsl) if dsl is not None else None  # None = debut
            style = pf(row, 210).upper().strip()
            h['bris_run_style'] = style if style in ('E', 'E/P', 'EP', 'P', 'S') else None
            if h['bris_run_style'] == 'EP':
                h['bris_run_style'] = 'E/P'
            qp = num(row, 211)
            h['quirin_pts'] = int(qp) if qp is not None else None
            h['wet_starts'] = int(num(row, 80) or 0)   # wet-track record block
            h['wet_wins']   = int(num(row, 81) or 0)
            h['wet_places'] = int(num(row, 82) or 0)
            h['wet_shows']  = int(num(row, 83) or 0)
            # best off-track speed = h['best_off'] (field 1180, parsed below)

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
            h['best_turf'] = num(row, 1179)
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

            # ── DERIVED FLAGS ────────────────────────────────────────────────
            # AE from DRF field 41 (supplements scout JSON when scout not run)
            if h['ae_indicator'] == 'A':
                h['also_eligible'] = True
            h['first_time_lasix'] = h['medication'] in (4.0, 5.0)

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

            # CLASS vs speed par (moved up — needed by fci_n)
            par = h['speed_par']

            if fci is None or fci <= 0:
                fci_n = 4.0  # debut/no figures — slight negative bias vs neutral 5.0
            else:
                par_eff = max(70.0, min(105.0, par)) if par else 78.0
                fci_n = max(0.0, min(10.0, 5.0 + (fci - par_eff) / 5.0))
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
            # Use program_post (field 58, updated after early scratches) when available
            bias_style = TRACK_POST_BIAS.get(h['track'].upper(), 'neutral')
            try:
                post_raw = (h.get('program_post') or '').strip() or h['pgm']
                post = int(post_raw)
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

            # === NEW NORMALIZED COMPONENTS (v3.5 / updated v3.6) ===

            # best_dist_n: surface-aware best BRIS speed, normalized to 0–10
            # Turf races use best_turf (field 1179); others use best_dist (field 1181)
            # Fallback: fci_n (so missing data doesn't crater composite)
            if surf_today == 'T' and h.get('best_turf') and h['best_turf'] > 0:
                bd = h['best_turf']
            else:
                bd = h['best_dist']
            if bd and bd > 0:
                par_eff_bd = max(70.0, min(105.0, par)) if par else 78.0
                best_dist_n = max(0.0, min(10.0, 5.0 + (bd - par_eff_bd) / 5.0))
            else:
                best_dist_n = fci_n  # fallback to new par-anchored fci_n

            # pp_n: Prime Power rating, normalized to 0–10
            # Anchor at 125 (empirical median of 1,168-horse DB). Debut fallback 4.0
            # matches fci_n debut treatment — data vacuum is a mild liability, not neutral.
            pp = h['prime_power']
            if pp and pp > 0:
                pp_n = max(0.0, min(10.0, 5.0 + (pp - 125) / 6))
            else:
                pp_n = 4.0

            # Store all components (bias_n and val_n finalized in finalize_field)
            h['ws4']          = round(ws4, 1) if ws4 else None
            h['trend']        = trend
            h['fci']          = round(fci, 1) if fci else None
            h['fci_n']        = round(fci_n, 2)
            h['class_n']      = round(class_n, 2)
            h['par_diff']     = round(ws4 - par, 1) if (ws4 and par) else None
            h['post_score']   = post_score
            h['bias_n']       = post_score       # updated in finalize_field
            h['tj_n']         = round(tj_n, 1)
            h['form_n']       = round(form_n, 1)
            h['ped_n']        = round(ped_n, 1)
            h['val_n']        = 5.0              # updated in finalize_field
            h['best_dist_n']  = round(best_dist_n, 2)
            h['pp_n']         = round(pp_n, 2)
            h['pace_style']   = 'unknown'
            h['pace_fit']     = 5.0

            # Pre-finalize composite (val_n=5.0, bias_n=post only) — v3.5 weights
            pre = (fci_n        * 0.22 + class_n * 0.20 + post_score   * 0.08 +
                   tj_n         * 0.15 + form_n  * 0.10 + ped_n        * 0.07 +
                   best_dist_n  * 0.08 + pp_n    * 0.05 + 5.0          * 0.05)
            h['pre_comp'] = round(pre, 2)
            h['comp']     = h['pre_comp']
            h['tier']     = tier(h['comp'])

            horses.append(h)

    return horses


# v3.10 composite weights. Single source of truth for downstream consumers
# (probability layer, reconstruction). val_n is listed but BANNED from P(win):
# comp_ex_val renormalizes the other eight by exact division by 0.95.
COMP_WEIGHTS = {"fci_n": 0.22, "class_n": 0.20, "tj_n": 0.15, "form_n": 0.10,
                "bias_n": 0.08, "best_dist_n": 0.08, "ped_n": 0.07,
                "pp_n": 0.05, "val_n": 0.05}


def compute_comp_ex_val(h):
    """
    Market-free composite for the P(win) layer (Session 2, Task 4).
    Pure renormalized weighted sum of the 8 non-val components — by
    construction excludes val_n (market-relative), scout/equipment
    adjustments, and the tight-cluster deduction.
    Returns None if any component is missing (pre-v3.5 rows).
    """
    total = 0.0
    for comp, w in COMP_WEIGHTS.items():
        if comp == "val_n":
            continue
        v = h.get(comp) if isinstance(h, dict) else h[comp]
        if v is None:
            return None
        total += v * (w / 0.95)
    return round(total, 2)


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

    # ── FINAL COMPOSITE — v3.5 weights (fci_n/best_dist_n updated v3.6) ─────
    for h in horses:
        h['comp'] = round(
            h['fci_n']        * 0.22 +
            h['class_n']      * 0.20 +
            h['tj_n']         * 0.15 +
            h['best_dist_n']  * 0.08 +
            h['pp_n']         * 0.05 +
            h['form_n']       * 0.10 +
            h['ped_n']        * 0.07 +
            h['bias_n']       * 0.08 +
            h['val_n']        * 0.05, 2)
        h['tier'] = tier(h['comp'])

    # ── v3.8 — FIRST-TIME LASIX / EQUIPMENT ADJUSTMENTS ─────────────────────
    # Applied after composite so val_n rank divergence is unaffected.
    # Caps: +0.20 Lasix, +0.10 blinkers on, -0.05 blinkers off (not capped vs scout)
    for h in horses:
        adj = 0.0
        if h.get('first_time_lasix'):
            adj += 0.20
        ec = h.get('equipment_change')
        if ec == 1.0:
            adj += 0.10
        elif ec == 2.0:
            adj -= 0.05
        if adj:
            h['equipment_adj'] = round(adj, 2)
            h['comp'] = round(h['comp'] + adj, 2)
            h['tier'] = tier(h['comp'])

    # ── SCOUT ADJUSTMENTS (Option A — applied before finalize so tight cluster sees them) ──
    # apply_scout_adjustments ran before finalize_field and stored h['scout_adj'].
    # finalize recomputes comp from scratch, so we re-add the stored adj here.
    for h in horses:
        sa = h.get('scout_adj', 0.0)
        if sa:
            h['comp'] = round(h['comp'] + sa, 2)
            h['tier'] = tier(h['comp'])

    # ── comp_ex_val for the P(win) layer (computed before the deduction;
    #    value is deduction/adjustment-independent by construction) ──────────
    for h in horses:
        h['comp_ex_val'] = compute_comp_ex_val(h)

    # ── ISSUE 6 v3.7 — TIGHT CLUSTER DEDUCTION (2026-05-28) ─────────────────
    # Evidence (99-race DB):
    #   spread ≤0.5: Rank 1 wins 17.1% | Rank 2 wins 25.7%  ← Rank 2 BEATS Rank 1
    #   spread 0.5-1.5: normal (Rank 1 wins ~25%)
    #   spread >1.5: high conviction (Rank 1 wins 50.0%)
    # Action: when spread ≤0.5, apply -0.40 deduction to top horse only.
    # This typically slips top horse one tier (HIGH→SOLID, SOLID→FAIR, FAIR→SPEC)
    # so downstream consumers (CLI, webapp PLAY/NEAR/SKIP, DB) all see the
    # reduced confidence. May also swap Rank 1↔Rank 2 when both are close,
    # which is the desired behaviour given the win-rate data.
    if len(horses) >= 3:
        ranked_by_comp = sorted(horses, key=lambda h: h['comp'], reverse=True)
        spread_top3 = round(ranked_by_comp[0]['comp'] - ranked_by_comp[2]['comp'], 2)
        if spread_top3 <= 0.5:
            top = ranked_by_comp[0]
            top['tight_cluster_severe'] = True
            top['tight_cluster_spread'] = spread_top3
            top['pre_tight_comp']       = top['comp']
            top['comp'] = round(top['comp'] - 0.40, 2)
            top['tier'] = tier(top['comp'])
            # Tag top 3 with a moderate flag so UI/exotics can downweight win plays
            for h in ranked_by_comp[:3]:
                h['tight_cluster_flag'] = True

    # ── P(win) layer (Session 2, Task 6) — conditional logit on comp_ex_val.
    #    Requires a fitted β (Results/logit_beta.json); degrades gracefully. ──
    try:
        from r5_probability import load_beta, score_field
        score_field(horses, load_beta())
    except Exception:
        for h in horses:
            h.setdefault('p_win', None)
            h.setdefault('fair_odds', None)
            h.setdefault('ml_edge', None)
            h.setdefault('is_overlay', 0)

    return horses


def layoff_tag(days):
    """Session 3A Task 1 display tag. None (debut) handled by [DEBUT]."""
    if days is None:
        return ""
    if days >= 180:
        return "  [LAYOFF 180+]"
    if days >= 90:
        return "  [LAYOFF 90+]"
    if days >= 45:
        return "  [LAYOFF 45+]"
    return ""


# trainer situational categories that pair with layoff / debut display
LAYOFF_CATS = ("daysaway", "days away", "layoff")
DEBUT_CATS  = ("1st time", "first time", "debut", "1st start", "firststr",
               "1st  str", "1st str")


def report(horses, wet=False):
    ranked   = sorted(horses, key=lambda h: h['comp'], reverse=True)
    dist_f   = round(horses[0]['dist_y'] / 220, 1) if horses[0]['dist_y'] else '?'
    speed_ct = sum(1 for h in horses if h.get('pace_style') == 'speed')
    pace_label = (
        f"HOT PACE ({speed_ct} speed)" if speed_ct >= 5 else
        f"SLOW PACE ({speed_ct} speed)" if speed_ct <= 1 else
        f"NORMAL PACE ({speed_ct} speed)"
    )

    print("=" * 118)
    par_val = horses[0].get('speed_par')
    par_str = f"Par {par_val:.0f}" if par_val else "Par N/A"
    purse_str = f"${horses[0]['purse']:,.0f}" if horses[0]['purse'] else "N/A"
    print(f"  🏇  R5 v3.10 — {horses[0]['track']}  Race {horses[0]['race']}  |  "
          f"{horses[0]['date']}  |  {dist_f}f  {horses[0]['surface']}  |  "
          f"Purse {purse_str}  |  {par_str}  |  {pace_label}")

    # ── RACE HEADER (Decision 1D): top-3 cum P(win), spread, shape ──────────
    top3   = ranked[:3]
    cum_p  = sum(h['p_win'] for h in top3 if h.get('p_win')) if top3 else None
    spread13 = round(ranked[0]['comp'] - ranked[2]['comp'], 2) if len(ranked) >= 3 else None
    spread12 = round(ranked[0]['comp'] - ranked[1]['comp'], 2) if len(ranked) >= 2 else None
    if spread13 is not None and spread13 <= 0.5:
        shape = "TIGHT"
    elif spread12 is not None and spread12 >= 1.0:
        shape = "STANDOUT"
    else:
        shape = "DEFAULT"
    hdr_bits = []
    if cum_p:
        hdr_bits.append(f"top-3 cum P(win) {cum_p*100:.0f}%")
    if spread13 is not None:
        hdr_bits.append(f"spread(r1−r3) {spread13} {shape}")
    # Session 3A Task 2: BRIS pace profile (E/EP early types vs P/S)
    n_eep = sum(1 for h in horses if h.get('bris_run_style') in ('E', 'E/P'))
    n_ps  = sum(1 for h in horses if h.get('bris_run_style') in ('P', 'S'))
    if n_eep or n_ps:
        hdr_bits.append(f"pace profile {n_eep}E/EP vs {n_ps}P/S")
    if hdr_bits:
        print(f"  R5 | {' | '.join(hdr_bits)}")
    print("=" * 125)
    print(f"\n{'#':<4} {'Horse':<29} {'ML':>5}  {'Spd 1-4':>22}  "
          f"{'WS4':>5}  {'T':>4}  {'FCI':>5}  {'vPar':>5}  "
          f"{'Ped':>4}  {'TJ':>4}  {'Pce':>4}  {'Q':>2}  {'BDn':>4}  {'PPn':>4}  {'Val':>4}  "
          f"{'Comp':>5}  {'P(win)':>6}  {'Fair':>6}  {'Edge':>6}")
    print("-" * 125)

    for h in ranked:
        s4  = " ".join(f"{s:.0f}" if s else "--" for s in h['bris_speed'][:4])
        ml  = f"{h['ml_odds']:.0f}-1" if h['ml_odds'] else "?"
        ws  = f"{h['ws4']:.1f}"  if h['ws4']  else "N/A"
        fc  = f"{h['fci']:.1f}"  if h['fci']  else "N/A"
        vp  = f"{h['par_diff']:+.1f}" if h['par_diff'] is not None else "  ?"
        tr  = f"{h['trend']:+.1f}"
        pce = h.get('pace_style', '?')[:3].upper()
        qp  = f"{h['quirin_pts']}" if h.get('quirin_pts') is not None else "-"
        sty = h.get('bris_run_style')
        name_sty = f"{h['name']} ({sty})" if sty else h['name']
        pw  = f"{h['p_win']*100:.0f}%"        if h.get('p_win')    else "  --"
        fo  = f"{h['fair_odds']:.1f}-1"       if h.get('fair_odds') else "  --"
        ed  = f"{h['ml_edge']*100:+.0f}%"     if h.get('ml_edge') is not None else "  --"
        debut_tag = "  [DEBUT]"    if h.get('debut') else ""
        ae_tag    = "  [AE]"       if h.get('also_eligible') else ""
        ftl_tag   = "  [1stLasix]" if h.get('first_time_lasix') else ""
        ec = h.get('equipment_change')
        blk_tag   = "  [BlkON]" if ec == 1.0 else ("  [BlkOFF]" if ec == 2.0 else "")
        ovl_tag   = "  ▲OVERLAY"   if h.get('is_overlay') else ""
        val_tag   = "  ◆VAL WATCH" if (h.get('val_n') or 0) >= 8.0 else ""
        lay_tag   = layoff_tag(h.get('days_since_last'))
        print(f"{h['pgm']:<4} {name_sty:<29} {ml:>5}  {s4:>22}  "
              f"{ws:>5}  {tr:>4}  {fc:>5}  {vp:>5}  "
              f"{h['ped_n']:>4.1f}  {h['tj_n']:>4.1f}  {pce:>4}  {qp:>2}  "
              f"{h['best_dist_n']:>4.1f}  {h['pp_n']:>4.1f}  "
              f"{h['val_n']:>4.1f}  {h['comp']:>5.2f}  {pw:>6}  {fo:>6}  {ed:>6}"
              f"{ovl_tag}{val_tag}{debut_tag}{lay_tag}{ae_tag}{ftl_tag}{blk_tag}")

    # Session 3A Task 4: wet-track lines, only when the user flags an off track
    if wet:
        print()
        print("🌧  OFF-TRACK CONDITION FLAGGED — wet form for top-3 contenders:")
        for h in ranked[:3]:
            if h.get('wet_starts', 0) > 0:
                bo = (f", best off-track {h['best_off']:.0f}"
                      if h.get('best_off') and h['best_off'] > 0 else "")
                print(f"    #{h['pgm']} {h['name']}: WET {h['wet_wins']}-for-"
                      f"{h['wet_starts']}{bo}")
            else:
                print(f"    #{h['pgm']} {h['name']}: WET first off-track start")

    print()
    if any(h.get('is_overlay') for h in ranked):
        print("▲ OVERLAY = model edge ≥ +25% with P(win) ≥ 8% — vs morning line; "
              "advisory until live odds (no win bets on this flag).")
        print()
    if any((h.get('val_n') or 0) >= 8.0 for h in ranked):
        print("◆ VAL WATCH = val_n ≥ 8 tracker qualifier (flat $2, max 2/card, "
              "hard-stop guardrails per ruling).")
        print()

    # ── DEBUT WARNING ──
    debut_horses = [h for h in ranked if h.get('debut')]
    if debut_horses:
        names = ", ".join(f"#{h['pgm']} {h['name']}" for h in debut_horses)
        print(f"⚠️   DEBUT FLAG: {names} — no BRIS speed figures, class_n=0.0. Do not bet on class score alone.")
        print()

    # ── ALSO-ELIGIBLE WARNING (Scout-3 fix, 2026-05-28) ──
    ae_horses = [h for h in ranked if h.get('also_eligible')]
    if ae_horses:
        names = ", ".join(f"#{h['pgm']} {h['name']}" for h in ae_horses)
        print(f"⏳  ALSO-ELIGIBLE: {names} — on wait list; will only run if a regular entrant scratches. "
              f"Confirm gate status at MTP before betting.")
        print()

    # ── TIGHT CLUSTER WARNING (v3.7 two-tier — Issue 6 fix) ──
    if len(ranked) >= 3:
        # Severity is a property of the original Rank 1, not the current top
        # (deduction may have swapped Rank 1 ↔ Rank 2). Find the deducted horse.
        demoted = next((h for h in ranked if h.get('tight_cluster_severe')), None)
        rank2_comp = ranked[1]['comp']
        rank3_comp = ranked[2]['comp']
        current_spread = round(ranked[0]['comp'] - ranked[2]['comp'], 2)

        if demoted:
            # ≤0.5 spread — Rank 2 historically wins more than Rank 1 here.
            pre_top         = demoted['pre_tight_comp']
            original_spread = demoted.get('tight_cluster_spread', current_spread)
            top_now         = ranked[0]
            swapped         = (top_now['pgm'] != demoted['pgm'])
            print(f"🚨  VERY TIGHT CLUSTER: original top 3 within {original_spread} pts — "
                  f"model conviction very low.")
            print(f"     #{demoted['pgm']} {demoted['name']} comp deducted -0.40 "
                  f"({pre_top} → {demoted['comp']}).")
            if swapped:
                print(f"     → Top pick promoted to #{top_now['pgm']} {top_now['name']} "
                      f"(comp {top_now['comp']}).")
            print(f"     Exact revalidation (33 fired races, 2026-06-11): post-deduction "
                  f"rank-1 25.9% win / −1.3% ROI vs demoted horse −43.3%.")
            print(f"     → Structure: box the cluster, don't key it (see EXOTICS below).")
            print()
        elif current_spread <= 1.5:
            # Moderate-tight — show advisory only, no deduction
            print(f"⚠️   TIGHT CLUSTER: top 3 within {current_spread} pts "
                  f"(#{ranked[0]['pgm']} {ranked[0]['comp']} / "
                  f"#{ranked[1]['pgm']} {rank2_comp} / "
                  f"#{ranked[2]['pgm']} {rank3_comp}) — "
                  f"moderate conviction. Consider value alt over top pick.")
            print()

    # ── TOP WIN PICK ──
    top = ranked[0]
    ml_hdr = f"{top['ml_odds']:.0f}-1 ML" if top['ml_odds'] else "N/A ML"
    print("=" * 118)
    pw_hdr = (f"P(win) {top['p_win']*100:.0f}%  |  fair {top['fair_odds']:.1f}-1"
              if top.get('p_win') else "P(win) n/a")
    edge_hdr = (f"  |  edge {top['ml_edge']*100:+.0f}%"
                + ("  ▲OVERLAY (advisory — vs ML)" if top.get('is_overlay') else "")
                if top.get('ml_edge') is not None else "")
    print(f"🏆  TOP WIN PICK:  #{top['pgm']} {top['name']}  "
          f"[{ml_hdr}]  |  Composite {top['comp']}  |  {pw_hdr}{edge_hdr}")
    print(f"    Trainer: {top['trainer']}  |  Jockey: {top['jockey']}")
    print(f"    BRIS Speeds (last 4): {top['bris_speed'][:4]}  |  "
          f"WS4: {top['ws4']}  Trend: {top['trend']:+.1f}  FCI: {top['fci']}")
    if top['speed_par'] and top['par_diff'] is not None:
        print(f"    Speed Par for class: {top['speed_par']:.0f}  →  WS4 vs Par: {top['par_diff']:+.1f}")
    if top['prime_power']:
        print(f"    Prime Power Rating: {top['prime_power']:.1f}")
    surf_top = normalize_surf(top.get('surface', ''))
    if surf_top == 'T' and top.get('best_turf'):
        print(f"    Best BRIS Turf: {top['best_turf']:.0f}")
    elif top['best_dist']:
        print(f"    Best BRIS @ distance: {top['best_dist']:.0f}")
    if top.get('first_time_lasix'):
        print(f"    ⚡ FIRST-TIME LASIX (+0.20 comp)")
    ec_top = top.get('equipment_change')
    if ec_top == 1.0:
        print(f"    🔧 BLINKERS ON (+0.10 comp)")
    elif ec_top == 2.0:
        print(f"    🔧 BLINKERS OFF (−0.05 comp)")
    print(f"    Sire: {top['sire']}  |  Dist Ped: {top['ped_dist']}  |  Dirt Ped: {top['ped_dirt']}")
    print(f"    Pace style: {top.get('pace_style','?').upper()}  |  "
          f"Pace fit score: {top.get('pace_fit', 5):.1f}  |  Value score: {top['val_n']:.1f}")
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
        vp_pw = (f"  |  P(win) {vp['p_win']*100:.0f}%  fair {vp['fair_odds']:.1f}-1"
                 if vp.get('p_win') else "")
        print(f"💰  VALUE ALT:  #{vp['pgm']} {vp['name']}  "
              f"[{vp['ml_odds']:.0f}-1 ML]  |  Composite {vp['comp']}{vp_pw}")
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

    # ── TRAINER ANGLES — contender set (Session 3A Task 3, display only) ────
    angle_lines = []
    for h in ranked[:3]:
        stats = [ts for ts in h.get('trnr_stats', [])
                 if (ts.get('starts') or 0) > 0 or ts.get('roi')]
        if not stats:
            continue
        dsl = h.get('days_since_last')
        hdr_tag = layoff_tag(dsl).strip()
        if h.get('debut'):
            hdr_tag = "[DEBUT]"
        dsl_str = f"  ({dsl}d since last)" if dsl is not None else ""
        angle_lines.append(f"    #{h['pgm']} {h['name']}{dsl_str}"
                           + (f"  {hdr_tag}" if hdr_tag else ""))
        for ts in stats:
            cat_l = ts['cat'].lower()
            mark = ""
            if (dsl is not None and dsl >= 45
                    and any(k in cat_l for k in LAYOFF_CATS)):
                mark = "  ← LAYOFF MATCH"
            elif h.get('debut') and any(k in cat_l for k in DEBUT_CATS):
                mark = "  ← DEBUT MATCH"
            wp  = f"{ts['win_pct']:.0f}%" if ts['win_pct'] else "?"
            roi = f"${ts['roi']:.2f}"     if ts['roi'] is not None else "?"
            angle_lines.append(f"        • {ts['cat']}: {ts['starts']:.0f} sts"
                               f"  {wp} win  ROI {roi}{mark}")
    if angle_lines:
        print("  📋 TRAINER ANGLES — contender set (small-n context, not signals):")
        for line in angle_lines:
            print(line)
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
    print("=" * 114)
    print("🎟️   EXOTICS STRUCTURE:")
    print(f"    WIN:        #{t3pgm[0]} {ranked[0]['name']}")
    if len(ranked) >= 2:
        print(f"    EXACTA:     #{t3pgm[0]} / #{t3pgm[1]}")
    if len(ranked) >= 3:
        print(f"    TRIFECTA:   #{t3pgm[0]} / #{t3pgm[1]} / #{t3pgm[2]}")
        print(f"    SUPERFECTA: #{t3pgm[0]} / #{t3pgm[1]} / #{t3pgm[2]} / {t6str}")
    print("=" * 114)


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
