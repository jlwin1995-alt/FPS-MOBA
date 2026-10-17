"""Fill CS2 matches that bo3.gg has no player tables for, from HLTV pages you captured in your own browser.

    python -m pipeline.hltv --slate 2026-10-17            # reads data/imports/<slate>/hltv/*.json, validates, merges into data/results/<slate>.json
    python -m pipeline.settle --slate 2026-10-17          # then settles the Log as usual

Nothing here talks to HLTV (it refuses automated access and is never routed around). docs/hltv-capture/ has the snippet you run on a match page.
A capture is one match:
  {"schema": 1, "source": "hltv.org", "url": "...", "captured_utc": "...", "teams": ["A", "B"],
   "maps": [{"n": 1, "map": "Anubis", "score": [13, 5], "players": [{"name": "stavn", "team": "A", "kills": 19, "hs": 3, "deaths": 9}, ...]}]}
Names: a team HLTV names differently from the board (a sponsor rename) goes in data/imports/<slate>/hltv/_aliases.json as {"HLTV name": "board name"}.
Rules: bo3.gg's numbers are never replaced (HLTV only fills a map bo3.gg has no players for, and must agree with bo3.gg on map name and score where both have them);
every map must pass the same identity checks as bo3.gg's (10 players, 5 per team, kills vs the other side's deaths, headshots <= kills, rounds = score total).
"""
import argparse, datetime as dt, glob, json, os, re
from .names import same_team, STOP, norm


def same_team_loose(board_name, *source_names):
    """same_team, plus a capture that uses a shorter name than the board ('Betclic' for 'Betclic Apogee Esports (BCA)'): a source name equal to one whole word of the board name."""
    if same_team(board_name, *source_names):
        return True
    words = {norm(w) for w in re.split(r"[^A-Za-z0-9]+", re.sub(r"\(.*?\)", "", board_name or "")) if len(w) >= 5 and w.lower() not in STOP}
    return any(norm(n) in words for n in source_names)
from .evaluate import norm_map


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def problems(cap):
    """Structural errors that make a capture unusable (checked before any identity check)."""
    bad = []
    if cap.get("schema") != 1:
        bad.append("schema must be 1")
    t = cap.get("teams")
    if not (isinstance(t, list) and len(t) == 2 and all(isinstance(x, str) and x for x in t)):
        bad.append("teams must be two names")
    if not cap.get("maps"):
        bad.append("no maps")
    seen = set()
    for m in cap.get("maps") or []:
        n = m.get("n")
        if not isinstance(n, int) or n < 1 or n in seen:
            bad.append(f"map number {n!r} missing or repeated")
        seen.add(n)
        s = m.get("score")
        if not (isinstance(s, list) and len(s) == 2 and all(isinstance(x, int) and x >= 0 for x in s)):
            bad.append(f"map {n}: score must be two whole numbers")
        for p in m.get("players") or []:
            if not (p.get("name") and p.get("team") and all(isinstance(p.get(k), int) and p[k] >= 0 for k in ("kills", "hs", "deaths"))):
                bad.append(f"map {n}: bad player row {p!r}")
    return bad


def checks(m):
    """The identity checks bo3.gg's maps get, for one captured map."""
    pl = m["players"]
    teams = {}
    for p in pl:
        teams.setdefault(p["team"], []).append(p)
    ts = list(teams)
    ok_n = len(pl) == 10 and len(teams) == 2 and all(len(v) == 5 for v in teams.values())
    if ok_n:
        k = {t: sum(x["kills"] for x in v) for t, v in teams.items()}
        d = {t: sum(x["deaths"] for x in v) for t, v in teams.items()}
        cross = 0 <= d[ts[1]] - k[ts[0]] <= 10 and 0 <= d[ts[0]] - k[ts[1]] <= 10
    else:
        cross = False
    return dict(map=m["n"], players_ok=ok_n, kills_vs_deaths_ok=bool(cross), hs_le_kills=all(p["hs"] <= p["kills"] for p in pl), rounds_ok=True)


