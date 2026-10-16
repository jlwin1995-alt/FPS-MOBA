"""Synthetic league so the site can be developed with no capture access (the site is bannered SAMPLE whenever it is built from this).

    python -m pipeline.sample_data [--date 2026-10-16] [--out data/sample]

Writes legs.csv (today's board), logs.csv (series history), matches.csv (today's matches) and, for the last few slates, a frozen
board_<date>.psv and settled_<date>.psv built with the same model code the site uses, so Scorecard/Results have something to show.
The names, teams and numbers are invented; nothing here is real data.
"""
import argparse, math, os, random
from datetime import date, timedelta
from . import config as C
from . import model as M
from . import prob
from .store import write_csv

SYL = ["ko", "ra", "vi", "ze", "mo", "lu", "ta", "sk", "ni", "fa", "dr", "yo", "bu", "qe", "ha", "ji", "xo", "pe"]
TEAMS = {"CS2": 6, "Valorant": 4, "LoL": 4, "Dota": 4}
BASE = {"CS2": (17.0, 2.2, 0.46), "Valorant": (15.0, 2.0, 0.24), "LoL": (3.2, 1.0, 0.0), "Dota": (6.5, 1.8, 0.0)}   # kills/map mean, between-player sd, HS share
POS = {"CS2": ["Rifler", "AWP", "Entry", "Lurker", "IGL"], "Valorant": ["Duelist", "Initiator", "Controller", "Sentinel", "Flex"],
       "LoL": ["Top", "Jungle", "Mid", "ADC", "Support"], "Dota": ["Pos1", "Pos2", "Pos3", "Pos4", "Pos5"]}
LEAGUES = {"CS2": "Sample Open", "Valorant": "Sample Masters", "LoL": "Sample League", "Dota": "Sample Cup"}
LOG_COLS = ["title", "player", "team", "opp", "date", "series", "m1_k", "m2_k", "m3_k", "m1_hs", "m2_hs", "m3_hs", "m12_k", "m123_k"]
SETTLED_COLS = ["title", "match", "player", "market", "line", "proj_a", "proj_b", "proj_c", "naive", "actual", "result", "registered", "source"]


def handle(rng, used):
    while True:
        h = "".join(rng.choice(SYL) for _ in range(rng.choice([2, 3]))).capitalize()
        if h not in used:
            used.add(h)
            return h


def make_league(rng):
    used, teams, players = set(), {}, []
    for t, n in TEAMS.items():
        mu0, sd0, hs = BASE[t]
        for i in range(n):
            name = f"{t[:3].upper()} {handle(rng, used)}"
            roster = []
            for j in range(5):
                p = dict(title=t, team=name, player=handle(rng, used), pos=POS[t][j], mu=max(mu0 + rng.gauss(0, sd0), mu0 * 0.5), hs=hs * rng.uniform(0.8, 1.2), form=0.0)
                roster.append(p)
                players.append(p)
            teams.setdefault(t, []).append((name, roster, sum(p["mu"] for p in roster) / 5))
    return teams, players


def one_map(rng, p):
    p["form"] = 0.8 * p["form"] + rng.gauss(0, 0.04 * p["mu"])        # slow drift: hot and cold spells
    mu = max(p["mu"] + p["form"], 0.5)
    k = max(0, round(rng.gauss(mu, 1.15 * math.sqrt(mu))))
    hs = round(k * min(max(p["hs"] + rng.gauss(0, 0.07), 0), 1)) if p["hs"] else None
    return k, hs


def play(rng, teams, day, play_series):
    """Pair up teams per title for one day; return [(title, a, b, maps)], and append each player's series row to `play_series`."""
    out = []
    for t, tl in teams.items():
        if rng.random() < 0.15:
            continue
        order = tl[:]
        rng.shuffle(order)
        for i in range(0, len(order) - 1, 2):
            out.append((t, order[i], order[i + 1], 2 if rng.random() < 0.55 else 3))
    return out


