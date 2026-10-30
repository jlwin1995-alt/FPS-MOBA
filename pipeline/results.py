"""Pull the day's results for a slate and work out every leg's Actual.

    python -m pipeline.results --slate 2026-10-16 [--titles CS2,VAL,LOL,DOTA]
    python -m pipeline.settle  --slate 2026-10-16          # applies data/results/<slate>.json to the Log (frozen values are never touched)

Sources (the ones the data dictionary names; HLTV is behind Cloudflare and is never routed around):
  CS2  bo3.gg   per-map player tables, second route = the match-level table
  VAL  vlr.gg   per-map player tables, check = the all-maps tab equals the sum of the maps
  LOL  gol.gg   per-game player kills, check = the team header equals the sum of the players
  DOTA OpenDota per-game player kills, checks = the team score is within 2 of the players' sum, and each player's kills in his own recent-match list equal the game table
A leg is only given an Actual when its match is finished, the player is found in the map tables, and the map identities hold.
Everything else is reported with a reason (void, did not play, unmatched, not finished), never guessed.
"""
import argparse, datetime as dt, json, os
from .names import same_team, same_player

NEED = {"K1": [1], "H1": [1], "K12": [1, 2], "H12": [1, 2], "K13": [1, 2, 3], "H13": [1, 2, 3]}          # maps a market needs
CT = dt.timedelta(hours=5)                                   # board start times are US Central (daylight time in October)


def load_board(slate, site="site", imports="data/imports"):
    """-> (fps, moba, where). The live slate's inputs are on the site; an older slate is read back from its own workbooks in data/imports,
    so settling Friday after Saturday's build never uses Saturday's board."""
    with open(f"{site}/data/meta.json", encoding="utf-8") as f:
        live = json.load(f).get("slate")
    if live == slate:
        with open(f"{site}/data/fps.json", encoding="utf-8") as f1, open(f"{site}/data/moba.json", encoding="utf-8") as f2:
            return json.load(f1), json.load(f2), "site"
    d = f"{imports}/{slate}"
    if not os.path.exists(f"{d}/fps.xlsx"):
        raise SystemExit(f"no board for slate {slate}: the site holds {live} and {d}/ has no fps.xlsx")
    from .import_xlsx import import_fps, import_moba, empty_moba
    moba = import_moba(f"{d}/moba.xlsx")[1] if os.path.exists(f"{d}/moba.xlsx") else empty_moba(slate, site)       # a CS2-only day has no MOBA workbook
    return import_fps(f"{d}/fps.xlsx")[1], moba, "workbooks"


def board_start_utc(slate, label):
    """'Fri 03:00' on the slate date -> UTC datetime (the weekday word is ignored: the slate date fixes the day)."""
    hh, mm = label.split()[-1].split(":")
    d = dt.datetime.fromisoformat(slate) + dt.timedelta(hours=int(hh), minutes=int(mm))
    return d + CT


def iso_utc(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None) if s.endswith("Z") or "+" in s[10:] else dt.datetime.fromisoformat(s)


def link_matches(slate, board, cands, team_names):
    """Pair each board match with a finished source match. cands: [{id, t1:[names], t2:[names], start(datetime), ref}].
    Both teams matching accepts up to a day of drift; one team matching needs the start within 4 hours and no rival."""
    out, used = {}, set()
    for b in board:
        exp = board_start_utc(slate, b["start"])
        scored = []
        for c in cands:
            if c["id"] in used:
                continue
            a1, a2 = same_team(b["a"], *c["t1"]), same_team(b["a"], *c["t2"])
            b1, b2 = same_team(b["b"], *c["t1"]), same_team(b["b"], *c["t2"])
            both = (a1 and b2) or (a2 and b1)
            one = a1 or a2 or b1 or b2
            gap = abs((c["start"] - exp).total_seconds()) / 3600
            if both and gap <= 24:
                scored.append((0, gap, c))
            elif one and gap <= 4:
                scored.append((1, gap, c))
        scored.sort(key=lambda x: (x[0], x[1]))
        if scored:
            out[b["id"]] = dict(cand=scored[0][2], how="both teams" if scored[0][0] == 0 else "one team + start time", gap_h=round(scored[0][1], 2),
                                rivals=len(scored) - 1)
            used.add(scored[0][2]["id"])
    return out


