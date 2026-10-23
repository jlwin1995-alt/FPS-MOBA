"""Dota 2 results from OpenDota's public API: per-game player kills for the pro series on the board.

Routes: /proMatches lists recent pro games (with a series id and the series type), /matches/<id> has the player table.
Identity checks, per game: 10 players 5 v 5; the team's kill score is within 2 of the sum of its players' kills (the API's team score counts every kill,
a player table can miss one); the players' deaths cover the other side's kills. Second route, per player: the kills in the player's own recent-match
list must equal the kills in the game table; a difference fails the game's player check (a player with no public history is simply not compared).
A series is "finished" only when one team has the wins its series type needs, so a half-played series is never read as a void map.
"""
from .http import get_json

BASE = "https://api.opendota.com/api"
BO = {0: 1, 1: 3, 2: 5}


def pro_series(since_ts, max_pages=5):
    """Recent pro games grouped by series: [{series_id, bo, teams:[radiant name, dire name of the first game], start (unix of the first game), games:[proMatches rows, oldest first]}]."""
    rows, less = [], None
    for _ in range(max_pages):
        page = get_json(f"{BASE}/proMatches" + (f"?less_than_match_id={less}" if less else ""))
        if not page:
            break
        rows += [r for r in page if r["start_time"] >= since_ts]
        if page[-1]["start_time"] < since_ts:
            break
        less = page[-1]["match_id"]
    by = {}
    for r in rows:
        by.setdefault(r["series_id"] or -r["match_id"], []).append(r)
    out = []
    for sid, gs in by.items():
        gs.sort(key=lambda r: r["start_time"])
        out.append(dict(series_id=sid, bo=BO.get(gs[0].get("series_type"), 1), teams=[gs[0]["radiant_name"], gs[0]["dire_name"]], start=gs[0]["start_time"], games=gs))
    return out


def wins(series):
    w = {}
    for g in series["games"]:
        name = g["radiant_name"] if g["radiant_win"] else g["dire_name"]
        w[name] = w.get(name, 0) + 1
    return w


def finished(series):
    return bool(wins(series)) and max(wins(series).values()) >= series["bo"] // 2 + 1


def _recent_kills(account_id, cache):
    if account_id not in cache:
        try:
            cache[account_id] = {m["match_id"]: m["kills"] for m in get_json(f"{BASE}/players/{account_id}/recentMatches", delay=1.1)}
        except Exception:
            cache[account_id] = None
    return cache[account_id]


def series_maps(series, route2=True):
    """-> {'maps': [...as the other sources...], 'checks': [...], 'route2': {...}}"""
    maps, checks, compared, mism, cache = [], [], 0, [], {}
    for n, row in enumerate(series["games"], 1):
        m = get_json(f"{BASE}/matches/{row['match_id']}")
        names = {True: (m.get("radiant_team") or {}).get("name") or m.get("radiant_name"), False: (m.get("dire_team") or {}).get("name") or m.get("dire_name")}
        players = []
        for p in m["players"]:
            rad = bool(p.get("isRadiant", p["player_slot"] < 128))
            players.append(dict(name=p.get("name") or p.get("personaname"), alias=p.get("personaname"), team=names[rad], kills=p["kills"], hs=None, deaths=p["deaths"], account_id=p.get("account_id"), radiant=rad))
        k = {r: sum(p["kills"] for p in players if p["radiant"] == r) for r in (True, False)}
        d = {r: sum(p["deaths"] for p in players if p["radiant"] == r) for r in (True, False)}
        ok_n = len(players) == 10 and sum(p["radiant"] for p in players) == 5
        score = {True: m.get("radiant_score"), False: m.get("dire_score")}
        header_ok = all(score[r] is not None and abs(score[r] - k[r]) <= 2 for r in (True, False))
        cross = ok_n and all(d[r] >= k[not r] - 2 for r in (True, False))
        bad = []
        if route2 and ok_n:
            for p in players:
                if not p["account_id"]:
                    continue
                rk = _recent_kills(p["account_id"], cache)
                if rk is None or row["match_id"] not in rk:
                    continue
                compared += 1
                if rk[row["match_id"]] != p["kills"]:
                    bad.append(p["name"])
        mism += [f"game {n}: {x}" for x in bad]
        maps.append(dict(n=n, map=f"game {n}", rounds=None, winner=names[bool(m["radiant_win"])], score=[score[True], score[False]], state="done", players=[{k_: v for k_, v in p.items() if k_ not in ("account_id", "radiant")} for p in players],
                         match_id=row["match_id"], duration=m.get("duration")))
        checks.append(dict(map=n, players_ok=ok_n and not bad, kills_vs_deaths_ok=bool(cross), hs_le_kills=True, rounds_ok=header_ok))      # rounds_ok = team kill score within 2 of the players' sum
    return dict(maps=maps, checks=checks, route2=dict(players=compared, mismatched=len(mism), detail=mism, note="each player's kills in his own recent-match list vs the game table; team score vs sum of players"))
