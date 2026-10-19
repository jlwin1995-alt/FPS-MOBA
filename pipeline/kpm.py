"""'Kills per map' shadow projection: a player's career kills per map x the maps that count, with no map names and no rounds.

    python -m pipeline.kpm --backfill 2026-10-16      # adds Proj KPM / P(over) KPM to a slate's Log rows that lack them (inputs only, no results used)

Maps 1: kills/map; Maps 1-2: 2 x kills/map; Maps 1-3: (2 + P(map 3)) x kills/map; headshots: the same x his overall HS%.
Spread and probabilities exactly as the workbook's model (KILLS_DISPERSION, headshots through binomial thinning, a whole-number line keeps its push probability).
It is a SHADOW: the workbook's KPR x rounds projection stays the published number, and the two are scored side by side (evaluate.py, hypothesis H9).
The same arithmetic is in site/fps.js (calcAll, `out.kpm`) so the Projections tab can show it; test_kpm.py checks the two agree.
"""
import argparse, json, math

N_MAPS = {"K1": 1, "H1": 1, "K12": 2, "H12": 2}


def norm_cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def over_under(line, mean, sd):
    if not isinstance(line, (int, float)) or mean is None or not sd or sd <= 0:
        return None
    po = 1 - norm_cdf((math.floor(line) + 0.5 - mean) / sd)
    pu = norm_cdf((math.ceil(line) - 0.5 - mean) / sd)
    return po, pu


def project(fps):
    """-> {(match, player, market): dict(proj, sigma, p_over, p_under)} for every leg that has a PickFinder kills/map."""
    players = {p["pid"]: p for p in fps["players"]}
    matches = {m["id"]: m for m in fps["matches"]}
    disp = fps["config"]["KILLS_DISPERSION"]
    out = {}
    for g in fps["legs"]:
        p, m = players.get(g["key"].split("|")[0]), matches.get(g["match"])
        if not p or not m or not isinstance(p.get("kills_map"), (int, float)) or not p["kills_map"]:
            continue
        code = g["code"]
        n = N_MAPS.get(code)
        if n is None and code in ("K13", "H13"):
            n = 2 + (m.get("p3_used") or 0)
        if n is None:
            continue
        hs = code[0] == "H"
        if hs and not isinstance(p.get("hs"), (int, float)):
            continue
        proj = p["kills_map"] * n * (p["hs"] if hs else 1)
        ap = p["hs"] if hs and isinstance(p.get("hs"), (int, float)) else 0
        sigma = math.sqrt(proj * ((ap * disp + 1 - ap) if hs else disp))
        pr = over_under(g["line"], proj, sigma)
        out[(g["match"], g["player"], g["market"])] = dict(proj=proj, sigma=sigma, p_over=pr[0] if pr else None, p_under=pr[1] if pr else None)
    return out


def add_to_log(log_rows, fps):
    """Add the two shadow columns to FPS Log rows that do not have them (frozen like every other Log column). Returns the number of rows filled."""
    sh = project(fps)
    n = 0
    for r in log_rows:
        if "Proj KPM" in r:
            continue
        v = sh.get((r.get("Match"), r.get("Player"), r.get("Market")))
        r["Proj KPM"] = round(v["proj"], 4) if v else None
        r["P(over) KPM"] = round(v["p_over"], 4) if v and v["p_over"] is not None else None
        n += 1 if v else 0
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", required=True, help="slate date; reads data/imports/<slate>/fps.xlsx and site/data/log/<slate>.json")
    ap.add_argument("--site", default="site")
    ap.add_argument("--imports", default="data/imports")
    a = ap.parse_args()
    from .import_xlsx import import_fps, dump
    _, fps, _, _ = import_fps(f"{a.imports}/{a.backfill}/fps.xlsx")
    path = f"{a.site}/data/log/{a.backfill}.json"
    with open(path, encoding="utf-8") as f:
        log = json.load(f)
    n = add_to_log(log["fps"], fps)
    dump(path, log)
    print(f"{a.backfill}: {n} of {len(log['fps'])} Log rows got a kills-per-map projection")


if __name__ == "__main__":
    main()
