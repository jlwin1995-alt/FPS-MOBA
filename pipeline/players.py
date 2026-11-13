"""Which players consistently beat or miss the line / the published projection?   python -m pipeline.players [--min-n 8]
Reads every settled leg in site/data/log (FPS and MOBA). The unit is the player-match (several legs of one player in one match share the same game):
for each player, match and prop type (kills / headshots) the legs' relative errors are averaged, error = actual / line - 1 and actual / projection - 1.
Per player: matches, mean error against the line and against the projection (each with a standard error over matches), the share of legs over the line,
and an empirical-Bayes shrunk estimate toward zero (a 3-match hot streak is mostly noise; the shrink factor is fitted on this data, not assumed).
A player is FLAGGED when he has at least --min-n matches and the shrunk error against the line is at least 1.5 standard errors from zero.
Persistence test (the part that matters): walk forward through the slates; before each slate a player is "over-performer" / "under-performer" if his
shrunk past error against the line is positive / negative with at least --min-n past matches; the next slate's legs for flagged players are then scored.
Output: data/players/players.json and a printed report. Descriptive logging, not a rule: a rule would be registered in evaluate.py first."""
import argparse, glob, json, math, os, statistics as st
from collections import defaultdict

from .names import norm

LOG = "site/data/log"


def title_of(row, sec):
    if row.get("Title"):
        return row["Title"]
    m = row.get("Match", "")
    return m.split(" · ")[0].replace(" [NO MARKET]", "").strip() or sec.upper()


def settled_legs(log_dir=LOG):
    """[{slate, title, player, key, kind, match, line, proj, act, result}] for every graded leg with a line and a positive projection"""
    out = []
    for f in sorted(glob.glob(os.path.join(log_dir, "20*.json"))):
        slate = os.path.basename(f)[:-5]
        d = json.load(open(f))
        for sec in ("fps", "moba"):
            for r in d.get(sec, []):
                if r.get("Result") not in ("OVER", "UNDER", "PUSH") or r.get("Actual") is None or not r.get("Line"):
                    continue
                t = title_of(r, sec)
                out.append(dict(slate=slate, title=t, player=r["Player"].strip(), key=f"{t}|{norm(r['Player'])}", kind="HS" if "HS" in r["Market"] else "K",
                                match=r["Match"], line=float(r["Line"]), proj=r.get("Proj"), act=float(r["Actual"]), result=r["Result"]))
    return out


def observations(legs):
    """one observation per (player, match, kind): the mean of the legs' relative errors; also the legs' over/under outcomes"""
    by = defaultdict(list)
    for l in legs:
        by[(l["key"], l["slate"], l["match"], l["kind"])].append(l)
    obs = []
    for (key, slate, match, kind), ls in by.items():
        e_line = st.mean(l["act"] / l["line"] - 1 for l in ls)
        pr = [l["act"] / l["proj"] - 1 for l in ls if l["proj"] and l["proj"] > 0]
        obs.append(dict(key=key, slate=slate, match=match, kind=kind, title=ls[0]["title"], player=ls[0]["player"], e_line=e_line,
                        e_proj=st.mean(pr) if pr else None, over=sum(l["result"] == "OVER" for l in ls), graded=sum(l["result"] in ("OVER", "UNDER") for l in ls)))
    return obs


def shrink_params(means_n, within_var):
    """empirical Bayes: tau^2 = between-player variance of the means minus their sampling variance (floored at 0); k = sigma^2 / tau^2"""
    ms = [m for m, n in means_n if n >= 2]
    if len(ms) < 3:
        return 0.0, None
    bet = st.pvariance(ms)
    samp = st.mean(within_var / n for m, n in means_n if n >= 2)
    tau2 = max(0.0, bet - samp)
    return tau2, (within_var / tau2 if tau2 > 0 else None)