def map_problems(c):
    """Structural errors in a one-map capture (what capture.js prints on a map-stats page)."""
    bad = []
    if c.get("schema") != 1 or c.get("kind") != "map":
        bad.append("schema 1 and kind 'map' required")
    if not (isinstance(c.get("teams"), list) and len(c["teams"]) == 2):
        bad.append("teams must be two names")
    return bad + problems(dict(schema=1, teams=c.get("teams"), maps=[dict(n=1, score=c.get("score"), players=c.get("players") or [])]))


def assemble(map_caps, board, cs2):
    """One-map captures -> match captures. A map's number comes from bo3.gg's list of the match's maps (by map name); any left over are numbered by HLTV map-stats id,
    which rises in play order. -> [(match capture, label)], [leftover map captures]"""
    out, used = [], set()
    for b in board:
        mine = [(c, p) for c, p in map_caps if (same_team_loose(b["a"], c["teams"][0]) and same_team_loose(b["b"], c["teams"][1])) or (same_team_loose(b["a"], c["teams"][1]) and same_team_loose(b["b"], c["teams"][0]))]
        if not mine:
            continue
        used |= {id(c) for c, _ in mine}
        names = [norm_map(m.get("map")) for m in (cs2.get(b["id"]) or {}).get("maps", [])]
        num, rest = {}, []
        for c, p in mine:
            nm = norm_map(c.get("map"))
            (num.__setitem__(names.index(nm) + 1, (c, p)) if nm in names and names.index(nm) + 1 not in num else rest.append((c, p)))
        free = [n for n in range(1, 6) if n not in num]
        for (c, p), n in zip(sorted(rest, key=lambda x: int(x[0].get("mapstatsid") or 0)), free):
            num[n] = (c, p)
        first = next(iter(num.values()))[0]
        cap = dict(schema=1, source="hltv.org", url=first.get("url"), captured_utc=max(c.get("captured_utc") or "" for c, _ in mine), teams=first["teams"],
                   maps=[dict(n=n, map=c.get("map"), score=c["score"], players=c["players"]) for n, (c, _) in sorted(num.items())])
        out.append((cap, ",".join(os.path.basename(p) for _, p in mine)))
    return out, [(c, p) for c, p in map_caps if id(c) not in used]


def link(board, caps):
    """board match id -> (capture, path). Both teams must match."""
    out = {}
    for b in board:
        for cap, path in caps:
            t1, t2 = cap["teams"]
            if (same_team_loose(b["a"], t1) and same_team_loose(b["b"], t2)) or (same_team_loose(b["a"], t2) and same_team_loose(b["b"], t1)):
                out[b["id"]] = (cap, path)
                break
    return out


def merge_match(old, cap, path):
    """-> (new match record, notes). `old` is bo3.gg's record or None."""
    notes, maps, chk = [], [], []
    old_by = {m["n"]: m for m in (old or {}).get("maps", [])}
    for m in sorted(cap["maps"], key=lambda x: x["n"]):
        o = old_by.pop(m["n"], None)
        c = checks(m)
        rounds = sum(m["score"])
        if o and o.get("players"):
            maps.append(o)                                    # bo3.gg's numbers stay
            chk.append(next(x for x in old["checks"] if x["map"] == m["n"]))
            continue
        if o:
            if o.get("map") and m.get("map") and norm_map(o["map"]) != norm_map(m.get("map")):
                c["players_ok"] = False
                notes.append(f"map {m['n']}: HLTV says {m.get('map')}, bo3.gg says {o['map']}")
            if o.get("score") and sorted(o["score"]) != sorted(m["score"]):
                c["rounds_ok"] = False
                notes.append(f"map {m['n']}: HLTV score {m['score']}, bo3.gg score {o['score']}")
        maps.append(dict(n=m["n"], map=(o or {}).get("map") or (f"de_{str(m['map']).lower()}" if m.get("map") else None), rounds=rounds, winner=(o or {}).get("winner"),
                         score=sorted(m["score"], reverse=True), state="done", site="hltv.org", players=[dict(name=p["name"], alias=p["name"], team=p["team"], kills=p["kills"], hs=p["hs"], deaths=p["deaths"]) for p in m["players"]]))
        chk.append(c)
    maps += list(old_by.values())                             # maps bo3.gg has and the capture lacks keep their (empty) tables
    chk += [x for x in (old or {}).get("checks", []) if x["map"] in {m["n"] for m in maps} and x["map"] not in {c["map"] for c in chk}]
    maps.sort(key=lambda m: m["n"])
    chk.sort(key=lambda c: c["map"])
    rec = dict(old or {})
    rec.update(status="finished", maps=maps, checks=chk, hltv=dict(file=os.path.basename(path), url=cap.get("url"), captured_utc=cap.get("captured_utc")))
    rec.setdefault("source", dict(site="hltv.org"))
    return rec, notes


