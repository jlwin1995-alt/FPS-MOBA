"""settled_YYYY-MM-DD.psv -> scorecard.json + results/<date>.json.

A settled file is the frozen pre-lock board joined with the next-day result: one row per leg with the line, three projection variants,
the naive projection, the actual, the result (O/U/P) and whether the leg was registered before lock. Only registered legs are scored.
"""
import glob, os, re
from . import config as C
from .store import read_rows, fnum, write_json

LABEL2STAT = {v["label"]: k for k, v in C.STATS.items()}


def load(log_dir):
    days = {}
    for f in sorted(glob.glob(os.path.join(log_dir, "settled_*.psv"))):
        m = re.search(r"settled_(\d{4}-\d{2}-\d{2})", f)
        rows = []
        for r in read_rows(f, "|"):
            stat = LABEL2STAT.get(r.get("market", ""), r.get("market", ""))
            line, a, nv, act = fnum(r.get("line")), fnum(r.get("proj_a")), fnum(r.get("naive")), fnum(r.get("actual"))
            if line is None or a is None or act is None or stat not in C.STATS:
                continue
            side = "O" if a > line else "U" if a < line else None
            res = r.get("result") or ("P" if act == line else "O" if act > line else "U")
            z = (a - line) / C.SD_FLOOR[stat]
            rows.append(dict(title=r.get("title"), match=r.get("match"), player=r.get("player"), stat=stat, label=C.STATS[stat]["label"], line=line,
                             a=a, b=fnum(r.get("proj_b")), c=fnum(r.get("proj_c")), naive=nv, actual=act, result=res, side=side,
                             hit=None if (side is None or res == "P") else int(side == res), z=round(z, 2),
                             reg=int(fnum(r.get("registered"), 1) or 0), src=r.get("source", "")))
        days[m.group(1)] = rows
    return days


def tier(z):
    z = abs(z)
    return "strong" if z >= C.STRONG else "lean" if z >= C.LEAN else "none"


def summarise(rows):
    reg = [r for r in rows if r["reg"]]
    graded = [r for r in reg if r["hit"] is not None]
    n = len(reg)
    mae = lambda k: sum(abs(r[k] - r["actual"]) for r in reg if r[k] is not None) / max(1, sum(r[k] is not None for r in reg)) if reg else None
    return dict(n=n, graded=len(graded), hits=sum(r["hit"] for r in graded), pushes=sum(r["result"] == "P" for r in reg),
                mae=mae("a"), mae_naive=mae("naive"), mae_season=mae("c"), bias=sum(r["a"] - r["actual"] for r in reg) / n if n else None)


def build(log_dir, out_dir):
    days = load(log_dir)
    per_day = [dict(date=d, **summarise(rows)) for d, rows in sorted(days.items())]
    allrows = [r for rows in days.values() for r in rows]
    by_title = {t: summarise([r for r in allrows if r["title"] == t]) for t in sorted({r["title"] for r in allrows})}
    by_stat = {s: summarise([r for r in allrows if r["stat"] == s]) for s in C.STATS if any(r["stat"] == s for r in allrows)}
    tiers = {k: summarise([r for r in allrows if tier(r["z"]) == k]) for k in ("none", "lean", "strong")}
    write_json(os.path.join(out_dir, "scorecard.json"), dict(total=summarise(allrows), days=per_day, by_title=by_title, by_stat=by_stat, tiers=tiers,
                                                             lean=C.LEAN, strong=C.STRONG))
    for d, rows in days.items():
        write_json(os.path.join(out_dir, "results", f"{d}.json"), dict(date=d, rows=rows, summary=summarise(rows)))
    write_json(os.path.join(out_dir, "results", "index.json"), [dict(date=d, **summarise(rows)) for d, rows in sorted(days.items(), reverse=True)])
    return len(allrows), len(days)
