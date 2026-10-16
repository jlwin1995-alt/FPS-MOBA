"""Build a PickFinder capture in the documented format from a slate that is already on the site (the workbook import).

    python -m pipeline.pickfinder_example --out docs/pickfinder-capture/example --matches "CS2 · AST vs MIBR" "VAL · VIT vs LOUD" "LOL · KC vs MVK"

Used as the living example of the format (it must always validate: pipeline/test_pickfinder.py checks it) and as the round-trip test input:
real numbers in, the loader must give the same numbers back.
"""
import argparse, datetime as dt, json, os, re
from .pickfinder import SCHEMA, Capture, jload
from .results import board_start_utc


def parse_pick(s):
    m = re.match(r"(.+?)\s+(\d+)%$", s or "")
    return dict(map=m.group(1), pct=int(m.group(2))) if m else None


def iso_date(mmdd, slate):
    mo, d = (int(x) for x in mmdd.split("/"))
    y = int(slate[:4])
    if mo > int(slate[5:7]):
        y -= 1
    return f"{y:04d}-{mo:02d}-{d:02d}"


def from_site(site="site", matches=None):
    fps, moba = jload(f"{site}/data/fps.json"), jload(f"{site}/data/moba.json")
    slate = fps["slate"]
    keep = set(matches) if matches else None
    start_of = {m["id"]: board_start_utc(slate, m["start"]).strftime("%Y-%m-%dT%H:%M:%SZ") for m in fps["matches"] + moba["matches"]}
    picks_of = {m["id"]: [x for x in (parse_pick(m.get("pick1")), parse_pick(m.get("pick2")), parse_pick(m.get("pick3"))) if x] for m in fps["matches"]}
    legs, players = [], {}
    P = {p["pid"]: p for p in fps["players"] + moba["players"]}
    for src in (fps, moba):
        for g in src["legs"]:
            if keep and g["match"] not in keep:
                continue
            pid = g["key"].split("|")[0]
            a, b = [s.strip() for s in g["match"].split(" · ", 1)[1].split(" vs ")]
            title = g.get("title") or g["match"].split(" ")[0]
            legs.append(dict(title=title, match=g["match"], player=g["player"], pid=pid, team=g["team"], opp=b if g["team"] == a else a, market=g["market"], line=g["line"], alt=False,
                             start=start_of.get(g["match"]), league=None, tournament=None, pos=None,
                             hit=dict(avg10=g.get("avg10"), l5=g.get("l5"), l10=g.get("l10"), l15=g.get("l15"), h2h=g.get("h2h"), streak=g.get("streak"))))
    pids = {g["pid"] for g in legs}
    glog = {}
    for r in moba["gamelog"]:
        glog.setdefault(r["player"], []).append(r)
    for pid in sorted(pids):
        p = P[pid]
        base = dict(pid=pid, player=p["player"], title=p["title"], team=p["team"], matchup=p.get("matchup"), url=p.get("url"), captured_utc=None)
        if p["title"] in ("CS2", "VAL"):
            mt = next(g["match"] for g in legs if g["pid"] == pid)
            players[pid] = dict(base, overall=dict(maps=p["maps"], kills_map=p["kills_map"], kpr=p["kpr"], hs=p["hs"], hs_round=p["hs_round"], kd=p["kd"], rating=p["rating"]),
                                map_stats=[dict(map=k, **v) for k, v in fps["mapstats"][pid].items()], map_picks=dict(matchup=p.get("matchup"), maps=picks_of.get(mt, [])))
        else:
            players[pid] = dict(base, role=p.get("role"), overall=dict(maps=p["maps"], win_rate=p["q"], k=p["k"], d=p["d"], a=p["a"], kd=p["kd"]),
                                gamelog=[dict(date=iso_date(r["date"], slate), opp=r["opp"], m1k=r["m1"], m2k=r["m2"], m3k=r["m3"], m12k=r["m12"], m123k=r["m13"]) for r in glog.get(p["player"], [])])
    built = (fps.get("built") or f"{slate} 00:00").replace(" ", "T") + ":00Z"
    meta = dict(schema=SCHEMA, slate=slate, captured_utc=built, source="pickfinder.app", tool="example built from the workbook import", expected_legs=len(legs),
                notes=["board.json is the PrizePicks board; one file per player under players/ so a capture can save after each player and resume"])
    return Capture(meta, legs, players)


def write(cap, out):
    os.makedirs(os.path.join(out, "players"), exist_ok=True)
    def dump(p, o):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(o, f, indent=1, ensure_ascii=False)

    dump(os.path.join(out, "capture.json"), cap.meta)
    dump(os.path.join(out, "board.json"), dict(legs=cap.legs))
    for pid, p in cap.players.items():
        dump(os.path.join(out, "players", f"{pid}.json"), p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", default="site")
    ap.add_argument("--matches", nargs="*")
    a = ap.parse_args()
    cap = from_site(a.site, a.matches)
    write(cap, a.out)
    print(f"wrote {a.out}: {len(cap.legs)} legs, {len(cap.players)} players")


if __name__ == "__main__":
    main()