def player_table(obs, min_n=8):
    by = defaultdict(list)
    for o in obs:
        by[o["key"]].append(o)
    allv = [o["e_line"] for o in obs]
    within = st.pvariance(allv) if len(allv) > 1 else 0.0
    tau2, k = shrink_params([(st.mean(o["e_line"] for o in os_), len(os_)) for os_ in by.values()], within)
    rows = []
    for key, os_ in by.items():
        n = len(os_)
        el = [o["e_line"] for o in os_]
        ep = [o["e_proj"] for o in os_ if o["e_proj"] is not None]
        mean_l = st.mean(el)
        sd = st.stdev(el) if n > 1 else None
        se = sd / math.sqrt(n) if sd is not None else None
        shr = mean_l * (n / (n + k)) if k else 0.0
        post_se = math.sqrt(within / (n + (within / tau2 if tau2 else 1e9))) if within else None
        over = sum(o["over"] for o in os_); gr = sum(o["graded"] for o in os_)
        row = dict(player=os_[0]["player"], title=os_[0]["title"], matches=n, legs=gr, over_rate=round(over / gr, 3) if gr else None,
                   err_vs_line=round(mean_l, 4), se_line=round(se, 4) if se else None, err_vs_proj=round(st.mean(ep), 4) if ep else None,
                   shrunk_vs_line=round(shr, 4), z=round(shr / post_se, 2) if post_se else None)
        for kind in ("K", "HS"):
            ks = [o for o in os_ if o["kind"] == kind]
            if ks:
                row[kind] = dict(matches=len(ks), err_vs_line=round(st.mean(o["e_line"] for o in ks), 4))
        row["flag"] = ("OVER" if shr > 0 else "UNDER") if (n >= min_n and row["z"] is not None and abs(row["z"]) >= 1.5) else None
        rows.append(row)
    rows.sort(key=lambda r: -abs(r["z"] or 0))
    return rows, dict(tau=round(math.sqrt(tau2), 4), within_sd=round(math.sqrt(within), 4), shrink_k=round(k, 2) if k else None)


def walk_forward(obs, legs, min_n=8):
    """before each slate, flag players from earlier slates only; score the flagged players' legs on that slate against the line"""
    slates = sorted({o["slate"] for o in obs})
    res = {"OVER": [0, 0], "UNDER": [0, 0], "NONE": [0, 0]}
    pairs = []
    for s in slates:
        past = [o for o in obs if o["slate"] < s]
        if not past:
            continue
        rows, _ = player_table(past, min_n)
        flag = {}
        pm = {}
        for r in rows:
            pm[(r["title"], r["player"])] = r["shrunk_vs_line"]
        flagged = {(r["title"], r["player"]): r["flag"] for r in rows if r["flag"]}
        for l in legs:
            if l["slate"] != s or l["result"] not in ("OVER", "UNDER"):
                continue
            f = flagged.get((l["title"], l["player"])) or "NONE"
            res[f][1] += 1
            res[f][0] += l["result"] == "OVER"
        for o in obs:
            if o["slate"] == s and (o["title"], o["player"]) in pm:
                pairs.append((pm[(o["title"], o["player"])], o["e_line"]))
    corr = None
    if len(pairs) > 10:
        xs, ys = zip(*pairs)
        mx, my = st.mean(xs), st.mean(ys)
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
        corr = round(sum((x - mx) * (y - my) for x, y in pairs) / (sx * sy), 3) if sx and sy else None
    return dict(over_rate_of_legs={k: dict(over=v[0], n=v[1], rate=round(v[0] / v[1], 3) if v[1] else None) for k, v in res.items()}, corr_past_vs_next=corr, pairs=len(pairs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=8)
    ap.add_argument("--out", default="data/players/players.json")
    a = ap.parse_args()
    legs = settled_legs()
    obs = observations(legs)
    rows, par = player_table(obs, a.min_n)
    wf = walk_forward(obs, legs, a.min_n)
    sl = sorted({l["slate"] for l in legs})
    rep = dict(slates=[sl[0], sl[-1]] if sl else [], legs=len(legs), observations=len(obs),
               players=len(rows), min_n=a.min_n, shrink=par, walk_forward=wf, flagged=[r for r in rows if r["flag"]], table=rows)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(rep, open(a.out, "w"), indent=1)
    print(f"{len(legs)} graded legs, {len(obs)} player-match observations, {len(rows)} players; shrink: {par}")
    print("walk-forward (legs of flagged players on the next slate, over rate):", json.dumps(wf["over_rate_of_legs"]), "corr(past shrunk error, next error) =", wf["corr_past_vs_next"], f"on {wf['pairs']} pairs")
    print(f"\nflagged (>= {a.min_n} matches, |z| >= 1.5): {len(rep['flagged'])}")
    for r in rep["flagged"][:25]:
        print(f"  {r['flag']:<5}{r['title']:<4}{r['player']:<14} {r['matches']:>3} matches  vs line {r['err_vs_line']:+.1%} (shrunk {r['shrunk_vs_line']:+.1%})  vs proj {r['err_vs_proj']:+.1%}  over {r['over_rate']:.0%}  z {r['z']}")


if __name__ == "__main__":
    main()