def line_from(rng, mu, maps):
    x = mu * maps + rng.gauss(0, 0.04 * mu * maps + 0.3)
    return math.floor(x) + 0.5


def simulate(today, seed=7, days=70, past_slates=6):
    rng = random.Random(seed)
    teams, players = make_league(rng)
    logs, slates = [], {}
    d0 = date.fromisoformat(today)
    for off in range(days, 0, -1):
        day = (d0 - timedelta(days=off)).isoformat()
        slates[day] = []
        for t, A, B, nmaps in play(rng, teams, day, logs):
            sid = f"{day}-{A[0][:7]}-{B[0][:7]}".replace(" ", "")
            for me, opp in ((A, B), (B, A)):
                for p in me[1]:
                    r = dict(title=t, player=p["player"], team=me[0], opp=opp[0], date=day, series=sid)
                    for m in (1, 2, 3):
                        if m <= nmaps:
                            r[f"m{m}_k"], hs = one_map(rng, p)
                            r[f"m{m}_hs"] = hs
                    r["m12_k"] = r["m1_k"] + r["m2_k"]                       # the combined columns the player pages carry; build checks M1 + M2 = M1-2
                    if nmaps == 3:
                        r["m123_k"] = r["m12_k"] + r["m3_k"]
                    logs.append(r)
            slates[day].append((t, A, B, sid))
    matches = []
    for t, A, B, nmaps in play(rng, teams, today, None):
        matches.append((t, A, B))
    return rng, teams, players, logs, slates, matches


def board_for(rng, title, A, B, mid, day, logs, tmeans, today_board=False):
    legs = []
    for me, opp in ((A, B), (B, A)):
        for p in me[1]:
            stats = ["M12K", "M1K", "M123K"] + (["M12HS", "M1HS"] if BASE[title][2] else [])
            for s in stats:
                spec = C.STATS[s]
                maps = len(spec["maps"])
                mu = p["mu"] * (p["hs"] if spec["hs"] else 1) * maps
                if rng.random() < 0.25:
                    continue
                line = line_from(rng, p["mu"] * (p["hs"] if spec["hs"] else 1), maps)
                legs.append(dict(title=title, match_id=mid, player=p["player"], team=me[0], opp=opp[0], pos=p["pos"], stat=s, line=line, alt=0,
                                 league=LEAGUES[title], tournament=LEAGUES[title], mu=mu))
    return legs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", default="data/sample")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    generate(a.date, a.out, a.seed)


