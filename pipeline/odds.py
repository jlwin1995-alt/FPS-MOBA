"""Market cross-check from OddsPapi: what the bookmakers think of the matches on the board, next to what the model assumes.

    python -m pipeline.odds fetch --slate 2026-10-18      # needs ODDSPAPI_KEY (a GitHub Actions secret); writes data/raw/odds/<slate>/<fixture>.json
    python -m pipeline.odds build --slate 2026-10-18      # offline: parses the raw files -> data/odds/<slate>.json and site/data/odds.json

What comes out for each linked match (all de-vigged, median across bookmakers, Pinnacle shown separately when it quotes):
  series win probability · each map's winner · P(map 3 played) from the total-maps line · per-map total rounds (line, P(over)) and overtime chance
  · and, whenever a book prices them, team/total kills and headshots and PLAYER kills/headshots lines.
OddsPapi lists player kill/headshot markets in its catalogue, but on the fixtures checked on 2026-10-17 (about a day out) no bookmaker had priced them, so those entries stay empty
until a book does. Nothing here is a bet signal: it is a second opinion on the inputs the model uses (series strength, how many maps, how long the maps run).
"""
import argparse, datetime as dt, glob, json, os, re, statistics, sys, time, urllib.error, urllib.parse, urllib.request
from .names import same_team
from .results import board_start_utc, link_matches, load_board

BASE = "https://api.oddspapi.io/v4"
SPORTS = {"CS2": 17, "VAL": 61, "LOL": 59, "DOTA": 16}
KEEP = re.compile(r"^(moneyline|overtime|totals|spreads-rounds|(player)?(team)?totals-)")        # market types worth keeping from each book
SKIP_PERIOD = re.compile(r"^p\dr\d+$")                                                         # per-round winner markets: not needed
SHARP = "pinnacle"


