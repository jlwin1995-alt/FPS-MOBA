"""Join a frozen board with next-day results -> data/log/settled_<date>.psv.

    python -m pipeline.settle --date 2026-10-15 --results data/raw/results_2026-10-15.csv

results csv columns: title, match, player, market (label like "Maps 1-2 Kills" or key like M12K), actual, source (optional).
Join key is (title, match, player, market): the match id carries the team pair, so a player in several Bo1s a day can't cross-wire.
Legs with no actual stay unsettled and are listed, never scored as zero.
"""
import argparse, os
from . import config as C
from .store import read_rows, fnum, write_csv

COLS = ["title", "match", "player", "market", "line", "proj_a", "proj_b", "proj_c", "naive", "actual", "result", "registered", "source"]
KEY2LABEL = {k: v["label"] for k, v in C.STATS.items()}


def settle(board, results):
    got = {(r.get("title"), r.get("match"), r.get("player"), KEY2LABEL.get(r.get("market"), r.get("market"))): r for r in results}
    out, missing = [], []
    for b in board:
        r = got.get((b["title"], b["match"], b["player"], b["market"]))
        actual = fnum(r.get("actual")) if r else None
        line = fnum(b.get("line"))
        if actual is None or line is None:
            missing.append(b)
            continue
        out.append(dict(b, actual=actual, result="P" if actual == line else "O" if actual > line else "U", source=r.get("source", "")))
    return out, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--log", default="data/log")
    a = ap.parse_args()
    board = read_rows(os.path.join(a.log, f"board_{a.date}.psv"), "|")
    if not board:
        raise SystemExit(f"no frozen board for {a.date}: it is written by the first build of that slate")
    out, missing = settle(board, read_rows(a.results))
    write_csv(os.path.join(a.log, f"settled_{a.date}.psv"), out, COLS, "|")
    print(f"settled {len(out)} of {len(board)} legs for {a.date}; {len(missing)} unsettled")
    for m in missing[:20]:
        print("  unsettled:", m["title"], m["match"], m["player"], m["market"])


if __name__ == "__main__":
    main()
