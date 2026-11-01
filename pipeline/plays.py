"""Freeze the legs a play rule selects, before the games.

    python -m pipeline.plays --slate 2026-10-18        # -> data/plays/<slate>.json

Reads the slate's frozen Log (projections as values at default settings) and applies the rules in pipeline/evaluate.py (RULES). Commit the file before the first start:
its commit time is the record that the selection was made before play. Settling never rewrites it.
"""
import argparse, datetime as dt, json, os
from .evaluate import RULES, MOBA_RULES


def select(log_rows):
    out = {}
    for rid, rule in RULES.items():
        legs = []
        for r in log_rows:
            po, poa = r.get("P(over)"), r.get("P(over) adj")
            if rule["test"](po, poa, line=r.get("Line"), market=r.get("Market"), pf=r.get("PF L10")):
                side = "UNDER" if rule.get("side") == "under" else "OVER" if rule.get("side") == "over" else "OVER" if po >= 0.5 else "UNDER"
                legs.append(dict(match=r["Match"], player=r["Player"], market=r["Market"], line=r["Line"], side=side, p_over=po, p_over_adj=poa))
        legs.sort(key=lambda l: (l["match"], -abs(l["p_over"] - 0.5)))
        out[rid] = dict(name=rule["name"], n=len(legs), legs=legs)
    return out


def late_matches(slate, frozen_utc, site="site"):
    """Board matches whose start is at or before the freeze: their legs were frozen after play began, so they are not a clean pre-play record."""
    from .results import board_start_utc
    fz = dt.datetime.fromisoformat(frozen_utc).astimezone(dt.timezone.utc).replace(tzinfo=None)
    out = []
    for f in ("fps", "moba"):
        try:
            with open(f"{site}/data/{f}.json", encoding="utf-8") as fh:
                ms = json.load(fh)["matches"]
        except OSError:
            continue
        for m in ms:
            st = board_start_utc(slate, m["start"])
            if st <= fz:
                out.append(dict(match=m["id"], start_utc=st.isoformat(timespec="minutes"), minutes_before_freeze=round((fz - st).total_seconds() / 60)))
    return out


def mark_late(slate, site="site", out="data/plays"):
    """Record the late matches in an existing plays file (only this key is added; the frozen legs are untouched)."""
    path = f"{out}/{slate}.json"
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    res["late_matches"] = late_matches(slate, res["frozen_utc"], site)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return path, res["late_matches"]


def select_moba(moba_rows):
    out = {}
    for rid, rule in MOBA_RULES.items():
        legs = []
        for r in moba_rows:
            po = r.get("P(over)")
            if po is not None and rule["test"](po):
                legs.append(dict(match=r["Match"], player=r["Player"], market=r["Market"], line=r["Line"], side="OVER" if po >= 0.5 else "UNDER", p_over=po))
        legs.sort(key=lambda l: (l["match"], -abs(l["p_over"] - 0.5)))
        out[rid] = dict(name=rule["name"], n=len(legs), legs=legs)
    return out


def add_rules(slate, site="site", out="data/plays"):
    """Add the FPS rules a plays file lacks (a slate frozen before a rule existed, still before play). The rules already in the file are left exactly as they are; the added ones carry their own freeze time."""
    path = f"{out}/{slate}.json"
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    missing = [rid for rid in RULES if rid not in res["rules"]]
    if not missing:
        return path, None
    with open(f"{site}/data/log/{slate}.json", encoding="utf-8") as f:
        log = json.load(f)["fps"]
    sel = select(log)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for rid in missing:
        res["rules"][rid] = sel[rid]
    res["rules_added_utc"] = {**res.get("rules_added_utc", {}), **{rid: now for rid in missing}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return path, {rid: sel[rid]["n"] for rid in missing}


def add_moba(slate, site="site", out="data/plays"):
    """Add the MOBA rules to a plays file that has none (a slate frozen before MOBA rules existed). Everything already in the file is left exactly as it is; the MOBA part carries its own freeze time."""
    path = f"{out}/{slate}.json"
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    if "moba_rules" in res:
        return path, None
    with open(f"{site}/data/log/{slate}.json", encoding="utf-8") as f:
        log = json.load(f)
    res["moba_rules"] = select_moba(log.get("moba", []))
    res["moba_frozen_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return path, {k: v["n"] for k, v in res["moba_rules"].items()}


def freeze(slate, site="site", out="data/plays", force=False):
    """Write data/plays/<slate>.json from the slate's frozen Log. An existing file is never rewritten (the commit time is the record that the selection preceded play) unless force."""
    path = f"{out}/{slate}.json"
    if os.path.exists(path) and not force:
        return path, None
    with open(f"{site}/data/log/{slate}.json", encoding="utf-8") as f:
        full = json.load(f)
    log = full["fps"]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    res = dict(slate=slate, frozen_utc=now, rules=select(log), moba_rules=select_moba(full.get("moba", [])), moba_frozen_utc=now, comparison="every leg on the board (the base model's side)",
               late_matches=late_matches(slate, now, site))
    for m in res["late_matches"]:
        print(f"WARNING {m['match']} started {m['minutes_before_freeze']} min before the freeze ({m['start_utc']} UTC): its plays are not a clean pre-play record")
    os.makedirs(out, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return path, {k: v["n"] for k, v in {**res["rules"], **res["moba_rules"]}.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--site", default="site")
    ap.add_argument("--out", default="data/plays")
    ap.add_argument("--add-moba", action="store_true", help="add the MOBA rules to an existing plays file, leaving what it holds untouched")
    ap.add_argument("--mark-late", action="store_true", help="record in an existing plays file which matches had started before its freeze")
    ap.add_argument("--add-rules", action="store_true", help="add the FPS rules the file lacks, leaving the ones it holds untouched")
    ap.add_argument("--force", action="store_true", help="rewrite an existing file (only to add a rule that did not exist yet; never after the games)")
    a = ap.parse_args()
    if a.mark_late:
        path, late = mark_late(a.slate, a.site, a.out)
        print(path, late or "no match started before the freeze")
        return
    if a.add_rules:
        path, counts = add_rules(a.slate, a.site, a.out)
        print(path, counts if counts is not None else "no rule missing: left as it is")
        return
    if a.add_moba:
        path, counts = add_moba(a.slate, a.site, a.out)
        print(path, counts if counts is not None else "MOBA rules already in the file: left as they are")
        return
    path, counts = freeze(a.slate, a.site, a.out, a.force)
    print(path, counts if counts is not None else "already frozen: left as it is")


if __name__ == "__main__":
    main()
