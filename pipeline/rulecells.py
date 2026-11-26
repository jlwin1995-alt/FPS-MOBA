"""Each registered rule's forward record split by side (over / under) and prop type (kills / headshots):   python -m pipeline.rulecells
Reads every frozen plays file (data/plays/<slate>.json) and the settled Log (site/data/log/<slate>.json): a play is graded on the side the rule took, pushes and open legs are excluded.
H10 all_under is every FPS leg of the slate, under. Writes site/data/rulecells.json for the Scorecard. Descriptive: the cells are cuts of the same plays, so some will look good by chance;
the registered forward tests are the rules themselves."""
import glob, json, os
from collections import defaultdict

HLABEL = {"agree10": "H8", "all_under": "H10", "under_core": "H11", "l10_over": "H12", "agree20": "H13", "moba_lean20": "H14", "hs_side": "H15",
          "l10_hs_over": "H16", "lean25_l10_over": "H17", "top12": "H18"}
LOG = "site/data/log"
PLAYS = "data/plays"


def kind(market):
    return "HS" if "HS" in market else "Kills"


def build(plays_dir=PLAYS, log_dir=LOG):
    cells = defaultdict(lambda: [0, 0])
    slates = []
    for pf in sorted(glob.glob(os.path.join(plays_dir, "20*.json"))):
        s = os.path.basename(pf)[:-5]
        lp = os.path.join(log_dir, f"{s}.json")
        if not os.path.exists(lp):
            continue
        lg = json.load(open(lp)); p = json.load(open(pf))
        used = False
        for sec, rk in (("fps", "rules"), ("moba", "moba_rules")):
            res = {(r["Match"], r["Player"], r["Market"], float(r["Line"])): r.get("Result") for r in lg.get(sec, [])}
            for k, v in p.get(rk, {}).items():
                legs = ([dict(match=r["Match"], player=r["Player"], market=r["Market"], line=r["Line"], side="UNDER") for r in lg.get(sec, [])]
                        if k == "all_under" else v.get("legs", []))
                for l in legs:
                    r = res.get((l["match"], l["player"], l["market"], float(l["line"])))
                    if r not in ("OVER", "UNDER"):
                        continue
                    c = cells[(k, l["side"], kind(l["market"]))]
                    c[1] += 1; c[0] += r == l["side"]; used = True
        if used:
            slates.append(s)
    rows = [dict(rule=k, h=HLABEL.get(k, k), side=s, prop=pr, hits=h, n=n) for (k, s, pr), (h, n) in cells.items()]
    rows.sort(key=lambda r: (-r["hits"] / r["n"], -r["n"]))
    return dict(breakeven=0.5425, through=slates[-1] if slates else None, slates=len(slates), cells=rows)


def main():
    rep = build()
    os.makedirs("site/data", exist_ok=True)
    json.dump(rep, open("site/data/rulecells.json", "w"), separators=(",", ":"))
    print(f"{len(rep['cells'])} cells over {rep['slates']} slates, through {rep['through']}")


if __name__ == "__main__":
    main()