def call(path, key, **params):
    q = urllib.parse.urlencode({**params, "apiKey": key})
    for attempt in range(4):
        time.sleep(1.5)
        req = urllib.request.Request(f"{BASE}/{path}?{q}", headers={"User-Agent": "fps-moba-odds", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or "null")
        except urllib.error.HTTPError as e:
            text = e.read()[:300].decode("utf-8", "replace")
            if e.code == 429 and attempt < 3:                       # the API says how long to wait; honour it, do not hammer
                m = re.search(r'"retryMs":\s*(\d+)', text)
                time.sleep(min(int(m.group(1)) / 1000 if m else 2, 6) + 0.5)
                continue
            if e.code == 404:
                return None
            raise SystemExit(f"{path}: HTTP {e.code} {text}")
    return None


# ----------------------------------------------------------------------------------------------- fetch
def fetch(slate, site="site", imports="data/imports", out="data/raw/odds"):
    key = os.environ.get("ODDSPAPI_KEY")
    if not key:
        sys.exit("ODDSPAPI_KEY is not set")
    fps, moba, where = load_board(slate, site, imports)
    boards = {"CS2": [m for m in fps["matches"] if m["title"] == "CS2"], "VAL": [m for m in fps["matches"] if m["title"] == "VAL"],
              "LOL": [m for m in moba["matches"] if m["id"].startswith("LOL")], "DOTA": [m for m in moba["matches"] if m["id"].startswith("DOTA")]}
    d0 = dt.date.fromisoformat(slate)
    os.makedirs(f"{out}/{slate}", exist_ok=True)
    got = []
    for title, board in boards.items():
        if not board:
            continue
        sid = SPORTS[title]
        fx = call("fixtures", key, sportId=sid, **{"from": d0.isoformat(), "to": (d0 + dt.timedelta(days=2)).isoformat()}) or []
        rows = fx if isinstance(fx, list) else fx.get("data", [])
        cands = [dict(id=r["fixtureId"], t1=[r.get("participant1Name")], t2=[r.get("participant2Name")], start=dt.datetime.fromisoformat(r["startTime"].replace("Z", "+00:00")).replace(tzinfo=None), ref=r) for r in rows if r.get("participant1Name")]
        links = link_matches(slate, board, cands, None)
        catalogue = {str(m["marketId"]): m for m in (call("markets", key, sportId=sid) or [])}
        for b in board:
            L = links.get(b["id"])
            if not L:
                exp = board_start_utc(slate, b["start"])
                near = sorted(cands, key=lambda c: abs((c["start"] - exp).total_seconds()))[:4]
                print(f"{b['id']}: no fixture found (board {b['a']} v {b['b']} at {exp:%m-%d %H:%M} UTC; nearest listed: " + "; ".join(f"{c['t1'][0]} v {c['t2'][0]} {c['start']:%m-%d %H:%M}" for c in near) + f"; {len(cands)} fixtures listed)")
                continue
            f = L["cand"]["ref"]
            if not f.get("hasOdds"):
                print(f"{b['id']}: fixture found ({f['participant1Name']} v {f['participant2Name']}) but no odds yet")
                continue
            od = call("odds", key, fixtureId=f["fixtureId"])
            if not od:
                continue
            raw = trim(od, catalogue)
            raw.update(board_match=b["id"], title=title, linked=dict(how=L["how"], start_gap_h=L["gap_h"], rivals=L["rivals"]), captured_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       participants=[f.get("participant1Name"), f.get("participant2Name")], start=f.get("startTime"))
            with open(f"{out}/{slate}/{f['fixtureId']}.json", "w", encoding="utf-8") as fh:
                json.dump(raw, fh, separators=(",", ":"))
            got.append(b["id"])
            print(f"{b['id']}: {len(raw['books'])} books, {len(raw['catalogue'])} market kinds")
    print(f"{len(got)} matches saved under {out}/{slate}/")


def trim(od, catalogue):
    """The odds payload without what the cross-check does not read: only kept market types, only price/main-line/active per outcome, and the catalogue rows those markets need."""
    books, used = {}, {}
    for book, bd in (od.get("bookmakerOdds") or {}).items():
        if not bd.get("bookmakerIsActive", True) or bd.get("suspended"):
            continue
        ms = {}
        for mid, md in (bd.get("markets") or {}).items():
            m = catalogue.get(mid)
            if not m or not md.get("marketActive", True) or not KEEP.match(m["marketType"]) or SKIP_PERIOD.match(m["period"] or ""):
                continue
            outs = {}
            for oid, o in (md.get("outcomes") or {}).items():
                for pk, p in (o.get("players") or {}).items():
                    if p.get("active", True) and p.get("price"):
                        outs.setdefault(oid, []).append([p.get("playerName"), p["price"], 1 if p.get("mainLine") else 0])
            if outs:
                ms[mid] = outs
                used[mid] = dict(name=m["marketName"], type=m["marketType"], period=m["period"], handicap=m.get("handicap"), playerProp=bool(m.get("playerProp")),
                                 outcomes={str(o["outcomeId"]): o["outcomeName"] for o in m.get("outcomes", [])})
        if ms:
            books[book] = ms
    return dict(fixtureId=od.get("fixtureId"), books=books, catalogue=used)


# ----------------------------------------------------------------------------------------------- parse
def devig(prices):
    """Fair probabilities from decimal prices of the mutually exclusive outcomes of one market."""
    inv = [1 / p for p in prices]
    s = sum(inv)
    return [x / s for x in inv]


def agg(vals):
    vals = [v for v in vals if v is not None]
    return None if not vals else dict(p=round(statistics.median(vals), 4), n=len(vals), lo=round(min(vals), 4), hi=round(max(vals), 4))


def parse(raw):
    """-> dict of market views for one fixture (see module doc)."""
    cat = raw["catalogue"]
    two_way = {}                 # (marketId, player) -> {book: {outcomeName: price}}
    for book, ms in raw["books"].items():
        for mid, outs in ms.items():
            names = cat[mid]["outcomes"]
            by_player = {}
            for oid, rows in outs.items():
                for player, price, main in rows:
                    by_player.setdefault(player, {})[names.get(oid, oid)] = (price, main)
            for player, d in by_player.items():
                two_way.setdefault((mid, player), {})[book] = d
    out = dict(series={}, maps={}, total_maps=[], totals={}, overtime={}, player={})
    for (mid, player), per_book in two_way.items():
        c = cat[mid]
        t, per = c["type"], c["period"]
        fair = {}                # book -> {outcome: p}
        for book, d in per_book.items():
            if len(d) < 2:
                continue
            ks = sorted(d)
            ps = devig([d[k][0] for k in ks])
            fair[book] = dict(zip(ks, ps))
        if not fair:
            continue
        def med(k):
            return agg([f[k] for f in fair.values() if k in f])
        sharp = (lambda k: round(fair[SHARP][k], 4) if SHARP in fair and k in fair[SHARP] else None)
        if t == "moneyline":
            view = dict(p1=med("1"), p2=med("2"), sharp_p1=sharp("1"))
            if per == "result":
                out["series"] = view
            elif re.fullmatch(r"p\d", per or ""):
                out["maps"][per[1]] = view
        elif t == "overtime":
            out["overtime"][per[1:] if per else "?"] = dict(yes=med("Yes") or med("yes"))
        elif t == "totals" and per == "result" and "map" in c["name"].lower():
            out["total_maps"].append(dict(line=c["handicap"], over=med("Over"), sharp_over=sharp("Over")))
        elif re.match(r"^(player)?(team)?totals-", t):
            key = f"{c['name']}|{per}"
            ent = dict(line=c["handicap"], over=med("Over"), sharp_over=sharp("Over"), books=len(fair), player=player or None)
            (out["player"] if c["playerProp"] else out["totals"]).setdefault(key, []).append(ent)
    out["total_maps"].sort(key=lambda x: x["line"])
    for grp in (out["totals"], out["player"]):
        for k, v in grp.items():
            v.sort(key=lambda x: (x["player"] or "", x["line"] if x["line"] is not None else 0))
    return out


def main_line(entries):
    """The consensus line among several: the one quoted by the most books (ties -> closest to even money)."""
    ok = [e for e in entries if e.get("over")]
    return max(ok, key=lambda e: (e["books"], -abs(e["over"]["p"] - 0.5)), default=None)


def flip(v):
    """Swap the two sides of a moneyline view (the fixture lists the teams in the other order from the board)."""
    if not v:
        return v
    return dict(p1=v.get("p2"), p2=v.get("p1"), sharp_p1=None if v.get("sharp_p1") is None else round(1 - v["sharp_p1"], 4))


def view(parsed, board_match, participants=None):
    """The parsed fixture next to what the model assumes for the same match -> one record for the site. p1 is always the board's team A."""
    m = board_match
    swapped = bool(participants) and same_team(m["a"], participants[1]) and not same_team(m["a"], participants[0])
    if swapped:
        parsed = dict(parsed, series=flip(parsed["series"]), maps={k: flip(v) for k, v in parsed["maps"].items()})
    s = parsed["series"]
    out = dict(swapped=swapped, series=s, maps=parsed["maps"], overtime=parsed["overtime"], total_maps=parsed["total_maps"],
               model=dict(pA=m.get("pA"), p3=m.get("p3_used"), bo=m.get("bo"), maps=[m.get("m1"), m.get("m2"), m.get("m3")], rounds=[m.get("r1"), m.get("r2"), m.get("r3")],
                          map_win=[m.get("pAm1"), m.get("pAm2"), m.get("pAm3")]))
    if parsed["total_maps"]:
        bo = m.get("bo") or 3
        third = next((e for e in parsed["total_maps"] if e["line"] == 2.5), None) if bo == 3 else None
        out["p_map3"] = dict(market=(third or {}).get("over"), model=m.get("p3_used"))
    rounds = {}
    for key, ents in parsed["totals"].items():
        name, per = key.split("|")
        if name.startswith("Total Rounds") and re.fullmatch(r"p\d", per):
            e = main_line(ents)
            if e:
                rounds[per[1]] = dict(line=e["line"], p_over=e["over"]["p"], books=e["books"])
    out["rounds"] = rounds
    # team and match kills per map (a few books post these for CS2 a day out); team 1/2 follow the fixture's order, so map them onto the board's A/B
    tk, mk = {}, {}
    for key, ents in parsed["totals"].items():
        name, per = key.split("|")
        mm = re.match(r"Kills - Over Under Team ([12])\b", name)
        e = main_line(ents)
        if not e or not re.fullmatch(r"p\d", per or ""):
            continue
        rec = dict(line=e["line"], p_over=e["over"]["p"], books=e["books"], ladder=[[x["line"], x["over"]["p"]] for x in ents if x.get("over")])
        if mm:
            side = "A" if (mm.group(1) == "1") != swapped else "B"
            tk.setdefault(per[1], {})[side] = rec
        elif name.startswith("Kills - Over Under") and "Team" not in name:
            mk[per[1]] = rec
    out["team_kills"], out["match_kills"] = tk, mk
    out["other_totals"] = {k: main_line(v) for k, v in parsed["totals"].items() if not k.startswith("Total Rounds") and main_line(v)}
    out["player"] = {k: v for k, v in parsed["player"].items()}
    return out


def build(slate, site="site", imports="data/imports", raw="data/raw/odds", out="data/odds"):
    fps, moba, _ = load_board(slate, site, imports)
    boards = {m["id"]: m for m in fps["matches"] + moba["matches"]}
    res = dict(slate=slate, generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), matches={})
    for p in sorted(glob.glob(f"{raw}/{slate}/*.json")):
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        b = boards.get(r["board_match"])
        if not b:
            continue
        v = view(parse(r), b, r["participants"])
        v.update(fixture=r["fixtureId"], participants=r["participants"], start=r["start"], captured_utc=r["captured_utc"], books=len(r["books"]), linked=r["linked"])
        res["matches"][r["board_match"]] = v
    os.makedirs(out, exist_ok=True)
    for path in (f"{out}/{slate}.json", f"{site}/data/odds.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(res, f, separators=(",", ":"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "build"])
    ap.add_argument("--slate", required=True)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.slate)
    else:
        r = build(a.slate)
        for mid, v in r["matches"].items():
            s = v["series"]
            print(mid, "series p1", (s.get("p1") or {}).get("p"), "model pA", v["model"]["pA"], "| rounds", {k: (x["line"], x["p_over"]) for k, x in v["rounds"].items()}, "| player props", len(v["player"]))


if __name__ == "__main__":
    main()
