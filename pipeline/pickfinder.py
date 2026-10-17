"""Receiving end for a PickFinder capture: load, validate, cross-check and (optionally) convert.

    python -m pipeline.pickfinder --slate 2026-10-16                 # validate data/raw/pickfinder/<slate>/ (exit 1 on any error)
    python -m pipeline.pickfinder --slate 2026-10-16 --crosscheck    # also compare with the slate already on the site (e.g. from the workbook)
    python -m pipeline.pickfinder --slate 2026-10-16 --build-out data/derived/2026-10-16   # PickFinder-only fps.json / moba.json

The capture is made by a session that has a logged-in PickFinder tab (see docs/pickfinder-capture/README.md for the exact format).
Nothing here talks to PickFinder: this is only what happens to the files afterwards.

Checks (errors stop the slate, warnings are reported):
  * the board count the capture tool saw equals the legs in board.json (the page-cap guard)
  * every board player has a player file (the workbook's "board players with no stats page read")
  * the workbook's identity: per-map n sums to overall maps, and the n-weighted kills/map equals overall kills/map
  * LoL/Dota gamelog identity: M1 + M2 = M1-2 and M1-2 + M3 = M1-3 on every row
  * hit rates are in [0,1] (warning when not an exact k/5, k/10, k/15, which catches shifted columns)
  * no duplicate (match, player, market) leg: one player can be in several matches a day, so the match is part of the key
"""
import argparse, datetime as dt, glob, json, os, sys

SCHEMA = 1
TITLES = {"CS2", "VAL", "LOL", "DOTA"}
FPS_TITLES, MOBA_TITLES = {"CS2", "VAL"}, {"LOL", "DOTA"}
CODE = {"Map 1 Kills": "K1", "Maps 1-2 Kills": "K12", "Maps 1-3 Kills": "K13", "Map 1 HS": "H1", "Maps 1-2 HS": "H12"}
KILL_TOL = 0.06                     # weighted kills/map vs overall: the workbook's own data differs by up to 0.036 from rounding
RECENCY_DAYS = 120
GRAIN = {"l5": 5, "l10": 10, "l15": 15}


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Capture:
    def __init__(self, meta, legs, players):
        self.meta, self.legs, self.players = meta, legs, players          # players: {pid: dict}


def load(slate, root="data/raw/pickfinder"):
    d = os.path.join(root, slate)
    meta = jload(os.path.join(d, "capture.json"))
    board = jload(os.path.join(d, "board.json"))
    players = {}
    for f in sorted(glob.glob(os.path.join(d, "players", "*.json"))):
        p = jload(f)
        players[p.get("pid") or os.path.basename(f)[:-5]] = p
    return Capture(meta, board.get("legs", []), players)


