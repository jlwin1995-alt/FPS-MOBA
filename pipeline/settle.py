"""Apply data/results/<slate>.json to the slate's frozen Log.

    python -m pipeline.settle --slate 2026-10-16

Only the settlement columns are written (Actual, Result, Source, Note). The frozen projection columns are never touched, an Actual already
on a row is never overwritten (a disagreement is reported instead), and legs the pull could not settle keep their reason in Note.
"""
import argparse, json, os

SRC = {"CS2": "bo3.gg", "VAL": "vlr.gg", "LOL": "gol.gg", "DOTA": "opendota"}


def apply(log, legs, title_of):
    """log: list of Log rows (dicts). legs: results legs. Returns (set, kept, conflicts, noted)."""
    idx = {(r.get("Match"), r.get("Player"), r.get("Market")): r for r in log}
    n = dict(set=0, same=0, conflict=[], noted=0, missing=0)
    for l in legs:
        r = idx.get((l["match"], l["player"], l["market"]))
        if r is None:
            n["missing"] += 1
            continue
        src = SRC.get(title_of(l["match"]), "")
        if l["status"] == "ok":
            line = r.get("Line")
            res = "PUSH" if l["actual"] == line else ("OVER" if l["actual"] > line else "UNDER")
            cur = r.get("Actual")
            if isinstance(cur, (int, float)) and not isinstance(cur, bool):
                if cur == l["actual"]:
                    n["same"] += 1
                else:
                    n["conflict"].append((l["match"], l["player"], l["market"], cur, l["actual"]))
                continue
            r["Actual"], r["Result"], r["Source"], r["Note"] = l["actual"], res, src, None
            n["set"] += 1
        else:
            if r.get("Actual") is None:
                r["Note"] = l["status"] + (f" ({l['detail']})" if l.get("detail") else "")
                r["Source"] = src or None
                n["noted"] += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--site", default="site")
    ap.add_argument("--results", default="data/results")
    a = ap.parse_args()
    res = json.load(open(f"{a.results}/{a.slate}.json"))
    path = f"{a.site}/data/log/{a.slate}.json"
    log = json.load(open(path))
    title_of = lambda m: m.split(" ")[0]
    fl = [l for l in res["legs"] if l["match"].split(" ")[0] in ("CS2", "VAL")]
    ml = [l for l in res["legs"] if l["match"].split(" ")[0] in ("LOL", "DOTA")]
    a1, a2 = apply(log["fps"], fl, title_of), apply(log["moba"], ml, title_of)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, separators=(",", ":"), ensure_ascii=False)
        f.write("\n")
    for tag, x in (("FPS", a1), ("MOBA", a2)):
        print(f"{tag}: set {x['set']}, already settled {x['same']}, noted {x['noted']}, no log row {x['missing']}, conflicts {len(x['conflict'])}")
        for c in x["conflict"]:
            print("   CONFLICT", c)


if __name__ == "__main__":
    main()