# ------------------------------------------------------------------ CS2
def apply_player_fixes(match_id, maps, fixes):
    """A map's table that bo3.gg labels with the wrong player (a stand-in's name on the real player's seat). `fixes` rows: {match, map, from, to, why}; the rename is recorded on the match so it shows in the results file."""
    done = []
    for f in fixes:
        if f["match"] != match_id:
            continue
        for mp in maps:
            if mp["n"] != f["map"]:
                continue
            for p in mp["players"]:
                if p["name"] == f["from"]:
                    p["name"], p["alias"] = f["to"], f["to"]
                    done.append(dict(f))
    return done


def pull_cs2(slate, fps, imports="data/imports"):
    from .sources import bo3
    d0 = dt.datetime.fromisoformat(slate)
    ms = list(bo3.finished_matches((d0 - dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M"), (d0 + dt.timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M")))
    cands = [dict(id=m["id"], t1=[(m.get("team1") or {}).get("name"), (m.get("team1") or {}).get("slug")], t2=[(m.get("team2") or {}).get("name"), (m.get("team2") or {}).get("slug")],
                  start=iso_utc(m["start_date"]), ref=m) for m in ms if m.get("team1") and m.get("team2")]
    board = [m for m in fps["matches"] if m["title"] == "CS2"]
    links = link_matches(slate, board, cands, None)
    out = {}
    for b in board:
        L = links.get(b["id"])
        if not L:
            out[b["id"]] = dict(status="not found among finished matches", maps=[])
            continue
        m = L["cand"]["ref"]
        r = bo3.match_maps(m)
        fx = f"{imports}/{slate}/bo3_fixes.json"                  # [{"match", "map", "from", "to", "why"}]: bo3.gg names a stand-in on a map where the real player (same kills on HLTV) played
        applied = apply_player_fixes(b["id"], r["maps"], json.load(open(fx, encoding="utf-8")) if os.path.exists(fx) else [])
        out[b["id"]] = dict(status="finished", source=dict(site="bo3.gg", slug=m["slug"], score=[m["team1_score"], m["team2_score"]], bo=m["bo_type"], start=m["start_date"]),
                            linked=dict(how=L["how"], start_gap_h=L["gap_h"], rivals=L["rivals"]), maps=r["maps"], checks=r["checks"], route2=r["route2"], **(dict(player_fixes=applied) if applied else {}))
    return out


# ------------------------------------------------------------------ LoL
def pull_lol(slate, moba, imports="data/imports"):
    from .sources import gol
    d0 = dt.date.fromisoformat(slate)
    board = [m for m in moba["matches"] if m["id"].startswith("LOL")]
    events = sorted({m["event"] for m in board})
    tl = json.loads(_gol_trlist())
    trs = [t["trname"] for t in tl if any(t["trname"].startswith(e) for e in events) and t["lastgame"] >= (d0 - dt.timedelta(days=1)).isoformat()]
    cands = []
    for tr in trs:
        for sr in gol.series_list(tr):
            if sr["played"]:
                cands.append(dict(id=sr["id"], t1=[sr["teams"][0]], t2=[sr["teams"][1]], start=dt.datetime.fromisoformat(sr["date"]) + dt.timedelta(hours=18), ref=dict(sr, tournament=tr)))
    ap = f"{imports}/{slate}/lol_aliases.json"                   # {"gol.gg team name": "board name"} for a team the two spell differently ('Los Grandes' / 'LOS')
    alias = json.load(open(ap, encoding="utf-8")) if os.path.exists(ap) else {}
    for c in cands:
        c["t1"], c["t2"] = [alias.get(x, x) for x in c["t1"]], [alias.get(x, x) for x in c["t2"]]
    links = link_matches(slate, board, cands, None)
    out = {}
    for b in board:
        L = links.get(b["id"])
        if not L:
            out[b["id"]] = dict(status="not found among finished matches", maps=[])
            continue
        r = L["cand"]["ref"]
        d = gol.series_maps(r["id"], single=r.get("single", False))
        out[b["id"]] = dict(status="finished", source=dict(site="gol.gg", slug=f"/game/stats/{r['id']}/page-summary/", score=r["score"], bo=b["bo"], start=r["date"], tournament=r["tournament"]),
                            linked=dict(how=L["how"], start_gap_h=L["gap_h"], rivals=L["rivals"]), maps=d["maps"], checks=d["checks"], route2=d["route2"])
    return out


