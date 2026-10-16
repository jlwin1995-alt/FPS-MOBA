"""Baseline projection for one player-stat from his own series history.

PLACEHOLDER MODEL. The real fps_log / moba_log model was not available when this site was assembled (see README), so this is a plain,
transparent stand-in with the same inputs and outputs: a recency-weighted mean of the last 15 series, shrunk toward the title's average
for that stat, with the player's own spread. Swap `project()` for the real model and nothing else in the site has to change.

history rows (logs.csv): title, player, team, opp, date, series, m1_k, m2_k, m3_k, m1_hs, m2_hs, m3_hs (blank = map not played / not tracked).
"""
import statistics
from datetime import date, timedelta
from . import config as C
from .store import fnum


def series_value(row, stat):
    """Stat total for one series, or None when any needed map is missing (a Bo3 that ended 2-0 has no 'Maps 1-3' result)."""
    spec = C.STATS[stat]
    tot = 0.0
    for m in spec["maps"]:
        v = fnum(row.get(f"m{m}_{spec['col']}"))
        if v is None:
            return None
        tot += v
    return tot


def player_history(logs, title, player, stat, asof, days=C.RECENCY_DAYS, limit=15):
    """Newest-first [(date, value)] for series strictly before `asof`, inside the recency window."""
    lo = (date.fromisoformat(asof) - timedelta(days=days)).isoformat()
    rows = [r for r in logs if r["title"] == title and r["player"] == player and lo <= r["date"] < asof]
    rows.sort(key=lambda r: r["date"], reverse=True)
    out = []
    for r in rows:
        v = series_value(r, stat)
        if v is not None:
            out.append((r["date"], v))
        if len(out) >= limit:
            break
    return out


def title_means(logs, asof):
    """Average per title and stat over every player's usable series before `asof`."""
    acc = {}
    for r in logs:
        if r["date"] >= asof:
            continue
        for s in C.STATS:
            v = series_value(r, s)
            if v is not None:
                acc.setdefault((r["title"], s), []).append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def project(vals, tmean, stat):
    """vals: newest-first list of series totals. Returns dict(proj, sd, n, naive, variants) or None when the sample is too thin."""
    n = len(vals)
    if n < C.MIN_GAMES:
        return None
    g1, g2, g3 = vals[:5], vals[5:10], vals[10:15]
    parts = [(C.W_L5, _mean(g1)), (C.W_L10, _mean(g2)), (C.W_REST, _mean(g3))]
    parts = [(w, m) for w, m in parts if m is not None]
    raw = sum(w * m for w, m in parts) / sum(w for w, _ in parts)       # weights renormalised over the groups that exist
    shrunk = (n * raw + C.SHRINK_N * tmean) / (n + C.SHRINK_N) if tmean is not None else raw
    sd = statistics.stdev(vals) if n >= 3 else 0.0
    return dict(proj=shrunk, sd=sd, n=n, naive=_mean(vals[:10]), variants=dict(a=shrunk, b=raw, c=_mean(vals)))