def generate(day, out, seed=7):
    a = argparse.Namespace(date=day, out=out, seed=seed)
    rng, teams, players, logs, slates, today_matches = simulate(a.date, a.seed)
    write_csv(f"{a.out}/logs.csv", logs, LOG_COLS)
    ldict = {(r["title"], r["player"], r["date"]): r for r in logs}

    # ---- past slates: frozen board + settlement, using only history before each day ----
    days = sorted(d for d, s in slates.items() if s)[-6:]
    for day in days:
        before = [r for r in logs if r["date"] < day]
        tm = M.title_means(before, day)
        board, settled = [], []
        for t, A, B, sid in slates[day]:
            for g in board_for(rng, t, A, B, sid, day, before, tm):
                hist = M.player_history(before, t, g["player"], g["stat"], day)
                pr = M.project([v for _, v in hist], tm.get((t, g["stat"])), g["stat"])
                row = ldict.get((t, g["player"], day))
                actual = M.series_value(row, g["stat"]) if row else None
                if not pr or actual is None:
                    continue
                res = "P" if actual == g["line"] else ("O" if actual > g["line"] else "U")
                settled.append(dict(title=t, match=sid, player=g["player"], market=C.STATS[g["stat"]]["label"], line=g["line"],
                                    proj_a=round(pr["variants"]["a"], 2), proj_b=round(pr["variants"]["b"], 2), proj_c=round(pr["variants"]["c"], 2),
                                    naive=round(pr["naive"], 2), actual=actual, result=res, registered=1, source="sample"))
        write_csv(f"{a.out}/log/settled_{day}.psv", settled, SETTLED_COLS, "|")

    # ---- today's board ----
    tm = M.title_means(logs, a.date)
    legs, matches = [], []
    for i, (t, A, B) in enumerate(today_matches):
        mid = f"{a.date}-{A[0][:7]}-{B[0][:7]}".replace(" ", "")
        start = f"{a.date}T{12 + (i * 37) % 11:02d}:{(i * 15) % 60:02d}:00+00:00"
        sa, sb = A[2], B[2]
        pa = 1 / (1 + math.exp(-(sa - sb) / (1.2 if t in ("CS2", "Valorant") else 0.8)))
        vig = 1.05
        mla, mlb = round(1 / (pa * vig), 2), round(1 / ((1 - pa) * vig), 2)
        matches.append(dict(match_id=mid, title=t, start=start, team_a=A[0], team_b=B[0], bo=3, ml_a=mla, ml_b=mlb,
                            margin_a=round(rng.gauss(1.5, 1.5) * (pa - 0.5) * 4, 2) if t == "CS2" else None,
                            margin_b=round(rng.gauss(1.5, 1.5) * (0.5 - pa) * 4, 2) if t == "CS2" else None,
                            lineup_a="|".join(p["player"] for p in A[1]), lineup_b="|".join(p["player"] for p in B[1])))
        for g in board_for(rng, t, A, B, mid, a.date, logs, tm, True):
            hist = M.player_history(logs, t, g["player"], g["stat"], a.date)
            vals = [v for _, v in hist]
            n10 = vals[:10]
            def hr(k):
                xs = vals[:k]
                return round(100 * sum(v > g["line"] for v in xs) / len(xs)) if len(xs) >= min(k, 4) else None
            g.update(leg_id=f"{mid}:{g['player']}:{g['stat']}", start=start,
                     line_ud=g["line"] + rng.choice([0, 0, 0.5, -0.5]) if rng.random() < 0.8 else None,
                     line_sl=g["line"] + rng.choice([0, 0, 0.5, -0.5]) if rng.random() < 0.6 else None,
                     line_betr=g["line"] + rng.choice([0, 0, 0.5, -0.5]) if rng.random() < 0.5 else None,
                     line_pplay=g["line"] + rng.choice([0, 0, 0.5, -0.5]) if rng.random() < 0.4 else None,
                     line_dk=g["line"] + rng.choice([0, 0.5, -0.5]) if rng.random() < 0.1 else None,
                     hr_l5=hr(5), hr_l10=hr(10), hr_l15=hr(15), hr_season=hr(15),
                     h2h_hits=rng.randint(0, 2), h2h_games=rng.randint(2, 4), avg10=round(sum(n10) / len(n10), 2) if n10 else None,
                     ml_team=mla if g["team"] == A[0] else mlb, ml_opp=mlb if g["team"] == A[0] else mla,
                     fav_over=rng.randint(10, 400), fav_under=rng.randint(10, 400))
            legs.append(g)
    leg_cols = ["leg_id", "title", "match_id", "start", "league", "tournament", "player", "team", "opp", "pos", "stat", "line", "alt",
                "line_ud", "line_sl", "line_betr", "line_pplay", "line_dk", "hr_l5", "hr_l10", "hr_l15", "hr_season", "h2h_hits", "h2h_games",
                "avg10", "ml_team", "ml_opp", "fav_over", "fav_under"]
    write_csv(f"{a.out}/legs.csv", legs, leg_cols)
    write_csv(f"{a.out}/matches.csv", matches, ["match_id", "title", "start", "team_a", "team_b", "bo", "ml_a", "ml_b", "margin_a", "margin_b", "lineup_a", "lineup_b"])
    open(f"{a.out}/SAMPLE", "w").write("synthetic data\n")
    print(f"sample league: {len(players)} players, {len(logs)} series rows, {len(matches)} matches today, {len(legs)} legs, {len(days)} settled slates -> {a.out}")


if __name__ == "__main__":
    main()
