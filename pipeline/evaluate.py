"""Evaluate how well the projections predicted, slate by slate and pooled, with hypotheses fixed in advance.

    python -m pipeline.evaluate --slate 2026-10-16        # one slate: writes data/evaluation/<slate>.json, refreshes site/data/evaluation.json
    python -m pipeline.evaluate --all                     # every slate that has settled legs

Reads the frozen Log (projections + Actual), the results pull (actual maps and rounds) and the slate's own board. Needs no network.
Pure Python; the one counterfactual (what the model would have said with the maps and rounds actually played) runs the site's own model through node.

What it measures, and why these:
  * AUC of each signal for OVER vs UNDER (0.5 = no information). Hit rate alone is misleading when a slate's base rate is lopsided (10-16: 39% overs).
  * MAE of the projection against the posted line as a forecast of the actual: does it beat the line?
  * the slope of (actual - line) on (projection - line): 1 = right about the gap, 0 = adds nothing.
  * hit rate by lean size, calibration, Brier.
  * where the error comes from: published inputs vs the actual maps and rounds, rounds assumed vs played, map-pick accuracy.
Every interval is a 95% bootstrap over MATCHES (legs in a match share maps and rounds, so they are not independent).

The hypotheses below were written after looking at 2026-10-16 (EXPLORATORY_THROUGH). Anything on that slate or earlier is labelled exploratory;
only later slates count as confirmatory. A hypothesis is supported only when the interval excludes the null in the claimed direction.
"""
import argparse, datetime as dt, glob, json, math, os, random, shutil, subprocess, tempfile
from collections import defaultdict

EXPLORATORY_THROUGH = "2026-10-16"
BOOT, SEED = 2000, 7
MIN_MATCHES, MIN_LEGS, MIN_MAPS = 8, 60, 20

HYPOTHESES = [
    dict(id="H1", name="The posted rounds total runs high", metric="mean(rounds assumed - rounds played) per map", claim=">0", null=0),
    dict(id="H2", name="The map-specific layer adds information", metric="AUC(model P(over)) - AUC(map-free projection)", claim=">0", null=0),
    dict(id="H3", name="The model's gap to the line predicts the realised gap", metric="slope of (actual - line) on (projection - line), sqrt(line)-standardised", claim=">0", null=0),
    dict(id="H4", name="Hit rate rises with the size of the lean", metric="hit rate(lean >= 15 pts) - hit rate(lean < 4 pts)", claim=">0", null=0),
    dict(id="H5", name="The projection is closer to the actual than the posted line", metric="MAE(projection) - MAE(line)", claim="<0", null=0),
    dict(id="H6", name="The round-differential layer adds information", metric="AUC(adj P(over)) - AUC(model P(over))", claim=">0", null=0),
]


# ----------------------------------------------------------------------------------------------- statistics
def wilson(h, n):
    if not n:
        return None
    p, z = h / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - w, 4), round(c + w, 4)]


