"""Freeze the legs a play rule selects, before the games.

    python -m pipeline.plays --slate 2026-10-18        # -> data/plays/<slate>.json

Reads the slate's frozen Log (projections as values at default settings) and applies the rules in pipeline/evaluate.py (RULES). Commit the file before the first start:
its commit time is the record that the selection was made before play. Settling never rewrites it.
"""
import argparse, datetime as dt, json, os
from .evaluate import RULES


def select(log_rows):
    out = {}
    for rid, rule in RULES.items():
        legs = []
        for r in log_rows:
            po, poa = r.get("P(over)"), r.get("P(over) adj")
            if rule["test"](po, poa):
                legs.append(dict(match=r["Match"], player=r["Player"], market=r["Market"], line=r["Line"], side="OVER" if po >= 0.5 else "UNDER", p_over=po, p_over_adj=poa))
        legs.sort(key=lambda l: (l["match"], -abs(l["p_over"] - 0.5)))
        out[rid] = dict(name=rule["name"], n=len(legs), legs=legs)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--site", default="site")
    ap.add_argument("--out", default="data/plays")
    a = ap.parse_args()
    with open(f"{a.site}/data/log/{a.slate}.json", encoding="utf-8") as f:
        log = json.load(f)["fps"]
    res = dict(slate=a.slate, frozen_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), rules=select(log), comparison="every leg on the board (the base model's side)")
    os.makedirs(a.out, exist_ok=True)
    path = f"{a.out}/{a.slate}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(path, {k: v["n"] for k, v in res["rules"].items()})


if __name__ == "__main__":
    main()
