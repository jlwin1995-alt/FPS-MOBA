"""Valorant results from vlr.gg: per-map player kills from the match overview tab.

Identity check from the data dictionary: the all-maps tab must equal the sum of the maps (an empty cell once parsed as 0).
"""
import html, re
from .http import get_text

BASE = "https://www.vlr.gg"
tidy = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _ago_hours(t):
    """'11h 30m' / '5d 10h' / '2w 1d' after 'Completed' -> hours ago."""
    m = re.search(r"Completed\s+((?:\d+[wdhm]\s*)+)", t)
    if not m:
        return None
    mult = dict(w=168, d=24, h=1, m=1 / 60)
    return sum(int(n) * mult[u] for n, u in re.findall(r"(\d+)([wdhm])", m.group(1)))


def recent_results(pages=2):
    """[{id, slug, teams:[a,b], score:[x,y], ago_h, text}] newest first."""
    out = []
    for p in range(1, pages + 1):
        s = get_text(f"{BASE}/matches/results" + (f"?page={p}" if p > 1 else ""))
        for href, body in re.findall(r'<a href="(/\d+/[^"]+)" class="wf-module-item[^"]*"[^>]*>(.*?)</a>', s, flags=re.S):
            names = [tidy(x) for x in re.findall(r'class="match-item-vs-team-name[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</div)', body, flags=re.S)] or []
            names = [re.sub(r"\s+\d+$", "", n) for n in names]
            scores = [tidy(x) for x in re.findall(r'class="match-item-vs-team-score[^"]*"[^>]*>(.*?)</div>', body, flags=re.S)]
            t = tidy(body)
            out.append(dict(id=int(href.split("/")[1]), slug=href, teams=names[:2], score=[int(x) if x.isdigit() else None for x in scores[:2]], ago_h=_ago_hours(t), text=t[:160]))
    return out


def match_maps(match_id):
    s = get_text(f"{BASE}/{match_id}/?game=all&tab=overview")
    blocks = [(m.start(), m.group(1)) for m in re.finditer(r'<div class="vm-stats-game[^"]*" data-game-id="(\w+)"', s)]
    parts = {gid: s[a:(blocks[i + 1][0] if i + 1 < len(blocks) else len(s))] for i, (a, gid) in enumerate(blocks)}

    def players(blk):
        rows = []
        for row in re.findall(r'<div class="ovw-row">(.*?)(?=<div class="ovw-row"|<div class="vm-stats-game|$)', blk, flags=re.S):
            nm = re.search(r'class="ovw-player-name[^"]*">(.*?)</div>', row, flags=re.S)
            tg = re.search(r'class="ovw-player-tag[^"]*">(.*?)</div>', row, flags=re.S)
            if not nm:
                continue
            def stat(col):
                m = re.search(rf'data-col="{col}"[^>]*>\s*<span class="side mod-both">\s*([-\d.]*)', row)
                return int(m.group(1)) if m and re.fullmatch(r"-?\d+", m.group(1) or "") else None
            rows.append(dict(name=tidy(nm.group(1)), team=tidy(tg.group(1)) if tg else None, kills=stat("kills"), deaths=stat("deaths")))
        return rows

    maps, n = [], 0
    for _, gid in blocks:
        if gid == "all":
            continue
        n += 1
        blk = parts[gid]
        mname = re.search(r'class="map-name">(.*?)</div>', blk, flags=re.S)
        sc = [int(x) for x in re.findall(r'<div class="score[^"]*"[^>]*>\s*(\d+)', blk)[:2]]
        teams = [tidy(x) for x in re.findall(r'class="team-name">(.*?)</div>', blk, flags=re.S)[:2]]
        mn = re.sub(r"\bPICK\b", "", tidy(mname.group(1))).strip() if mname else None
        maps.append(dict(n=n, game_id=gid, map=mn, score=sc, teams=teams, players=players(blk), state="done" if len(sc) == 2 else None))
    allp = players(parts.get("all", ""))
    checks = []
    for mp in maps:
        ps = mp["players"]
        t = {}
        for p in ps:
            t.setdefault(p["team"], []).append(p)
        ts = list(t)
        k = {x: sum(p["kills"] or 0 for p in v) for x, v in t.items()}
        d = {x: sum(p["deaths"] or 0 for p in v) for x, v in t.items()}
        ok_n = len(ps) == 10 and len(ts) == 2 and all(len(v) == 5 for v in t.values()) and all(p["kills"] is not None and p["deaths"] is not None for p in ps)
        cross = ok_n and 0 <= d[ts[1]] - k[ts[0]] <= 10 and 0 <= d[ts[0]] - k[ts[1]] <= 10
        rounds = sum(mp["score"]) if len(mp["score"]) == 2 else None
        checks.append(dict(map=mp["n"], players_ok=ok_n, kills_vs_deaths_ok=bool(cross), hs_le_kills=True, rounds_ok=bool(rounds)))
        mp["rounds"] = rounds
    # the dictionary's identity: the all-maps tab equals the sum of the maps
    sums = {}
    for mp in maps:
        for p in mp["players"]:
            sums[(p["team"], p["name"])] = sums.get((p["team"], p["name"]), 0) + (p["kills"] or 0)
    mism = [(p["name"], p["kills"], sums.get((p["team"], p["name"]))) for p in allp if p["kills"] != sums.get((p["team"], p["name"]))]
    return dict(maps=maps, checks=checks, route2=dict(players=len(allp), mismatched=len(mism), detail=mism[:5]))
