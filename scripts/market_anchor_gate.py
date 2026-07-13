#!/usr/bin/env python3
"""
Market-anchored conditional-logit falsification gate (Fable round-2 spec).

Question: does the market-blind fundamental score (comp_ex_val) carry win
information ORTHOGONAL to the closing market? i.e. is beta != 0 in a per-race
conditional logit  u_i = alpha*log(q_i) + beta*z_i , where q_i is the closing
implied probability and z_i is comp_ex_val standardized within race?

Pre-registered decision rule (OOS mean dLL per race, leave-one-card-out CV):
  dLL <= 0            OR beta CI spans 0 w/ point <= 0.05  -> NO-GO (re-run @ ~300, else ABANDON)
  0 < dLL < 0.02                                           -> INSUFFICIENT (re-run @ ~300)
  dLL >= 0.02 AND 90% bootstrap CI excludes 0             -> GO (offline calibration; still frozen)

No wagering implication. Offline research fit only.
"""
import os, sys, sqlite3, math, random
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Claude"))
from r5_paths import R5_DB_PATH
DB = str(R5_DB_PATH)
random.seed(12345)

# ---------- data ----------
def load_races():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; cur = c.cursor()
    out = []
    rs = cur.execute("SELECT id,track,date FROM races WHERE result_fetched=1 AND is_backtest=0 "
                     "AND (has_coupled_entry=0 OR has_coupled_entry IS NULL)").fetchall()
    for r in rs:
        rid = r["id"]
        ran = cur.execute("SELECT horse_pgm,finish_position,final_tote_odds FROM race_finish_order "
                          "WHERE race_id=? AND finish_position IS NOT NULL AND is_late_scratch=0", (rid,)).fetchall()
        if len(ran) < 4:                        continue
        if any(x["final_tote_odds"] is None for x in ran): continue
        winners = [x for x in ran if x["finish_position"] == 1]
        if len(winners) != 1:                   continue   # drop dead-heat-for-win
        horses = []
        ok = True
        for x in ran:
            p = cur.execute("SELECT comp_ex_val FROM picks WHERE race_id=? AND pgm=? AND finish_pos!=-1",
                            (rid, str(x["horse_pgm"]))).fetchone()
            if not p or p["comp_ex_val"] is None: ok = False; break
            q = 1.0 / (x["final_tote_odds"] + 1.0)          # closing implied prob
            horses.append({"logq": math.log(q), "comp": p["comp_ex_val"],
                           "win": 1 if x["finish_position"] == 1 else 0})
        if not ok:                              continue
        # standardize comp within race (z); center logq within race (cancels in CL, aids conditioning)
        mc = sum(h["comp"] for h in horses) / len(horses)
        sd = (sum((h["comp"]-mc)**2 for h in horses)/len(horses))**0.5
        ml = sum(h["logq"] for h in horses)/len(horses)
        for h in horses:
            h["z"]  = (h["comp"]-mc)/sd if sd > 1e-9 else 0.0
            h["lq"] = h["logq"] - ml
        out.append({"card": f"{r['track']}_{r['date']}", "track": r["track"], "horses": horses})
    c.close()
    return out

# ---------- conditional logit (pure-python Newton) ----------
def _race_ll_grad_hess(horses, theta, cols):
    # u_i = sum_k theta_k * x_i[col_k]; returns (ll, grad[K], hess[K][K]) for this race
    K = len(theta)
    us = []
    for h in horses:
        u = sum(theta[k]*h[cols[k]] for k in range(K)); us.append(u)
    m = max(us); Z = sum(math.exp(u-m) for u in us); logZ = m + math.log(Z)
    P = [math.exp(u-logZ) for u in us]
    win = next(i for i,h in enumerate(horses) if h["win"])
    ll = us[win] - logZ
    ex = [sum(P[i]*horses[i][cols[k]] for i in range(len(horses))) for k in range(K)]  # E_P[x_k]
    grad = [horses[win][cols[k]] - ex[k] for k in range(K)]
    hess = [[0.0]*K for _ in range(K)]
    for k in range(K):
        for l in range(K):
            cov = sum(P[i]*horses[i][cols[k]]*horses[i][cols[l]] for i in range(len(horses))) - ex[k]*ex[l]
            hess[k][l] = -cov
    return ll, grad, hess

def fit(races, cols, iters=50, tol=1e-8):
    K = len(cols); theta = [0.0]*K
    for _ in range(iters):
        g = [0.0]*K; H = [[0.0]*K for _ in range(K)]; ll = 0.0
        for r in races:
            l, gr, he = _race_ll_grad_hess(r["horses"], theta, cols)
            ll += l
            for k in range(K):
                g[k] += gr[k]
                for j in range(K): H[k][j] += he[k][j]
        step = _solve(H, g)           # Newton: theta -= H^-1 g  (H is neg-def -> minus)
        mx = 0.0
        for k in range(K):
            theta[k] -= step[k]; mx = max(mx, abs(step[k]))
        if mx < tol: break
    return theta, ll

