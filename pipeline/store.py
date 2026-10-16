"""Small readers/writers. Column names are looked up case-insensitively with aliases, so a real capture with slightly different headers loads without edits."""
import csv, json, os

ALIASES = {
    "leg_id": ["leg_id", "id", "leg"], "match_id": ["match_id", "match", "series_id"], "player": ["player", "name", "handle"],
    "stat": ["stat", "market", "prop"], "line": ["line", "pp_line", "prizepicks_line"], "start": ["start", "start_time", "starts_at"],
    "title": ["title", "game", "league_game"], "team": ["team"], "opp": ["opp", "opponent"],
}


def read_rows(path, delim=None):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        head = f.readline()
        f.seek(0)
        d = delim or ("|" if head.count("|") > head.count(",") else ",")
        return [{(k or "").strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in csv.DictReader(f, delimiter=d)]


def get(row, key, default=None):
    for k in ALIASES.get(key, [key]):
        v = row.get(k)
        if v not in (None, ""):
            return v
    return default


def fnum(x, default=None):
    try:
        v = float(x)
        return v if v == v else default
    except (TypeError, ValueError):
        return default


def write_csv(path, rows, cols, delim=","):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=delim, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        f.write("\n")
