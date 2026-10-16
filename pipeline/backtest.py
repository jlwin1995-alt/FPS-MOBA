"""Walk-forward replay of the projection over the series history: for each series in the window, project from only the games before it.

    python -m pipeline.backtest [--raw data/raw] [--days 40] [--out site/data]

The history has no posted lines, so this scores the projection itself (error vs the naive last-10 average and the all-games mean), not betting results.
"""
import argparse, os, statistics
from datetime import date, timedelta
from . import config as C
from . import model as M
from .store import read_rows, write_json


def run(logs, asof, days=40):
    lo = (date.fromisoformat(asof) - timedelta(days=days)).isoformat()
    by = {}
    for r in logs:
        by.setdefault((r["title"], r["player"]), []).append(r)
    errs = {}
    cache = {}
    for (t, p), rows in by.items():
        for r in rows:
            if r["date"] < lo or r["date"] >= asof:
                continue
            for s in C.STATS:
                actual = M.series_value(r, s)
                if actual is None:
                    continue
                if (r["date"], t) not in cache:
                    cache[(r["date"], t)] = M.title_means([x for x in logs if x["date"] < r["date"]], r["date"])
                tm = cache[(r["date"], t)].get((t, s))
                pr = M.project([v for _, v in M.player_history(rows, t, p, s, r["date"])], tm, s)
                if not pr:
                    continue
                e = errs.setdefault((t, s), dict(n=0, a=0.0, naive=0.0, season=0.0, bias=0.0, ab=0.0, tm=0.0))
                e["n"] += 1
                e["a"] += abs(pr["proj"] - actual)
                e["naive"] += abs(pr["naive"] - actual)
                e["season"] += abs(pr["variants"]["c"] - actual)
                e["tm"] += abs((tm if tm is not None else actual) - actual)
                e["bias"] += pr["proj"] - actual
    rows = []
    for (t, s), e in sorted(errs.items()):
        n = e["n"]
        rows.append(dict(title=t, stat=s, label=C.STATS[s]["label"], n=n, mae=e["a"] / n, naive=e["naive"] / n, season=e["season"] / n, titlemean=e["tm"] / n, bias=e["bias"] / n))
    tot = sum(r["n"] for r in rows)
    agg = lambda k: sum(r[k] * r["n"] for r in rows) / tot if tot else None
    return dict(days=days, n=tot, mae=agg("mae"), naive=agg("naive"), season=agg("season"), titlemean=agg("titlemean"), rows=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--days", type=int, default=40)
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--out", default="site/data")
    a = ap.parse_args()
    out = run(read_rows(os.path.join(a.raw, "logs.csv")), a.asof, a.days)
    write_json(os.path.join(a.out, "backtest.json"), out)
    print(f"backtest: {out['n']} projections, MAE {out['mae']:.3f} vs naive {out['naive']:.3f}")


if __name__ == "__main__":
    main()