def apply(slate, imports="data/imports", results_dir="data/results", site="site"):
    from .results import load_board, leg_actuals
    path = f"{results_dir}/{slate}.json"
    res = read(path)
    fps, _, _ = load_board(slate, site, imports)
    caps, map_caps, rejected = [], [], []
    ap = f"{imports}/{slate}/hltv/_aliases.json"                 # {"HLTV name": "board name"} for a team HLTV calls something else (a sponsor rename)
    alias = read(ap) if os.path.exists(ap) else {}
    for p in sorted(glob.glob(f"{imports}/{slate}/hltv/*.json")):
        if os.path.basename(p).startswith("_"):
            continue
        c = read(p)
        if isinstance(c.get("teams"), list):
            c["teams"] = [alias.get(t, t) for t in c["teams"]]
            for pl in c.get("players") or []:
                pl["team"] = alias.get(pl.get("team"), pl.get("team"))
            for mp in c.get("maps") or []:
                for pl in mp.get("players") or []:
                    pl["team"] = alias.get(pl.get("team"), pl.get("team"))
        is_map = c.get("kind") == "map"
        e = map_problems(c) if is_map else problems(c)
        (rejected.append((p, e)) if e else (map_caps if is_map else caps).append((c, p)))
    board = [m for m in fps["matches"] if m["title"] == "CS2"]
    cs2 = res["titles"]["CS2"]
    built, left = assemble(map_caps, board, cs2)
    for c, label in built:
        e = problems(c)
        (rejected.append((label, e)) if e else caps.append((c, label)))
    rejected += [(p, ["no board match for these teams"]) for _, p in left]
    links = link(board, caps)
    notes = {}
    for mid, (cap, p) in links.items():
        cs2[mid], notes[mid] = merge_match(cs2.get(mid), cap, p)
    res["legs"] = [l for l in res["legs"] if not (l["match"] in links)] + leg_actuals([g for g in fps["legs"] if g["title"] == "CS2" and g["match"] in links], fps["players"], cs2)
    res["hltv_merged"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, separators=(",", ":"), ensure_ascii=False)
    unmatched = [c["teams"] for c, p in caps if not any(c is x[0] for x in links.values())]
    return dict(linked=sorted(links), unmatched=unmatched, rejected=rejected, notes=notes, legs={mid: _count(res["legs"], mid) for mid in links})


def _count(legs, mid):
    from collections import Counter
    return dict(Counter(l["status"] for l in legs if l["match"] == mid))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    a = ap.parse_args()
    r = apply(a.slate)
    for mid in r["linked"]:
        print(mid, r["legs"][mid], *r["notes"][mid])
    for t in r["unmatched"]:
        print("no board match for capture", t)
    for p, e in r["rejected"]:
        print("REJECTED", p, e)
    if not r["linked"]:
        print("nothing merged: put captures in data/imports/<slate>/hltv/*.json")


if __name__ == "__main__":
    main()