def auc(y, s):
    """Mann-Whitney AUC with average ranks for ties. None when one class is empty."""
    n1 = sum(y)
    n0 = len(y) - n1
    if not n1 or not n0:
        return None
    order = sorted(range(len(s)), key=lambda i: s[i])
    ranks = [0.0] * len(s)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and s[order[j + 1]] == s[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return (sum(ranks[k] for k in range(len(y)) if y[k]) - n1 * (n1 + 1) / 2) / (n1 * n0)


def boot(fn, clusters, B=BOOT, seed=SEED):
    """95% interval of fn(indices) when whole clusters are resampled with replacement. None if fewer than 2 clusters."""
    groups = defaultdict(list)
    for i, c in enumerate(clusters):
        groups[c].append(i)
    keys = list(groups)
    if len(keys) < 2:
        return None
    rng, out = random.Random(seed), []
    for _ in range(B):
        idx = [i for k in (rng.choice(keys) for _ in keys) for i in groups[k]]
        v = fn(idx)
        if v is not None and v == v:
            out.append(v)
    if len(out) < B // 2:
        return None
    out.sort()
    return [round(out[int(0.025 * len(out))], 4), round(out[min(len(out) - 1, int(0.975 * len(out)))], 4)]


def est(fn, clusters, n=None):
    v = fn(list(range(len(clusters))))
    return dict(value=None if v is None else round(v, 4), ci=boot(fn, clusters) if v is not None else None, n=n if n is not None else len(clusters))


def verdict(e, claim, n_matches, n_units, min_units):
    if e["value"] is None or e["ci"] is None:
        return "insufficient data"
    if n_matches < MIN_MATCHES or n_units < min_units:
        return "insufficient data"
    lo, hi = e["ci"]
    if claim == ">0":
        return "supported" if lo > 0 else "contradicted" if hi < 0 else "inconclusive"
    return "supported" if hi < 0 else "contradicted" if lo > 0 else "inconclusive"


# ----------------------------------------------------------------------------------------------- inputs
def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


def norm_map(s):
    s = str(s or "").replace("de_", "")
    return s[:1].upper() + s[1:] if s else None


def overrides(results, board_matches):
    """The maps and rounds actually played, in the shape the model takes. A match is left out when the source has no round count for a map it needs."""
    out = {}
    for m in board_matches:
        r = ((results or {}).get("titles", {}).get(m["title"]) or {}).get(m["id"])
        if not r or r.get("status") != "finished" or not r.get("maps"):
            continue
        maps, rounds = [None] * 3, [None] * 3
        for mp in r["maps"]:
            if mp["n"] <= 3:
                maps[mp["n"] - 1], rounds[mp["n"] - 1] = norm_map(mp.get("map")), mp.get("rounds")
        need = [0] + ([1] if len([x for x in r["maps"] if x["n"] <= 2]) >= 2 else [])
        if all(rounds[i] for i in need):
            out[m["id"]] = dict(maps=maps, rounds=rounds)
    return out


def counterfactual(fps, ovr):
    """-> {legs, matches} from the site's own model, or None when node is not available."""
    node = shutil.which("node")
    tool = os.path.join(os.path.dirname(__file__), "..", "site", "tools", "counterfactual.cjs")
    if not node or not os.path.exists(tool):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        for name, obj in (("fps.json", fps), ("ovr.json", ovr)):
            with open(f"{tmp}/{name}", "w", encoding="utf-8") as f:
                json.dump(obj, f)
        r = subprocess.run([node, tool, f"{tmp}/fps.json", f"{tmp}/ovr.json"], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None


def build(slate, site="site", results_dir="data/results", imports="data/imports"):
    """-> dict(rows, matches, notes). One row per settled leg with a number for every signal that exists."""
    from .results import load_board
    log = read_json(f"{site}/data/log/{slate}.json")
    if not log:
        raise SystemExit(f"no Log for {slate}")
    fps, moba, where = load_board(slate, site, imports)
    res = read_json(f"{results_dir}/{slate}.json")
    legs = {(g["match"], g["player"], g["market"]): g for g in fps["legs"]}
    ovr = overrides(res, fps["matches"])
    cf = counterfactual(fps, ovr) if ovr else None
    notes = []
    if not res:
        notes.append("no results file: counterfactual, rounds and map-pick sections are empty")
    elif cf is None:
        notes.append("node is not available: counterfactual section is empty")
    rows = []
    for r in log["fps"]:
        a = r.get("Actual")
        if not isinstance(a, (int, float)) or isinstance(a, bool):
            continue
        k = (r["Match"], r["Player"], r["Market"])
        c = ((cf or {}).get("legs") or {}).get("|".join(k)) or {}
        g = legs.get(k) or {}
        rows.append(dict(slate=slate, match=r["Match"], cluster=f"{slate}|{r['Match']}", title=r["Match"].split(" ")[0], market=r["Market"], line=r["Line"], act=a, proj=r.get("Proj"),
                         po=r.get("P(over)"), adj=r.get("Proj adj"), poa=r.get("P(over) adj"), mf=r.get("Proj map-free"), tp=r.get("TP book median"), l10=r.get("PF L10"),
                         avg10=g.get("avg10"), proj_or=c.get("proj_or"), po_or=c.get("p_over_or"), cf=bool(c.get("counterfactual")), n1=c.get("n1")))
    mrows = []
    picks = {m["id"]: m.get("picks_from") or "" for m in fps["matches"]}
    for mid, info in ((cf or {}).get("matches") or {}).items():
        if mid not in ovr:
            continue
        actual_maps, actual_rounds = ovr[mid]["maps"], ovr[mid]["rounds"]
        mrows.append(dict(slate=slate, match=mid, cluster=f"{slate}|{mid}", picks_from="PF Map Picks" if "PF Map Picks" in picks.get(mid, "") else "fallback",
                          used_maps=info["used_maps"][:2], used_rounds=info["used_rounds"][:2], actual_maps=actual_maps[:2], actual_rounds=actual_rounds[:2]))
    moba_rows = []
    for r in log["moba"]:
        a = r.get("Actual")
        if isinstance(a, (int, float)) and not isinstance(a, bool):
            moba_rows.append(dict(slate=slate, match=r["Match"], cluster=f"{slate}|{r['Match']}", line=r["Line"], act=a, proj=r.get("Proj"), po=r.get("P(over)"), naive=r.get("Naive proj"), tp=r.get("TP book median")))
    return dict(slate=slate, board=where, rows=rows, matches=mrows, moba=moba_rows, notes=notes)


# ----------------------------------------------------------------------------------------------- summary
def summarise(rows, mrows, moba=None):
    """Everything above, for any set of rows (one slate, or pooled)."""
    out = dict(n_settled=len(rows), n_matches=len({r["cluster"] for r in rows}))
    R = [r for r in rows if r["act"] != r["line"]]
    out["n_pushes"] = len(rows) - len(R)
    if not R:
        return dict(out, note="no settled legs")
    y = [1 if r["act"] > r["line"] else 0 for r in R]
    cl = [r["cluster"] for r in R]
    out["over_rate"] = round(sum(y) / len(y), 4)
    out["always_under_hit"] = round(1 - sum(y) / len(y), 4)

    signals = {"model P(over)": lambda r: r["po"], "model adj P(over)": lambda r: r["poa"], "map-free projection - line": lambda r: (r["mf"] if r["mf"] is not None else r["proj"]) - r["line"],
               "PF avg L10 - line": lambda r: None if r["avg10"] is None else r["avg10"] - r["line"], "PF L10 hit rate": lambda r: r["l10"]}
    S = {}
    out["auc"] = {}
    for name, f in signals.items():
        vals = [f(r) for r in R]
        keep = [i for i, v in enumerate(vals) if v is not None]
        if len(keep) < 20:
            continue
        S[name] = vals
        yy, ss, cc = [y[i] for i in keep], [vals[i] for i in keep], [cl[i] for i in keep]
        out["auc"][name] = est(lambda idx, yy=yy, ss=ss: auc([yy[i] for i in idx], [ss[i] for i in idx]), cc, len(keep))
    tpk = [i for i, r in enumerate(R) if r["tp"] is not None]
    if len(tpk) >= 20:
        out["auc"]["Thunderpick kill-line median - line"] = est(lambda idx: auc([y[tpk[i]] for i in idx], [R[tpk[i]]["tp"] - R[tpk[i]]["line"] for i in idx]), [cl[i] for i in tpk], len(tpk))

    # error against the line
    allc = [r["cluster"] for r in rows]
    mae = lambda f, sel: (lambda xs: round(sum(xs) / len(xs), 4) if xs else None)([abs(f(r) - r["act"]) for r in sel if f(r) is not None])
    bias = lambda f, sel: (lambda xs: round(sum(xs) / len(xs), 4) if xs else None)([f(r) - r["act"] for r in sel if f(r) is not None])
    groups = [("all", rows)] + [(m, [r for r in rows if r["market"] == m]) for m in sorted({r["market"] for r in rows})] + [(t, [r for r in rows if r["title"] == t]) for t in sorted({r["title"] for r in rows})]
    out["error"] = {name: dict(n=len(sel), mae_line=mae(lambda r: r["line"], sel), mae_proj=mae(lambda r: r["proj"], sel), mae_map_free=mae(lambda r: r["mf"], sel), mae_adj=mae(lambda r: r["adj"], sel),
                               bias_line=bias(lambda r: r["line"], sel), bias_proj=bias(lambda r: r["proj"], sel)) for name, sel in groups if sel}
    d = [abs(r["proj"] - r["act"]) - abs(r["line"] - r["act"]) for r in rows]
    out["mae_proj_minus_line"] = est(lambda idx: sum(d[i] for i in idx) / len(idx), allc, len(rows))

    # gap slope
    x = [(r["proj"] - r["line"]) / math.sqrt(r["line"]) for r in rows]
    z = [(r["act"] - r["line"]) / math.sqrt(r["line"]) for r in rows]

    def slope(idx):
        xs, zs = [x[i] for i in idx], [z[i] for i in idx]
        mx, mz = sum(xs) / len(xs), sum(zs) / len(zs)
        v = sum((a - mx) ** 2 for a in xs)
        return sum((a - mx) * (b - mz) for a, b in zip(xs, zs)) / v if v else None
    out["gap_slope"] = est(slope, allc, len(rows))

    # lean bins
    bins = []
    for lo, hi, label in ((0, .04, "no lean (< 4 pts)"), (.04, .15, "lean 4-15 pts"), (.15, .25, "lean 15-25 pts"), (.25, 1.01, "strong (>= 25 pts)"), (.04, 1.01, "any lean (>= 4 pts)")):
        sel = [r for r in R if lo <= abs(r["po"] - .5) < hi]
        h = sum((r["po"] >= .5) == (r["act"] > r["line"]) for r in sel)
        ov, un = [r for r in sel if r["po"] >= .5], [r for r in sel if r["po"] < .5]
        bins.append(dict(label=label, n=len(sel), hits=h, rate=round(h / len(sel), 4) if sel else None, wilson=wilson(h, len(sel)), over_calls=[sum(r["act"] > r["line"] for r in ov), len(ov)],
                         under_calls=[sum(r["act"] < r["line"] for r in un), len(un)]))
    out["lean_bins"] = bins

    # calibration
    cal, edges = [], [0, .3, .4, .5, .6, .7, 1.01]
    for a, b in zip(edges, edges[1:]):
        sel = [(r["po"], yy) for r, yy in zip(R, y) if a <= r["po"] < b]
        if sel:
            cal.append(dict(lo=a, hi=min(b, 1), n=len(sel), mean_p=round(sum(p for p, _ in sel) / len(sel), 4), over_rate=round(sum(v for _, v in sel) / len(sel), 4)))
    out["calibration"] = cal
    out["brier"] = round(sum((r["po"] - yy) ** 2 for r, yy in zip(R, y)) / len(R), 4)
    out["brier_coin"] = 0.25

    # inputs: published vs the maps and rounds actually played
    cf = [r for r in rows if r["cf"] and r["proj_or"] is not None]
    if cf:
        Rc = [r for r in cf if r["act"] != r["line"]]
        yc = [1 if r["act"] > r["line"] else 0 for r in Rc]
        out["counterfactual"] = dict(n=len(cf), mae_published=mae(lambda r: r["proj"], cf), mae_actual_inputs=mae(lambda r: r["proj_or"], cf), mae_line=mae(lambda r: r["line"], cf),
                                     bias_published=bias(lambda r: r["proj"], cf), bias_actual_inputs=bias(lambda r: r["proj_or"], cf),
                                     auc_published=est(lambda idx: auc([yc[i] for i in idx], [Rc[i]["po"] for i in idx]), [r["cluster"] for r in Rc], len(Rc)),
                                     auc_actual_inputs=est(lambda idx: auc([yc[i] for i in idx], [Rc[i]["po_or"] for i in idx]), [r["cluster"] for r in Rc], len(Rc)))
    pairs = [(m, u, a) for m in mrows for u, a in zip(m["used_rounds"], m["actual_rounds"]) if u and a]
    if pairs:
        diffs = [u - a for _, u, a in pairs]
        out["rounds"] = dict(n_maps=len(pairs), assumed_mean=round(sum(u for _, u, _ in pairs) / len(pairs), 3), played_mean=round(sum(a for _, _, a in pairs) / len(pairs), 3),
                             mean_error=round(sum(diffs) / len(diffs), 3), mae=round(sum(abs(v) for v in diffs) / len(diffs), 3), assumed_sd=round(_sd([u for _, u, _ in pairs]), 3), played_sd=round(_sd([a for _, _, a in pairs]), 3))
    slots = [(m["picks_from"], u == a) for m in mrows for u, a in zip(m["used_maps"], m["actual_maps"]) if u and a]
    if slots:
        by = defaultdict(lambda: [0, 0])
        for src, ok in slots:
            by[src][0] += ok
            by[src][1] += 1
        out["map_picks"] = dict(hit=sum(ok for _, ok in slots), total=len(slots), by_source={k: v for k, v in by.items()})

    # hypotheses
    n_match = out["n_matches"]
    hyp = {}
    if pairs:
        pc = [m["cluster"] for m, _, _ in pairs]
        hyp["H1"] = (est(lambda idx: sum(diffs[i] for i in idx) / len(idx), pc, len(pairs)), len(pairs), MIN_MAPS)
    if "model P(over)" in S and "map-free projection - line" in S:
        po, mf = S["model P(over)"], S["map-free projection - line"]
        hyp["H2"] = (est(lambda idx: _d(auc([y[i] for i in idx], [po[i] for i in idx]), auc([y[i] for i in idx], [mf[i] for i in idx])), cl, len(R)), len(R), MIN_LEGS)
    hyp["H3"] = (out["gap_slope"], len(rows), MIN_LEGS)
    hi_, lo_ = [i for i, r in enumerate(R) if abs(r["po"] - .5) >= .15], [i for i, r in enumerate(R) if abs(r["po"] - .5) < .04]
    hit = lambda r: 1.0 if (r["po"] >= .5) == (r["act"] > r["line"]) else 0.0

    def h4(idx):
        a = [hit(R[i]) for i in idx if i in set(hi_)]
        b = [hit(R[i]) for i in idx if i in set(lo_)]
        return (sum(a) / len(a) - sum(b) / len(b)) if a and b else None
    hyp["H4"] = (est(h4, cl, len(hi_) + len(lo_)), min(len(hi_), len(lo_)) * 2, MIN_LEGS // 2)
    hyp["H5"] = (out["mae_proj_minus_line"], len(rows), MIN_LEGS)
    if "model adj P(over)" in S:
        pa, po = S["model adj P(over)"], S["model P(over)"]
        hyp["H6"] = (est(lambda idx: _d(auc([y[i] for i in idx], [pa[i] for i in idx]), auc([y[i] for i in idx], [po[i] for i in idx])), cl, len(R)), len(R), MIN_LEGS)
    out["hypotheses"] = []
    for h in HYPOTHESES:
        e, units, minu = hyp.get(h["id"], (dict(value=None, ci=None, n=0), 0, 0))
        out["hypotheses"].append(dict(h, estimate=e["value"], ci=e["ci"], n=e["n"], status=verdict(e, h["claim"], n_match, units, minu)))
    if moba:
        out["moba"] = summarise_moba(moba)
    return out


def _sd(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _d(a, b):
    return None if a is None or b is None else a - b


def summarise_moba(rows):
    n = len(rows)
    out = dict(n_settled=n)
    mae = lambda f: (lambda xs: round(sum(xs) / len(xs), 4) if xs else None)([abs(f(r) - r["act"]) for r in rows if f(r) is not None])
    out.update(mae_line=mae(lambda r: r["line"]), mae_proj=mae(lambda r: r["proj"]), mae_naive=mae(lambda r: r["naive"]))
    if n < 30:
        out["note"] = f"{n} settled legs: too few to evaluate (needs 30)"
    return out


# ----------------------------------------------------------------------------------------------- driver
def settled_slates(site):
    idx = read_json(f"{site}/data/log/index.json") or []
    out = []
    for s in idx:
        lg = read_json(f"{site}/data/log/{s}.json") or {}
        if any(isinstance(r.get("Actual"), (int, float)) for r in lg.get("fps", []) + lg.get("moba", [])):
            out.append(s)
    return out


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        f.write("\n")


def run(slates, site="site", results_dir="data/results", imports="data/imports", out_dir="data/evaluation"):
    for s in slates:
        b = build(s, site, results_dir, imports)
        b["summary"] = summarise(b["rows"], b["matches"], b["moba"])
        write(f"{out_dir}/{s}.json", b)
    # pooled views are rebuilt from every stored slate
    stored = {}
    for p in sorted(glob.glob(f"{out_dir}/*.json")):
        d = read_json(p)
        stored[d["slate"]] = d
    pooled = lambda ss: (lambda rows, ms, mo: summarise(rows, ms, mo) if rows else None)(
        [r for s in ss for r in stored[s]["rows"]], [m for s in ss for m in stored[s]["matches"]], [r for s in ss for r in stored[s]["moba"]])
    expl = [s for s in stored if s <= EXPLORATORY_THROUGH]
    conf = [s for s in stored if s > EXPLORATORY_THROUGH]
    report = dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), exploratory_through=EXPLORATORY_THROUGH, hypotheses=HYPOTHESES,
                  slates=sorted(stored), by_slate={s: stored[s]["summary"] for s in stored}, notes={s: stored[s]["notes"] for s in stored},
                  exploratory=dict(slates=expl, summary=pooled(expl)) if expl else None, confirmatory=dict(slates=conf, summary=pooled(conf)) if conf else None)
    write(f"{site}/data/evaluation.json", report)
    return report


def show(s, title):
    print(f"\n=== {title}: {s['n_settled']} settled legs, {s['n_matches']} matches, over-rate {s.get('over_rate', 0):.1%} (always-under would hit {s.get('always_under_hit', 0):.1%})")
    for k, v in (s.get("auc") or {}).items():
        print(f"  AUC {k:38} {v['value']:.3f}  {v['ci']}  n={v['n']}")
    e = (s.get("error") or {}).get("all")
    if e:
        print(f"  MAE  line {e['mae_line']}  projection {e['mae_proj']}  map-free {e['mae_map_free']}  adj {e['mae_adj']} | bias projection {e['bias_proj']:+}  line {e['bias_line']:+}")
    if s.get("counterfactual"):
        c = s["counterfactual"]
        print(f"  with actual maps+rounds: MAE {c['mae_published']} -> {c['mae_actual_inputs']}, bias {c['bias_published']:+} -> {c['bias_actual_inputs']:+}")
    if s.get("rounds"):
        r = s["rounds"]
        print(f"  rounds per map: assumed {r['assumed_mean']} (sd {r['assumed_sd']}), played {r['played_mean']} (sd {r['played_sd']}), n={r['n_maps']}")
    if s.get("map_picks"):
        print(f"  map picks right: {s['map_picks']['hit']}/{s['map_picks']['total']}")
    print("  hypotheses:")
    for h in s.get("hypotheses") or []:
        ci = "" if not h["ci"] else f" {h['ci']}"
        est_ = "n/a" if h["estimate"] is None else f"{h['estimate']:+.3f}"
        print(f"    {h['id']} {h['name'][:60]:60} {est_}{ci}  -> {h['status']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--site", default="site")
    a = ap.parse_args()
    slates = settled_slates(a.site) if a.all or not a.slate else [a.slate]
    if not slates:
        raise SystemExit("no slate has settled legs yet")
    rep = run(slates, a.site)
    for s in slates:
        show(rep["by_slate"][s], f"{s}{' (exploratory: the hypotheses came from this slate)' if s <= EXPLORATORY_THROUGH else ' (confirmatory)'}")
    if rep["confirmatory"] and rep["confirmatory"]["summary"]:
        show(rep["confirmatory"]["summary"], f"CONFIRMATORY, pooled over {rep['confirmatory']['slates']}")
    else:
        print("\nno confirmatory slate settled yet: the first slate after", EXPLORATORY_THROUGH, "is the first real test of the hypotheses")


if __name__ == "__main__":
    main()
