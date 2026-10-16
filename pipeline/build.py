"""Raw captures -> site/data/*.json.

    python -m pipeline.build [--raw data/raw] [--out site/data] [--date YYYY-MM-DD] [--no-log]

Inputs (data/raw): legs.csv (the board), logs.csv (player series history), matches.csv (moneylines, round margins, lineups).
With no legs.csv there, it builds from the synthetic league in data/sample and stamps meta.sample so the site shows a banner.
The first build of a slate also freezes it to data/log/board_<date>.psv; that file is never rewritten, so the Scorecard can't be flattered afterwards.
"""
import argparse, datetime as dt, os, shutil
from . import config as C
from . import model as M
from . import prob
from . import scorecard, backtest
from .store import read_rows, get, fnum, write_json, write_csv

APPS = [("ud", "Underdog"), ("sl", "Sleeper"), ("betr", "Betr"), ("pplay", "ParlayPlay"), ("dk", "DK Pick6")]


def checks(logs, legs, matches, asof):
    """The data-quality checks from the Esports Data Dictionary that can be run mechanically."""
    ident = [r for r in logs if fnum(r.get("m1_k")) is not None and fnum(r.get("m2_k")) is not None and fnum(r.get("m12_k")) is not None]
    bad = [r for r in ident if fnum(r["m1_k"]) + fnum(r["m2_k"]) != fnum(r["m12_k"])]
    ident3 = [r for r in logs if all(fnum(r.get(k)) is not None for k in ("m1_k", "m2_k", "m3_k", "m123_k"))]
    bad3 = [r for r in ident3 if fnum(r["m1_k"]) + fnum(r["m2_k"]) + fnum(r["m3_k"]) != fnum(r["m123_k"])]
    lo = (dt.date.fromisoformat(asof) - dt.timedelta(days=C.RECENCY_DAYS)).isoformat()
    stale = [r for r in logs if r["date"] < lo]
    per_player = {}
    for g in legs:
        per_player.setdefault((g["title"], g["player"], g["stat"]), set()).add(g["match_id"])
    multi = [k for k, v in per_player.items() if len(v) > 1]
    return [
        dict(name="Kill sums: map 1 + map 2 = maps 1-2", rows=len(ident), bad=len(bad), note="A free check on every row of a player page."),
        dict(name="Kill sums: maps 1 + 2 + 3 = maps 1-3", rows=len(ident3), bad=len(bad3), note="Only Bo3s that went the distance."),
        dict(name=f"Recency: history older than {C.RECENCY_DAYS} days", rows=len(logs), bad=len(stale), note="Dropped from every projection; a player's 15 rows once ran back 19 months."),
        dict(name="One player in several matches on the board", rows=len(per_player), bad=len(multi), note="Bo1 groups: every join keys on the team pair, not the player."),
        dict(name="Matches with no moneyline", rows=len(matches), bad=sum(1 for m in matches if fnum(m.get("ml_a")) is None or fnum(m.get("ml_b")) is None), note="Bo1s and small events are often unpriced."),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="site/data")
    ap.add_argument("--date", default=None)
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args()

    sample = not os.path.exists(os.path.join(a.raw, "legs.csv"))
    raw = "data/sample" if sample else a.raw
    log_dir = os.path.join(raw, "log") if sample else "data/log"
    if sample and not os.path.exists(os.path.join(raw, "legs.csv")):
        from . import sample_data
        sample_data.generate(a.date or dt.date.today().isoformat(), raw)
    legs_raw, logs, matches_raw = read_rows(os.path.join(raw, "legs.csv")), read_rows(os.path.join(raw, "logs.csv")), read_rows(os.path.join(raw, "matches.csv"))
    slate = a.date or (min(get(g, "start", "")[:10] for g in legs_raw) if legs_raw else dt.date.today().isoformat())
    tmeans = M.title_means(logs, slate)
    mt = {get(m, "match_id"): m for m in matches_raw}

    legs, proj = [], []
    for g in legs_raw:
        stat = get(g, "stat")
        if stat not in C.STATS:
            continue
        legs.append(dict(g, title=get(g, "title"), player=get(g, "player"), match_id=get(g, "match_id"), stat=stat, leg_id=get(g, "leg_id")))
    for g in legs:
        line = fnum(get(g, "line"))
        hist = M.player_history(logs, g["title"], g["player"], g["stat"], slate)
        vals = [v for _, v in hist]
        pr = M.project(vals, tmeans.get((g["title"], g["stat"])), g["stat"])
        m = mt.get(g["match_id"], {})
        lineup = [x for x in (m.get("lineup_a", "") + "|" + m.get("lineup_b", "")).split("|") if x]
        flags = []
        if pr and pr["n"] < 8:
            flags.append("thin")
        if not pr:
            flags.append("nohist")
        if lineup and g["player"] not in lineup:
            flags.append("lineup")
        apps = {k: fnum(g.get("line_" + k)) for k, _ in APPS}
        row = dict(id=g["leg_id"], title=g["title"], kind=C.KIND.get(g["title"], ""), match=g["match_id"], start=get(g, "start"), league=g.get("league"),
                   player=g["player"], team=g.get("team"), opp=g.get("opp"), pos=g.get("pos"), stat=g["stat"], label=C.STATS[g["stat"]]["label"],
                   line=line, alt=int(fnum(g.get("alt"), 0) or 0), apps={k: v for k, v in apps.items() if v is not None},
                   hr={k: fnum(g.get("hr_" + k)) for k in ("l5", "l10", "l15", "season")}, h2h=[fnum(g.get("h2h_hits")), fnum(g.get("h2h_games"))],
                   avg10=fnum(g.get("avg10")), ml=fnum(g.get("ml_team")), ml_opp=fnum(g.get("ml_opp")),
                   fav=[fnum(g.get("fav_over")), fnum(g.get("fav_under"))], hist=[v for _, v in reversed(hist)], flags=flags)
        if pr and line is not None:
            sd = prob.sigma(g["stat"], pr["proj"], pr["sd"])
            po, pu = prob.sides(line, pr["proj"], sd)
            row.update(proj=round(pr["proj"], 2), naive=round(pr["naive"], 2), sd=round(sd, 2), n=pr["n"], p_over=round(po, 4), z=round((pr["proj"] - line) / sd, 3),
                       variants={k: round(v, 2) for k, v in pr["variants"].items()}, l5=round(sum(vals[:5]) / len(vals[:5]), 2))
        proj.append(row)

    # matches: de-vigged moneyline, round margins, leg counts
    mrows = []
    for m in matches_raw:
        pa, pb = prob.devig2(m.get("ml_a"), m.get("ml_b"))
        mid = get(m, "match_id")
        mrows.append(dict(id=mid, title=get(m, "title"), start=get(m, "start"), a=m.get("team_a"), b=m.get("team_b"), bo=fnum(m.get("bo")),
                          ml_a=fnum(m.get("ml_a")), ml_b=fnum(m.get("ml_b")), p_a=pa, p_b=pb, margin_a=fnum(m.get("margin_a")), margin_b=fnum(m.get("margin_b")),
                          lineup_a=[x for x in m.get("lineup_a", "").split("|") if x], lineup_b=[x for x in m.get("lineup_b", "").split("|") if x],
                          legs=sum(1 for p in proj if p["match"] == mid)))

    # freeze the board once, before lock
    if not (sample or a.no_log):
        path = f"data/log/board_{slate}.psv"
        if not os.path.exists(path):
            rows = [dict(title=p["title"], match=p["match"], player=p["player"], market=p["label"], line=p["line"], proj_a=p.get("variants", {}).get("a"),
                         proj_b=p.get("variants", {}).get("b"), proj_c=p.get("variants", {}).get("c"), naive=p.get("naive"), registered=1) for p in proj]
            write_csv(path, rows, ["title", "match", "player", "market", "line", "proj_a", "proj_b", "proj_c", "naive", "registered"], "|")

    nres, ndays = scorecard.build(log_dir, a.out)
    bt = backtest.run(logs, slate)
    write_json(os.path.join(a.out, "backtest.json"), bt)
    write_json(os.path.join(a.out, "projections.json"), proj)
    write_json(os.path.join(a.out, "matches.json"), mrows)
    write_json(os.path.join(a.out, "coverage.json"), dict(checks=checks(logs, legs, matches_raw, slate), apps=[dict(app="PrizePicks", legs=sum(1 for p in proj if p["line"] is not None))] +
               [dict(app=n, legs=sum(1 for p in proj if k in p["apps"])) for k, n in APPS],
               titles=[dict(title=t, legs=sum(1 for p in proj if p["title"] == t), players=len({p["player"] for p in proj if p["title"] == t})) for t in C.TITLES],
               stats=[dict(stat=s, label=v["label"], legs=sum(1 for p in proj if p["stat"] == s)) for s, v in C.STATS.items()]))
    write_json(os.path.join(a.out, "meta.json"), dict(
        generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), slate=slate, sample=sample, legs=len(proj), projected=sum(1 for p in proj if "proj" in p),
        matches=len(mrows), players=len({(p["title"], p["player"]) for p in proj}), history_rows=len(logs), settled=nres, settled_days=ndays,
        stats={k: dict(label=v["label"], maps=list(v["maps"]), hs=v["hs"]) for k, v in C.STATS.items()}, titles=C.TITLES, kind=C.KIND,
        sd_floor=C.SD_FLOOR, sd_rel_floor=C.SD_REL_FLOOR, lean=C.LEAN, strong=C.STRONG, breakeven=C.PP_BE,
        model=dict(name="baseline (placeholder)", w=[C.W_L5, C.W_L10, C.W_REST], shrink_n=C.SHRINK_N, recency_days=C.RECENCY_DAYS, min_games=C.MIN_GAMES)))
    print(f"{'SAMPLE ' if sample else ''}slate {slate}: {len(proj)} legs ({sum(1 for p in proj if 'proj' in p)} projected), {len(mrows)} matches, {nres} settled legs over {ndays} days -> {a.out}")


if __name__ == "__main__":
    main()