def pull_dota(slate, moba, imports="data/imports"):
    from .sources import opendota
    board = [m for m in moba["matches"] if m["id"].startswith("DOTA")]
    if not board:
        return {}
    d0 = dt.datetime.fromisoformat(slate).replace(tzinfo=dt.timezone.utc)
    cands = [dict(id=sr["series_id"], t1=[sr["teams"][0]], t2=[sr["teams"][1]], start=dt.datetime.fromtimestamp(sr["start"], dt.timezone.utc).replace(tzinfo=None), ref=sr)
             for sr in opendota.pro_series(int((d0 - dt.timedelta(hours=6)).timestamp()))]
    links = link_matches(slate, board, cands, None)
    ap = f"{imports}/{slate}/dota_aliases.json"                  # {"board name": "OpenDota name"} for a handle the two spell differently
    alias = json.load(open(ap, encoding="utf-8")) if os.path.exists(ap) else {}
    out = {}
    for b in board:
        L = links.get(b["id"])
        if not L:
            out[b["id"]] = dict(status="not found among finished matches", maps=[])
            continue
        sr = L["cand"]["ref"]
        if not opendota.finished(sr):
            out[b["id"]] = dict(status="not finished", maps=[], detail=f"wins so far {opendota.wins(sr)} of a best of {sr['bo']}")
            continue
        r = opendota.series_maps(sr)
        for mp in r["maps"]:
            for p in mp["players"]:
                for bname, oname in alias.items():
                    if p["name"] == oname or p.get("alias") == oname:
                        p["alias"] = bname
        out[b["id"]] = dict(status="finished", source=dict(site="opendota.com", slug=f"series {sr['series_id']}", score=sorted(opendota.wins(sr).values(), reverse=True), bo=sr["bo"], start=sr["start"]),
                            linked=dict(how=L["how"], start_gap_h=L["gap_h"], rivals=L["rivals"]), maps=r["maps"], checks=r["checks"], route2=r["route2"])
    return out


def _gol_trlist():
    import urllib.request
    req = urllib.request.Request("https://gol.gg/tournament/ajax.trlist.php", data=b"season=S16", headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=40).read().decode()


# ------------------------------------------------------------------ Valorant
def pull_val(slate, fps):
    from .sources import vlr
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    rs = vlr.recent_results(pages=2)
    cands = [dict(id=r["id"], t1=[r["teams"][0]], t2=[r["teams"][1]], start=now - dt.timedelta(hours=r["ago_h"] + 1.5), ref=r)
             for r in rs if len(r["teams"]) == 2 and r["ago_h"] is not None]
    board = [m for m in fps["matches"] if m["title"] == "VAL"]
    links = link_matches(slate, board, cands, None)
    out = {}
    for b in board:
        L = links.get(b["id"])
        if not L:
            out[b["id"]] = dict(status="not found among finished matches", maps=[])
            continue
        r = L["cand"]["ref"]
        d = vlr.match_maps(r["id"])
        out[b["id"]] = dict(status="finished", source=dict(site="vlr.gg", slug=r["slug"], score=r["score"], bo=b["bo"], start=None), linked=dict(how=L["how"], start_gap_h=L["gap_h"], rivals=L["rivals"]),
                            maps=d["maps"], checks=d["checks"], route2=d["route2"])
    return out