def _solve(H, g):
    # solve H x = g for small K (1 or 2) directly
    K = len(g)
    if K == 1:
        return [g[0]/H[0][0]]
    a,b,c,d = H[0][0],H[0][1],H[1][0],H[1][1]
    det = a*d - b*c
    return [(d*g[0]-b*g[1])/det, (-c*g[0]+a*g[1])/det]

def loglik(races, cols, theta):
    return sum(_race_ll_grad_hess(r["horses"], theta, cols)[0] for r in races)

# ---------- CV / bootstrap ----------
def leave_one_card_out(races):
    cards = defaultdict(list)
    for r in races: cards[r["card"]].append(r)
    per_race_dll = []
    for card, held in cards.items():
        train = [r for r in races if r["card"] != card]
        tA,_ = fit(train, ["lq"]); tB,_ = fit(train, ["lq","z"])
        for r in held:
            llA = loglik([r], ["lq"], tA); llB = loglik([r], ["lq","z"], tB)
            per_race_dll.append(llB - llA)
    return per_race_dll

def boot_ci(vals, n=2000, lo=5, hi=95):
    means = []
    N = len(vals)
    for _ in range(n):
        s = [vals[random.randrange(N)] for _ in range(N)]
        means.append(sum(s)/N)
    means.sort()
    return means[int(lo/100*n)], means[int(hi/100*n)]

def boot_beta(races, n=2000, lo=5, hi=95):
    betas = []
    N = len(races)
    for _ in range(n):
        s = [races[random.randrange(N)] for _ in range(N)]
        try:
            tB,_ = fit(s, ["lq","z"]); betas.append(tB[1])
        except ZeroDivisionError:
            continue
    betas.sort(); m = len(betas)
    return betas[int(lo/100*m)], betas[int(hi/100*m)]

# ---------- run ----------
def main():
    races = load_races()
    n = len(races)
    print(f"Gate dataset: {n} races (complete closing odds + full comp_ex_val join, no coupled, single winner)\n")

    tA, llA = fit(races, ["lq"]);        tB, llB = fit(races, ["lq","z"])
    lr = 2*(llB - llA)
    print("IN-SAMPLE FIT")
    print(f"  A (market only)   alpha={tA[0]:+.3f}   LL={llA:.2f}")
    print(f"  B (market+comp)   alpha={tB[0]:+.3f}  beta={tB[1]:+.3f}   LL={llB:.2f}")
    print(f"  LR stat (df=1) = {lr:.2f}   (chi2 .05 crit=3.84, .01=6.63)")
    b90 = boot_beta(races, 2000, 5, 95); b95 = boot_beta(races, 2000, 2.5, 97.5)
    print(f"  beta 90% CI [{b90[0]:+.3f}, {b90[1]:+.3f}]   95% CI [{b95[0]:+.3f}, {b95[1]:+.3f}]\n")

    dll = leave_one_card_out(races)
    mean_dll = sum(dll)/len(dll)
    ci = boot_ci(dll, 2000, 5, 95)
    print("OUT-OF-SAMPLE (leave-one-card-out CV)")
    print(f"  mean dLL/race = {mean_dll:+.4f} nats   90% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print(f"  McFadden dR2 ~ {mean_dll/2.2:+.4f}\n")

    # SAR sub-result: train non-SAR, test SAR
    nonsar = [r for r in races if r["track"] != "SAR"]; sar = [r for r in races if r["track"] == "SAR"]
    if sar and nonsar:
        tA2,_ = fit(nonsar, ["lq"]); tB2,_ = fit(nonsar, ["lq","z"])
        sdll = [loglik([r],["lq","z"],tB2) - loglik([r],["lq"],tA2) for r in sar]
        print(f"SAR fold (train non-SAR n={len(nonsar)} -> test SAR n={len(sar)})")
        print(f"  mean dLL/race (SAR) = {sum(sdll)/len(sdll):+.4f} nats\n")

    print("DECISION RULE")
    go = mean_dll >= 0.02 and ci[0] > 0
    nogo = mean_dll <= 0 or (b90[0] <= 0 <= b90[1] and tB[1] <= 0.05)
    verdict = "GO" if go else ("NO-GO" if nogo else "INSUFFICIENT")
    print(f"  -> {verdict}")
    if verdict != "GO":
        print("     (per rule: re-run once at ~300 joined races; ABANDON if still not GO)")

if __name__ == "__main__":
    main()