def isnum(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def validate(cap):
    iss = []

    def add(level, code, where, msg):
        iss.append(dict(level=level, code=code, where=where, msg=msg))

    err = lambda c, w, m: add("error", c, w, m)
    warn = lambda c, w, m: add("warning", c, w, m)
    m = cap.meta
    if m.get("schema") != SCHEMA:
        err("SCHEMA", "capture.json", f"schema {m.get('schema')!r}, expected {SCHEMA}")
    try:
        cap_date = dt.date.fromisoformat(str(m.get("slate")))
    except ValueError:
        err("SCHEMA", "capture.json", "slate must be an ISO date")
        cap_date = dt.date.today()
    if not isinstance(m.get("expected_legs"), int):
        err("SCHEMA", "capture.json", "expected_legs (the board count the capture tool saw) is required: it is the page-cap guard")
    elif m["expected_legs"] != len(cap.legs):
        err("COUNT", "board.json", f"capture tool saw {m['expected_legs']} legs, board.json holds {len(cap.legs)}")

    seen = set()
    for i, g in enumerate(cap.legs):
        w = f"board.json legs[{i}] {g.get('player')} / {g.get('market')}"
        title = g.get("title")
        if title not in TITLES:
            err("TITLE", w, f"title {title!r} not in {sorted(TITLES)}")
        if g.get("market") not in CODE:
            err("MARKET", w, f"market {g.get('market')!r} not one of {sorted(CODE)}")
        if not isnum(g.get("line")):
            err("LINE", w, "line is not a number")
        for k in ("match", "player", "pid", "team"):
            if not g.get(k):
                err("SCHEMA", w, f"missing {k}")
        key = (g.get("match"), g.get("player"), g.get("market"))
        if key in seen:
            err("DUP", w, "duplicate (match, player, market)")
        seen.add(key)
        mt = g.get("match") or ""
        if title and not mt.startswith(f"{title} · "):
            err("MATCHKEY", w, f"match {mt!r} must read '<TITLE> · <A> vs <B>'")
        else:
            sides = [s.strip() for s in mt.split(" · ", 1)[-1].split(" vs ")]
            if len(sides) != 2 or g.get("team") not in sides or (g.get("opp") and g["opp"] not in sides):
                err("MATCHKEY", w, f"team {g.get('team')!r}/opp {g.get('opp')!r} are not the two sides of {mt!r}")
        h = g.get("hit") or {}
        for k, n in GRAIN.items():
            v = h.get(k)
            if v is None:
                continue
            if not isnum(v) or not 0 <= v <= 1:
                err("HITRATE", w, f"{k}={v!r} must be a fraction in [0,1]")
            elif abs(round(v * n) / n - v) > 0.006:
                warn("HITRATE_GRAIN", w, f"{k}={v} is not an exact k/{n}: a shifted column?")
        p = cap.players.get(g.get("pid"))
        if p is None:
            err("NO_PLAYER", w, f"no player file for pid {g.get('pid')}: the stats page was not captured")
        elif p.get("title") != title:
            err("TITLE", w, f"player file says {p.get('title')}, leg says {title}")
        elif p.get("team") != g.get("team"):
            warn("TEAM", w, f"player file team {p.get('team')!r} vs leg team {g.get('team')!r}")

    legpids = {g.get("pid") for g in cap.legs}
    for pid, p in cap.players.items():
        w = f"players/{pid}.json {p.get('player')}"
        if pid not in legpids:
            warn("EXTRA_PLAYER", w, "a stats page was captured for a player with no leg on the board")
        t, o = p.get("title"), p.get("overall") or {}
        if t in FPS_TITLES:
            for k in ("maps", "kills_map", "kpr"):
                if not isnum(o.get(k)):
                    err("OVERALL", w, f"overall.{k} missing")
            if t == "CS2" and not isnum(o.get("hs")):
                warn("NO_HS", w, "CS2 player without HS %")
            ms = p.get("map_stats") or []
            if not ms:
                err("MAPSTATS", w, "no per-map stats")
            elif isnum(o.get("maps")):
                n = sum(x.get("n") or 0 for x in ms)
                if n != o["maps"]:
                    err("IDENTITY_MAPS", w, f"per-map n sums to {n}, overall maps is {o['maps']}")
                elif n and isnum(o.get("kills_map")):
                    wk = sum((x.get("n") or 0) * (x.get("kills") or 0) for x in ms) / n
                    if abs(wk - o["kills_map"]) > KILL_TOL:
                        err("IDENTITY_KILLS", w, f"n-weighted kills/map is {wk:.3f}, overall kills/map is {o['kills_map']}")
            if isnum(o.get("maps")) and o["maps"] < 15:
                warn("THIN", w, f"only {o['maps']} maps")
        elif t in MOBA_TITLES:
            for k in ("maps", "win_rate", "k"):
                if not isnum(o.get(k)):
                    err("OVERALL", w, f"overall.{k} missing")
            rows = p.get("gamelog") or []
            if not rows:
                err("GAMELOG", w, "no gamelog rows")
            if len(rows) > 15:
                warn("GAMELOG", w, f"{len(rows)} rows (PickFinder shows 15 series at most)")
            for j, r in enumerate(rows):
                try:
                    age = (cap_date - dt.date.fromisoformat(r.get("date"))).days
                    if age > RECENCY_DAYS:
                        warn("STALE", f"{w} gamelog[{j}]", f"row is {age} days old")
                except (TypeError, ValueError):
                    err("GAMELOG", f"{w} gamelog[{j}]", "date must be an ISO date")
                a, b, c, ab, abc = (r.get(k) for k in ("m1k", "m2k", "m3k", "m12k", "m123k"))
                if None not in (a, b, ab) and a + b != ab:
                    err("IDENTITY_GAMELOG", f"{w} gamelog[{j}]", f"M1 {a} + M2 {b} != M1-2 {ab}")
                if None not in (ab, c, abc) and ab + c != abc:
                    err("IDENTITY_GAMELOG", f"{w} gamelog[{j}]", f"M1-2 {ab} + M3 {c} != M1-3 {abc}")
        else:
            err("TITLE", w, f"title {t!r}")
        if not p.get("pid"):
            err("SCHEMA", w, "missing pid")
    return iss


# --------------------------------------------------------------------------------------------------- conversion
def _sides(match):
    a, b = [s.strip() for s in match.split(" · ", 1)[-1].split(" vs ")]
    return a, b


def _tag_leg(g):
    return dict(title=g["title"], match=g["match"], player=g["player"], team=g["team"], market=g["market"], line=g["line"], tp=None,
                avg10=(g.get("hit") or {}).get("avg10"), l5=(g.get("hit") or {}).get("l5"), l10=(g.get("hit") or {}).get("l10"), l15=(g.get("hit") or {}).get("l15"),
                h2h=(g.get("hit") or {}).get("h2h") or "-", streak=(g.get("hit") or {}).get("streak"), key=f"{g['pid']}|{g['match']}", code=CODE[g["market"]], flags=None)


def to_site(cap, config=None):
    """-> (fps, moba): the PickFinder-derived parts of site/data/{fps,moba}.json. What PickFinder does not carry stays empty and is flagged
    (`inputs`): Thunderpick (P(win), rounds ladders, kill ladders) and HLTV (round differential), so rounds fall back to the Config defaults."""
    cfg = config or {}
    fps = dict(slate=cap.meta["slate"], built=cap.meta.get("captured_utc"), source="pickfinder", inputs=dict(pickfinder=True, thunderpick=False, hltv=False),
               players=[], mapstats={}, matches=[], legs=[], maps={"CS2": [], "VAL": []})
    moba = dict(slate=cap.meta["slate"], built=cap.meta.get("captured_utc"), source="pickfinder", inputs=dict(pickfinder=True, thunderpick=False),
                players=[], gamelog=[], matches=[], legs=[], book=[])
    for pid, p in cap.players.items():
        o, t = p.get("overall") or {}, p.get("title")
        if t in FPS_TITLES:
            fps["players"].append(dict(pid=pid, player=p["player"], title=t, team=p.get("team"), matchup=p.get("matchup"), maps=o.get("maps"), kills_map=o.get("kills_map"),
                                       kpr=o.get("kpr"), hs=o.get("hs"), hs_round=o.get("hs_round"), kd=o.get("kd"), rating=o.get("rating"), identity="OK", url=p.get("url")))
            fps["mapstats"][pid] = {x["map"]: dict(n=x.get("n"), kills=x.get("kills"), kpr=x.get("kpr"), hs=x.get("hs"), kd=x.get("kd")) for x in p.get("map_stats") or []}
        elif t in MOBA_TITLES:
            rows = p.get("gamelog") or []
            played = sum(1 for r in rows for k in ("m1k", "m2k", "m3k") if r.get(k) is not None)
            kills = sum(r[k] for r in rows for k in ("m1k", "m2k", "m3k") if r.get(k) is not None)
            moba["players"].append(dict(pid=pid, player=p["player"], team=p.get("team"), matchup=p.get("matchup"), maps=o.get("maps"), q=o.get("win_rate"), k=o.get("k"), d=o.get("d"),
                                        a=o.get("a"), kd=o.get("kd"), gl_maps=played, gl_kpm=round(kills / played, 2) if played else None, identity="OK", url=p.get("url"), title=t,
                                        role=p.get("role"), od_w=None, od_l=None, own_ratio=None, with_team=None))
            moba["gamelog"] += [dict(player=p["player"], date=r.get("date"), opp=r.get("opp"), m1=r.get("m1k"), m2=r.get("m2k"), m3=r.get("m3k"), m12=r.get("m12k"), m13=r.get("m123k")) for r in rows]
    by_match = {}
    for g in cap.legs:
        by_match.setdefault(g["match"], []).append(g)
        (fps if g["title"] in FPS_TITLES else moba)["legs"].append(_tag_leg(g))
    for mid, gs in by_match.items():
        title, g0 = gs[0]["title"], gs[0]
        a, b = _sides(mid)
        start = g0.get("start")
        if title in FPS_TITLES:
            picks = []
            for g in gs:                                                     # the Map Picks panel is per matchup: take it from the first player that has one
                mp = (cap.players.get(g["pid"]) or {}).get("map_picks") or {}
                if mp.get("maps"):
                    picks = mp["maps"]
                    break
            top = [x["map"] for x in sorted(picks, key=lambda x: -(x.get("pct") or 0))[:3]]
            top += [None] * (3 - len(top))
            rd = cfg.get("DEFAULT_ROUNDS_CS2", 21.5) if title == "CS2" else cfg.get("DEFAULT_ROUNDS_VAL", 22.5)
            rounds = [rd if mp else None for mp in top]
            fps["matches"].append(dict(id=mid, title=title, start=start, bo=None, a=a, b=b, pA=None, pA20=None, pB20=None, p3=None, pick1=None, pick2=None, pick3=None,
                                       picks_from="PF Map Picks" if picks else "none", tp_r1=None, tp_r2=None, tp_r3=None, p_ot1=None, a_margin1=None, a_rounds1=None, b_rounds1=None,
                                       tp_markets=None, m1=top[0], m2=top[1], m3=top[2], r1=rounds[0], r2=rounds[1], r3=rounds[2], p3_used=None, tag_a=a, tag_b=b,
                                       pAm1=None, pAm2=None, pAm3=None, hist_a=None, hist_b=None, default=dict(maps=top, rounds=rounds)))
        else:
            moba["matches"].append(dict(id=mid, event=g0.get("tournament") or g0.get("league"), start=start, bo=None, a=a, b=b, pA=None, tp_total=None, tp_a=None, tp_b=None, tp_dur=None,
                                        tp_markets=None, pm1=None, pm2=None, pm3=None, p2=None, p3=None, env=1, tag_a=a, tag_b=b, default=dict(pm=[None] * 3, p2=None, p3=None, env=1)))
    if cfg:
        fps["config"], moba["config"] = cfg.get("fps", {}), cfg.get("moba", {})
    return fps, moba


# --------------------------------------------------------------------------------------------------- cross-check
def crosscheck(cap, site="site"):
    """Compare the capture with the slate already on the site (the workbook import for the same day). Returns a report dict, never raises on a mismatch."""
    meta = jload(f"{site}/data/meta.json")
    if meta.get("slate") != cap.meta["slate"]:
        return dict(compared=False, reason=f"the site holds slate {meta.get('slate')}, the capture is {cap.meta['slate']}")
    fps, moba = jload(f"{site}/data/fps.json"), jload(f"{site}/data/moba.json")
    mine_f, mine_m = to_site(cap)
    diffs, missing, extra = [], [], []

    def close(a, b, tol):
        return (a is None and b is None) or (isnum(a) and isnum(b) and abs(a - b) <= tol) or a == b

    for tag, theirs, mine, fields in (("fps", fps, mine_f, (("maps", 0), ("kills_map", 0.005), ("kpr", 0.005), ("hs", 0.0006))),
                                      ("moba", moba, mine_m, (("maps", 0), ("q", 0.005), ("k", 0.05), ("d", 0.05), ("a", 0.05)))):
        tp, mp = {p["pid"]: p for p in theirs["players"]}, {p["pid"]: p for p in mine["players"]}
        for pid in sorted(set(tp) | set(mp)):
            if pid not in mp or pid not in tp:
                (missing if pid in tp else extra).append(f"{tag} player {(tp.get(pid) or mp.get(pid))['player']}")
                continue
            for f, tol in fields:
                if not close(tp[pid].get(f), mp[pid].get(f), tol):
                    diffs.append(f"{tag} player {tp[pid]['player']} {f}: workbook {tp[pid].get(f)} vs capture {mp[pid].get(f)}")
        if tag == "fps":
            for pid, ms in theirs["mapstats"].items():
                if pid not in mp:                                            # a player the capture lacks is already reported as missing
                    continue
                for mapname, x in ms.items():
                    y = (mine["mapstats"].get(pid) or {}).get(mapname)
                    if y is None or x.get("n") != y.get("n") or not close(x.get("kills"), y.get("kills"), 0.05):
                        diffs.append(f"fps mapstats {pid} {mapname}: workbook {x} vs capture {y}")
        lk = lambda g: (g["match"], g["player"], g["market"])
        tl, ml = {lk(g): g for g in theirs["legs"]}, {lk(g): g for g in mine["legs"]}
        for k in sorted(set(tl) | set(ml)):
            if k not in ml or k not in tl:
                (missing if k in tl else extra).append(f"{tag} leg {k[0]} {k[1]} {k[2]}")
                continue
            for f, tol in (("line", 0), ("avg10", 0.05), ("l5", 0.006), ("l10", 0.006), ("l15", 0.006), ("streak", 0), ("h2h", 0)):
                if not close(tl[k].get(f), ml[k].get(f), tol):
                    diffs.append(f"{tag} leg {k[1]} {k[2]} {f}: workbook {tl[k].get(f)} vs capture {ml[k].get(f)}")
    return dict(compared=True, differences=len(diffs), missing=len(missing), extra=len(extra), detail=diffs[:40], missing_detail=missing[:20], extra_detail=extra[:20])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--root", default="data/raw/pickfinder")
    ap.add_argument("--site", default="site")
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--build-out", default=None, help="write a PickFinder-only fps.json / moba.json here (never into site/data)")
    a = ap.parse_args()
    cap = load(a.slate, a.root)
    iss = validate(cap)
    errs = [i for i in iss if i["level"] == "error"]
    warns = [i for i in iss if i["level"] == "warning"]
    from collections import Counter
    print(f"capture {a.slate}: {len(cap.legs)} legs, {len(cap.players)} players | {len(errs)} errors, {len(warns)} warnings")
    for lvl, lst in (("ERROR", errs), ("warning", warns)):
        for code, n in Counter(i["code"] for i in lst).most_common():
            ex = next(i for i in lst if i["code"] == code)
            print(f"  {lvl:7} {code:16} x{n:<4} e.g. {ex['where']}: {ex['msg']}")
    if a.crosscheck:
        r = crosscheck(cap, a.site)
        if not r["compared"]:
            print("crosscheck skipped:", r["reason"])
        else:
            print(f"crosscheck vs the slate on the site: {r['differences']} value differences, {r['missing']} items on the site but not in the capture, {r['extra']} in the capture but not on the site")
            for d in r["detail"][:15]:
                print("    differs:", d)
            for d in r["missing_detail"][:5]:
                print("    missing from capture:", d)
            for d in r["extra_detail"][:5]:
                print("    not on the site:", d)
    if a.build_out and not errs:
        cfg = {}
        try:
            cfg = {"fps": jload(f"{a.site}/data/fps.json")["config"], "moba": jload(f"{a.site}/data/moba.json")["config"]}
            cfg.update(cfg["fps"])
        except (OSError, KeyError):
            pass
        fps, moba = to_site(cap, cfg)
        os.makedirs(a.build_out, exist_ok=True)
        for name, obj in (("fps.json", fps), ("moba.json", moba)):
            with open(os.path.join(a.build_out, name), "w", encoding="utf-8") as fh:
                json.dump(obj, fh, separators=(",", ":"), ensure_ascii=False)
        print("wrote", a.build_out)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