def leg_actuals(legs, players, matches):
    """Every leg of this title -> {status, actual, ...}. Statuses, in the order they are decided:
    match not found / not finished · void: map not played (a Bo1 has no map 2) · no player stats at source (the source has the map, not the table)
    · did not play (not in the map's table: a stand-in) · identity check failed · ok"""
    P = {p["pid"]: p for p in players}
    out = []
    for g in legs:
        pid = g["key"].split("|")[0]
        name = (P.get(pid) or {}).get("player") or g["player"]
        rec = dict(match=g["match"], player=g["player"], market=g["market"], code=g["code"], key=g["key"], line=g["line"])
        mr = matches.get(g["match"])
        if not mr or mr["status"] != "finished":
            out.append(dict(rec, status="match not found / not finished"))
            continue
        need = NEED[g["code"]]
        by_n = {mp["n"]: mp for mp in mr["maps"]}
        if any(n not in by_n for n in need):
            out.append(dict(rec, status="void: map not played"))
            continue
        if any(not by_n[n]["players"] for n in need):
            out.append(dict(rec, status="no player stats at source", detail=f"maps {[by_n[n]['map'] for n in need if not by_n[n]['players']]}"))
            continue
        rows, missing = [], None
        for n in need:
            cand = [p for p in by_n[n]["players"] if same_player(name, p["name"]) or same_player(name, p.get("alias"))]
            exact = [p for p in cand if (p["name"] or "").lower() == name.lower() or (p.get("alias") or "").lower() == name.lower()]
            cand = exact or cand
            if len(cand) != 1:
                missing = (n, len(cand))
                break
            rows.append(cand[0])
        if missing:
            n, k = missing
            out.append(dict(rec, status="did not play / not in the map tables" if k == 0 else "ambiguous player", detail=f"{k} rows for '{name}' on map {n}"))
            continue
        checks = [c for c in mr["checks"] if c["map"] in need]
        ok = all(c["players_ok"] and c["kills_vs_deaths_ok"] and c["hs_le_kills"] and c["rounds_ok"] for c in checks)
        field = "hs" if g["code"][0] == "H" else "kills"
        total = sum(r[field] for r in rows)
        extra = dict(team=rows[-1]["team"], maps=[by_n[n]["map"] for n in need], checked=ok)
        if any(by_n[n].get("site") for n in need):
            extra["source"] = ", ".join(sorted({by_n[n].get("site") or "bo3.gg" for n in need}))
        # an unverified number is kept apart from `actual` so nothing downstream can mistake it for a settled value
        out.append(dict(rec, status="ok", actual=total, **extra) if ok else dict(rec, status="identity check failed", unverified=total, **extra))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--titles", default="CS2,VAL,LOL,DOTA")
    ap.add_argument("--site", default="site")
    ap.add_argument("--out", default="data/results")
    a = ap.parse_args()
    fps, moba, where = load_board(a.slate, a.site)
    print(f"board for {a.slate} read from the {where}")
    res = dict(slate=a.slate, generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), titles={}, legs=[])
    for t in a.titles.split(","):
        if t == "CS2":
            m = pull_cs2(a.slate, fps)
            res["titles"]["CS2"] = m
            res["legs"] += leg_actuals([g for g in fps["legs"] if g["title"] == "CS2"], fps["players"], m)
        elif t == "VAL":
            m = pull_val(a.slate, fps)
            res["titles"]["VAL"] = m
            res["legs"] += leg_actuals([g for g in fps["legs"] if g["title"] == "VAL"], fps["players"], m)
        elif t == "LOL":
            m = pull_lol(a.slate, moba)
            res["titles"]["LOL"] = m
            res["legs"] += leg_actuals([g for g in moba["legs"] if g["match"].startswith("LOL")], moba["players"], m)
        elif t == "DOTA":
            m = pull_dota(a.slate, moba)
            res["titles"]["DOTA"] = m
            res["legs"] += leg_actuals([g for g in moba["legs"] if g["match"].startswith("DOTA")], moba["players"], m)
    os.makedirs(a.out, exist_ok=True)
    path = f"{a.out}/{a.slate}.json"
    json.dump(res, open(path, "w"), separators=(",", ":"), ensure_ascii=False)
    from collections import Counter
    print(path, dict(Counter(l["status"] for l in res["legs"])))


if __name__ == "__main__":
    main()
