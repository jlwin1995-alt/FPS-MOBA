"""Running tally of how the daily lean ranking does:   python -m pipeline.ranktally
The ranking is every FPS leg of a slate sorted by the base model's lean, |P(over) - 0.5|, largest first (ties by match, then player), scored on the model's own side
(P(over) >= 50% = over). It is fixed by the frozen Log at import, so any settled slate can be scored exactly as it would have been on the day.
Per slate: hits on the model's side for the top 10 / 20 / 30 legs, by lean bucket, and for the H8 definition (lean >= 10 points and the adjusted model on the same side), with open legs counted.
A slate with open legs is marked partial: its tally uses only the legs graded so far. Pushes and voids are excluded.
Output: data/ranking/tally.json (per slate and cumulative). Descriptive only: the ranking is not a registered rule."""
import glob, json, os

LOG = "site/data/log"
BUCKETS = [("0-10", 0.0, 0.10), ("10-15", 0.10, 0.15), ("15-20", 0.15, 0.20), ("20-25", 0.20, 0.25), ("25+", 0.25, 1.01)]
TOPS = (10, 20, 30)


def lean(r):
    return abs(r["P(over)"] - 0.5)


def side(r):
    return "OVER" if r["P(over)"] >= 0.5 else "UNDER"


def ranked(rows):
    """FPS legs with a P(over), strongest lean first (the order of the daily ranking file)"""
    return sorted((r for r in rows if r.get("P(over)") is not None), key=lambda r: (-lean(r), r["Match"], r["Player"]))


def graded(r):
    return r.get("Result") in ("OVER", "UNDER")


def hit(r):
    return r["Result"] == side(r)


def tally(h, n, extra=None):
    d = dict(hits=h, n=n, rate=round(h / n, 4) if n else None)
    if extra:
        d.update(extra)
    return d


def slate_tally(rows):
    rk = ranked(rows)
    g = [r for r in rk if graded(r)]
    out = dict(legs=len(rk), graded=len(g), open=sum(1 for r in rk if r.get("Result") is None), all=tally(sum(hit(r) for r in g), len(g)))
    out["top"] = {}
    for k in TOPS:
        t = [r for r in rk[:k] if graded(r)]
        out["top"][str(k)] = tally(sum(hit(r) for r in t), len(t))
    out["bucket"] = {}
    for name, a, b in BUCKETS:
        t = [r for r in g if a <= lean(r) < b]
        out["bucket"][name] = tally(sum(hit(r) for r in t), len(t))
    h8 = [r for r in g if lean(r) >= 0.10 and r.get("P(over) adj") is not None and (r["P(over) adj"] >= 0.5) == (r["P(over)"] >= 0.5)]
    out["h8_def"] = dict(all=tally(sum(hit(r) for r in h8), len(h8)), over=tally(sum(hit(r) for r in h8 if side(r) == "OVER"), sum(1 for r in h8 if side(r) == "OVER")),
                         under=tally(sum(hit(r) for r in h8 if side(r) == "UNDER"), sum(1 for r in h8 if side(r) == "UNDER")))
    return out


def add(a, b):
    return tally(a["hits"] + b["hits"], a["n"] + b["n"])


def cumulative(per):
    cum = dict(slates=len(per), all=tally(0, 0), top={str(k): tally(0, 0) for k in TOPS}, bucket={n: tally(0, 0) for n, _, _ in BUCKETS}, h8_def={k: tally(0, 0) for k in ("all", "over", "under")})
    for t in per.values():
        cum["all"] = add(cum["all"], t["all"])
        for k in cum["top"]:
            cum["top"][k] = add(cum["top"][k], t["top"][k])
        for k in cum["bucket"]:
            cum["bucket"][k] = add(cum["bucket"][k], t["bucket"][k])
        for k in cum["h8_def"]:
            cum["h8_def"][k] = add(cum["h8_def"][k], t["h8_def"][k])
    return cum


def build(log_dir=LOG):
    per = {}
    for f in sorted(glob.glob(os.path.join(log_dir, "20*.json"))):
        d = json.load(open(f))
        if d.get("fps"):
            per[os.path.basename(f)[:-5]] = slate_tally(d["fps"])
    return dict(per_slate=per, cumulative=cumulative(per))


def pct(d):
    return f"{d['hits']}/{d['n']} {100 * d['rate']:.0f}%" if d["n"] else "-"


def main():
    rep = build()
    os.makedirs("data/ranking", exist_ok=True)
    json.dump(rep, open("data/ranking/tally.json", "w"), indent=1)
    print(f"{'slate':<12}{'graded':>7}{'open':>5}  {'top10':<10}{'top20':<10}{'top30':<10}{'lean>=10 & adj':<16}{'all legs':<12}")
    for s, t in rep["per_slate"].items():
        print(f"{s:<12}{t['graded']:>7}{t['open']:>5}  {pct(t['top']['10']):<10}{pct(t['top']['20']):<10}{pct(t['top']['30']):<10}{pct(t['h8_def']['all']):<16}{pct(t['all']):<12}")
    c = rep["cumulative"]
    print(f"\ncumulative over {c['slates']} slates ({c['all']['n']} graded legs):")
    print("  top 10:", pct(c["top"]["10"]), "| top 20:", pct(c["top"]["20"]), "| top 30:", pct(c["top"]["30"]), "| all legs:", pct(c["all"]))
    print("  by lean:", ", ".join(f"{k} pts {pct(v)}" for k, v in c["bucket"].items()))
    print("  lean>=10 & adjusted agrees:", pct(c["h8_def"]["all"]), "(overs", pct(c["h8_def"]["over"]) + ", unders", pct(c["h8_def"]["under"]) + ")")


if __name__ == "__main__":
    main()
