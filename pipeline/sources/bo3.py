"""CS2 results from bo3.gg's public API (the per-map tables the site itself draws): kills, headshots and deaths per player per map.

Games and match players_stats are separate routes in the API, which gives the second-route check the dictionary asks for
(HLTV is behind Cloudflare and is never routed around): the match endpoint's per-player totals must equal the sum over maps.
"""
import urllib.parse
from .http import get_json

BASE = "https://api.bo3.gg/api/v1/"
HDR = {"Accept": "application/json", "Origin": "https://bo3.gg", "Referer": "https://bo3.gg/"}


def api(path, **params):
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    return get_json(BASE + path + q, headers=HDR)


def finished_matches(since_iso, until_iso, max_pages=12):
    """Finished CS2 matches with start_date in [since, until), newest first, paged until the list passes `since`."""
    out, off = [], 0
    for _ in range(max_pages):
        d = api("matches", **{"page[offset]": off, "page[limit]": 100, "filter[matches.status][in]": "finished",
                              "filter[matches.discipline_id][eq]": 1, "sort": "-start_date", "with": "teams"})
        rs = d["results"]
        out += [m for m in rs if since_iso <= m["start_date"] < until_iso]
        if not rs or rs[-1]["start_date"] < since_iso:
            break
        off += 100
    return {m["id"]: m for m in out}.values()


def match_maps(m):
    """-> {'maps': [{n, map, rounds, winner, state, players:[{name, alias, team, kills, hs, deaths}]}], 'checks': [...]}"""
    games = sorted(api("games", **{"filter[games.match_id][eq]": m["id"]})["results"], key=lambda g: g["number"])
    maps, checks, per_player_games = [], [], {}
    for g in games:
        rows = api(f"games/{g['id']}/players_stats")
        players = []
        for r in rows:
            sp = r.get("steam_profile") or {}
            pl = sp.get("player") or {}
            players.append(dict(name=pl.get("nickname") or sp.get("nickname"), alias=sp.get("nickname"), team=(r.get("team_clan") or {}).get("clan_name") or r.get("clan_name"),
                                kills=r["kills"], hs=r["headshots"], deaths=r["death"], steam=sp.get("steam_id_64")))
        maps.append(dict(n=g["number"], map=g["map_name"], rounds=g["rounds_count"], winner=g["winner_clan_name"], score=[g["winner_clan_score"], g["loser_clan_score"]], state=g["state"], players=players))
        for p in players:
            per_player_games.setdefault(p["steam"], []).append(p["kills"])
        # identity checks, per map
        teams = {}
        for p in players:
            teams.setdefault(p["team"], []).append(p)
        k = {t: sum(x["kills"] for x in v) for t, v in teams.items()}
        d = {t: sum(x["deaths"] for x in v) for t, v in teams.items()}
        ok_n = len(players) == 10 and all(len(v) == 5 for v in teams.values()) and len(teams) == 2
        ts = list(teams)
        # a team's kills cannot exceed the other side's deaths; deaths also include bomb, fall and team-kill deaths, so allow a small gap
        cross = ok_n and 0 <= d[ts[1]] - k[ts[0]] <= 10 and 0 <= d[ts[0]] - k[ts[1]] <= 10
        checks.append(dict(map=g["number"], players_ok=ok_n, kills_vs_deaths_ok=bool(cross), hs_le_kills=all(p["hs"] <= p["kills"] for p in players),
                           rounds_ok=None not in (g["rounds_count"], g["winner_clan_score"], g["loser_clan_score"]) and g["rounds_count"] == g["winner_clan_score"] + g["loser_clan_score"]))
    # second route: the match-level table must equal the sum over maps
    tot = api(f"matches/{m['slug']}/players_stats")
    route2 = {}
    for r in tot:
        sid = (r.get("steam_profile") or {}).get("steam_id_64")
        route2[sid] = r["kills"]
    mism = [sid for sid, s in per_player_games.items() if route2.get(sid) is not None and route2[sid] != sum(s)]
    return dict(maps=maps, checks=checks, route2=dict(players=len(route2), mismatched=len(mism)))
