"""Score a SHADOW projection variant against the live (registered) model once its slate is settled:   python -m pipeline.shadow [--variant vetosim]
A shadow file (data/shadow/<variant>/<slate>.json) is a frozen copy of the projections a variant workbook produced before play (the commit time is the record).
It is NOT a rule and never feeds plays, the site or the evaluation. Per slate and pooled, on the graded legs, live vs shadow:
  Brier score of P(over) (lower is better), hit rate on the model's own side (P(over) >= 0.5 = over), and the legs where the two sides differ (who was right).
The map assignment each used is listed so the veto simulation can be checked against the maps actually played."""
import argparse, glob, json, os

LOG = "site/data/log"


def key(r):
    return (r["Match"], r["Player"], r["Market"], float(r["Line"]))


def score(rows):
    n = len(rows)
    if not n:
        return None
    br = sum((r["p"] - (r["res"] == "OVER")) ** 2 for r in rows) / n
    hit = sum((r["p"] >= .5) == (r["res"] == "OVER") for r in rows)
    return dict(n=n, brier=round(br, 4), hits=hit, rate=round(hit / n, 4))


def compare(variant="vetosim", shadow_dir="data/shadow", log_dir=LOG):
    out = {}
    for f in sorted(glob.glob(os.path.join(shadow_dir, variant, "20*.json"))):
        slate = os.path.basename(f)[:-5]
        sh = json.load(open(f))
        lp = os.path.join(log_dir, f"{slate}.json")
        if not os.path.exists(lp):
            continue
        live = {key(r): r for r in json.load(open(lp))["fps"]}
        L, S, D = [], [], []
        for r in sh["rows"]:
            o = live.get(key(r))
            if not o or o.get("Result") not in ("OVER", "UNDER") or r.get("P(over)") is None or o.get("P(over)") is None:
                continue
            L.append(dict(p=o["P(over)"], res=o["Result"])); S.append(dict(p=r["P(over)"], res=o["Result"]))
            if (o["P(over)"] >= .5) != (r["P(over)"] >= .5):
                D.append(dict(live=o["P(over)"], shadow=r["P(over)"], res=o["Result"]))
        out[slate] = dict(live=score(L), shadow=score(S), differ=len(D),
                          differ_live_right=sum((d["live"] >= .5) == (d["res"] == "OVER") for d in D),
                          differ_shadow_right=sum((d["shadow"] >= .5) == (d["res"] == "OVER") for d in D))
    return out


def site_data(variant="vetosim", shadow_dir="data/shadow", log_dir=LOG):
    """the slim file the Shadow tab reads: every shadow leg next to the live frozen leg, with the result once settled, plus the comparison per slate"""
    cmp = compare(variant, shadow_dir, log_dir)
    slates = {}
    for f in sorted(glob.glob(os.path.join(shadow_dir, variant, "20*.json"))):
        slate = os.path.basename(f)[:-5]
        sh = json.load(open(f))
        lp = os.path.join(log_dir, f"{slate}.json")
        live = {key(r): r for r in json.load(open(lp))["fps"]} if os.path.exists(lp) else {}
        rows = []
        for r in sh["rows"]:
            o = live.get(key(r)) or {}
            rows.append(dict(match=r["Match"], player=r["Player"], market=r["Market"], line=r["Line"],
                             live_proj=o.get("Proj"), live_p=o.get("P(over)"), live_maps=o.get("Maps used"),
                             sh_proj=r.get("Proj"), sh_p=r.get("P(over)"), sh_maps=r.get("Maps used"),
                             actual=o.get("Actual"), result=o.get("Result")))
        slates[slate] = dict(built=sh.get("built"), source=sh.get("source"), matches=sh.get("matches"), rows=rows, compare=cmp.get(slate))
    return dict(variant=variant, registered=False, slates=slates)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="vetosim")
    ap.add_argument("--site", default="site/data/shadow.json", help="slim file for the Shadow tab; '' to skip")
    a = ap.parse_args()
    if a.site:
        os.makedirs(os.path.dirname(a.site), exist_ok=True)
        json.dump(site_data(a.variant), open(a.site, "w"), separators=(",", ":"), ensure_ascii=False)
    rep = compare(a.variant)
    for s, t in rep.items():
        print(s, "live", t["live"], "| shadow", t["shadow"], f"| sides differ on {t['differ']}: live right {t['differ_live_right']}, shadow right {t['differ_shadow_right']}")
    if not rep:
        print("no settled slate with a shadow file yet")


if __name__ == "__main__":
    main()
