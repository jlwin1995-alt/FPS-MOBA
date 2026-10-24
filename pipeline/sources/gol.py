"""LoL results from gol.gg (Games of Legends): per-game player kills.

Identity check from the data dictionary: the team's kill header must equal the sum of its players' kills.
(Leaguepedia, the dictionary's second source, rate-limits and refuses this environment, so it is not used here.)
"""
import html, re, urllib.parse
from .http import get_text

BASE = "https://gol.gg"
tidy = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def series_list(tournament):
    """[{id, teams:[left, right], winner:'left'|'right'|None, score:'3 - 0', played, round, date}] from the tournament match list."""
    s = get_text(f"{BASE}/tournament/tournament-matchlist/{urllib.parse.quote(tournament)}/")
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S):
        m = re.search(r"stats/(\d+)/page-(summary|preview|game)/", r)       # a best-of-1 (Worlds main event) links straight to its game page
        tds = re.findall(r"<td([^>]*)>(.*?)</td>", r, flags=re.S)
        if not m or len(tds) < 7:
            continue
        left, right = tidy(tds[1][1]), tidy(tds[3][1])
        win = "left" if "text_victory" in tds[1][0] else "right" if "text_victory" in tds[3][0] else None
        out.append(dict(id=int(m.group(1)), teams=[left, right], winner=win, score=tidy(tds[2][1]), played=m.group(2) in ("summary", "game"), single=m.group(2) == "game", round=tidy(tds[4][1]), date=tidy(tds[6][1])))
    return out


def series_game_ids(series_id):
    s = get_text(f"{BASE}/game/stats/{series_id}/page-summary/")
    return sorted({int(g) for g in re.findall(r"stats/(\d+)/page-game/", s)})


def game(gid):
    s = get_text(f"{BASE}/game/stats/{gid}/page-game/")
    teams = []
    for side, cls in (("blue", "blue-line-header"), ("red", "red-line-header")):
        m = re.search(rf'<div class="col-12 {cls}">(.*?)</div>', s, flags=re.S)
        t = tidy(m.group(1)) if m else ""
        nm, _, res = t.rpartition(" - ")
        kills = None
        mk = re.search(rf'class="score-box {side}_line"><img src="[^"]*ic_kills[^"]*"[^>]*/>\s*(\d+)', s)
        if mk:
            kills = int(mk.group(1))
        teams.append(dict(side=side, name=nm, result=res, kills=kills, players=[]))
    for i, t in enumerate(re.split(r"(?=<table class='playersInfosLine)", s)[1:3]):
        for mm in re.finditer(r"class='link-blanc'[^>]*title='([^']+?) stats'>(.*?)</a>", t):
            tail = t[mm.end(): mm.end() + 6000]
            kda = re.search(r"(?<![\d/])(\d+)/(\d+)/(\d+)(?![\d/])", tail)
            if kda:
                teams[i]["players"].append(dict(name=tidy(mm.group(2)), kills=int(kda.group(1)), deaths=int(kda.group(2)), assists=int(kda.group(3))))
    dur = re.search(r"Game Time<br/>\s*<h1>([\d:]+)</h1>", s)
    return dict(id=gid, teams=teams, duration=dur.group(1) if dur else None)


def series_maps(series_id, single=False):
    """-> {'maps': [...as the other sources...], 'checks': [...], 'route2': {...}}. `single`: the id is already a game id (a best-of-1 listed by its game page)."""
    maps, checks, mism = [], [], 0
    for n, gid in enumerate([series_id] if single else series_game_ids(series_id), 1):
        g = game(gid)
        players = [dict(name=p["name"], alias=None, team=t["name"], kills=p["kills"], hs=None, deaths=p["deaths"]) for t in g["teams"] for p in t["players"]]
        k = {t["name"]: sum(p["kills"] for p in t["players"]) for t in g["teams"]}
        d = {t["name"]: sum(p["deaths"] for p in t["players"]) for t in g["teams"]}
        ts = [t["name"] for t in g["teams"]]
        ok_n = len(players) == 10 and all(len(t["players"]) == 5 for t in g["teams"])
        header_ok = all(t["kills"] is not None and t["kills"] == k[t["name"]] for t in g["teams"])
        cross = ok_n and 0 <= d[ts[1]] - k[ts[0]] <= 6 and 0 <= d[ts[0]] - k[ts[1]] <= 6
        winner = next((t["name"] for t in g["teams"] if t["result"].upper().startswith("WIN")), None)
        maps.append(dict(n=n, map=f"game {n}", rounds=None, winner=winner, score=[k.get(ts[0]), k.get(ts[1])], state="done", players=players, game_id=gid, duration=g["duration"]))
        checks.append(dict(map=n, players_ok=ok_n, kills_vs_deaths_ok=bool(cross), hs_le_kills=True, rounds_ok=header_ok))   # rounds_ok = team kill header equals sum of players
        mism += 0 if header_ok else 1
    return dict(maps=maps, checks=checks, route2=dict(players=sum(len(m["players"]) for m in maps), mismatched=mism, note="team kill header vs sum of players, per game"))
