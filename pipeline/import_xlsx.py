"""Import the two slate workbooks (FPS: CS2 + Valorant, MOBA: LoL + Dota 2) into the JSON the site reads.

    python -m pipeline.import_xlsx --fps FPS_Player_Model.xlsx --moba MOBA_Player_Model.xlsx

The workbooks are rebuilt every slate from fresh captures; this reads their INPUTS (players, per-map stats, matches with the shaded
columns, board legs with PickFinder hit rates, Thunderpick books, HLTV tables, the frozen Log) and the numbers the workbook itself
computed (kept in site/test/expected.json so the browser's port of the model can be checked against them). The model itself is
NOT run here: it lives in site/fps.js and site/moba.js so that editing maps, rounds or win probabilities recalculates live.

Writes: site/data/{fps,moba,meta}.json, site/data/log/<slate>.json (+ index.json), site/test/expected.json,
        data/imports/<slate>/ (copies of the workbooks: the raw record).

Re-imports are safe:
  * the frozen Log is never rewritten: a later import of the same slate only adds Actual / Result to rows that have none (settlement);
  * a workbook for an OLDER slate than the one on the site updates only that slate's Log, never the live inputs.
"""
import argparse, json, os, shutil
import openpyxl
from openpyxl.utils import get_column_letter as L, column_index_from_string as CI


def sheet(wb, name):
    return wb[name] if name in wb.sheetnames else None


def clean(v):
    if isinstance(v, float) and v == int(v) and abs(v) < 1e12:
        return int(v) if abs(v) >= 1 else v
    return v


def table(ws, header_row=1, first=None, last_col=None, key_by_letter=False):
    """Rows below the header as dicts keyed by header text (or by column letter). Blank rows are skipped."""
    hdr = {c.column: (L(c.column) if key_by_letter else str(c.value).strip()) for c in ws[header_row] if c.value is not None}
    out = []
    for r in range((first or header_row + 1), ws.max_row + 1):
        row = {h: clean(ws.cell(r, c).value) for c, h in hdr.items()}
        if any(v not in (None, "") for v in row.values()):
            out.append(row)
    return out


def rows_raw(ws):
    return [[clean(c.value) for c in r] for r in ws.iter_rows()]


def pick(d, m):
    """Rename columns: m = {new: old}."""
    return {n: d.get(o) for n, o in m.items()}


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def checks(ws):
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            continue
        out.append(dict(name=str(r[0]), value=r[1] if not (isinstance(r[1], str) and r[1].startswith("=")) else None, live=isinstance(r[1], str) and str(r[1]).startswith("=")))
    return out


def log_rows(ws):
    return [r for r in table(ws)]


def kv(ws, r0, r1):
    return {str(ws.cell(r, 1).value).strip(): clean(ws.cell(r, 2).value) for r in range(r0, r1 + 1) if ws.cell(r, 1).value}


def import_fps(path):
    wv = openpyxl.load_workbook(path, data_only=True)
    cfg = kv(wv["Config"], 4, 15)
    cs = wv["Config"]
    maps = {"CS2": [cs.cell(r, 5).value for r in range(4, 40) if cs.cell(r, 5).value], "VAL": [cs.cell(r, 6).value for r in range(4, 40) if cs.cell(r, 6).value]}
    slate = str(kv(cs, 18, 19)["SLATE_DATE"])
    built = kv(cs, 18, 19).get("BUILT_UTC")

    players = [pick(p, dict(pid="PID", player="Player", title="Title", team="Team", matchup="PF matchup", maps="Maps", kills_map="Kills/Map", kpr="KPR", hs="HS %",
                            hs_round="HS/Round", kd="K/D", rating="Rating", identity="Identity", url="PickFinder page")) for p in table(wv["Players"])]
    mapstats = {}
    for r in table(wv["Map_Stats"]):
        mapstats.setdefault(r["PID"], {})[r["Map"]] = dict(n=r["Maps (n)"], kills=r["Kills/map"], kpr=r["KPR (PF)"], hs=r["HS %"], kd=r["K/D"])

    mcols = dict(id="A", title="B", start="C", bo="D", a="E", b="F", pA="G", pA20="H", pB20="I", p3="J", pick1="K", pick2="L", pick3="M", picks_from="N",
                 tp_r1="O", tp_r2="P", tp_r3="Q", p_ot1="R", a_margin1="S", a_rounds1="T", b_rounds1="U", tp_markets="V", m1="W", m2="X", m3="Y",
                 r1="Z", r2="AA", r3="AB", p3_used="AC", tag_a="AD", tag_b="AE", pAm1="AF", pAm2="AG", pAm3="AH", hist_a="AI", hist_b="AJ")
    wsm = wv["Matches"]
    matches = []
    for r in range(5, wsm.max_row + 1):
        if not wsm.cell(r, 1).value:
            continue
        matches.append({k: clean(wsm.cell(r, CI(c)).value) for k, c in mcols.items()})
    for m in matches:                                                  # keep the workbook's defaults so the site can "reset" an edit
        m["default"] = dict(maps=[m["m1"], m["m2"], m["m3"]], rounds=[m["r1"], m["r2"], m["r3"]])

    wsp = wv["Projections"]
    legs, expected = [], []
    for r in range(2, wsp.max_row + 1):
        if not wsp.cell(r, 1).value:
            continue
        g = lambda c: clean(wsp.cell(r, CI(c)).value)
        legs.append(dict(title=g("A"), match=g("B"), player=g("C"), team=g("D"), market=g("E"), line=g("F"), tp=g("M"), avg10=g("N"), l5=g("O"), l10=g("P"), l15=g("Q"),
                         h2h=g("R"), streak=g("S"), key=g("W"), code=g("X"), flags=g("V")))
        expected.append(dict(key=g("W"), code=g("X"), proj=g("G"), sigma=g("H"), p_over=g("I"), p_under=g("J"), p_push=g("K"), side=g("L"),
                             proj_adj=g("Z"), sigma_adj=g("AA"), p_over_adj=g("AB"), p_under_adj=g("AC"), side_adj=g("AD"), mult=g("AE")))
    hl = {r["Key (match|side|map|stat)"]: r["Value"] for r in table(wv["HLTV_Long"])}
    teams = [dict(key=r["Key"], match=r["Match"], side=r["Side"], team=r["HLTV team"], lw=r["Rounds lost in wins"], wl=r["Rounds won in losses"], p20=r["P(2-0)"], p21=r["P(2-1)"],
                  p02=r["P(0-2)"], p12=r["P(1-2)"], ot=r["OT %"], win=r["Map win rate"], share=r["Hist round share"]) for r in table(wv["HLTV_Teams"])]
    veto = [dict(match=r["Match"], map=r["Map"], team=r["Team"], first_pick=r["First pick %"], first_ban=r["First ban %"], win=r["Win %"], played=r["Played (3 months)"]) for r in table(wv["HLTV_Veto"])]
    book = [dict(match=r["Match"], name=r["TP player name"], m1=r["Map 1 median"], m1_rungs=r["Map 1 rungs"], m2=r["Map 2 median"], m2_rungs=r["Map 2 rungs"], m12=r["Maps 1-2 median"], pid=r["Matched PID"]) for r in table(wv["Book_Props"])]
    ladders = [dict(match=r["Match"], map=r["Map"], total=r["Total"], over=r["Over odds"], under=r["Under odds"], p_over=r["P(over) devigged"], cross=r["50% crossing"]) for r in table(wv["Round_Ladders"])]
    intel = rows_raw(wv["Match_Intel"])
    log = log_rows(wv["Log"])
    data = dict(slate=slate, built=built, config=cfg, maps=maps, players=players, mapstats=mapstats, matches=matches, legs=legs, hltv_long=hl, hltv_teams=teams, veto=veto,
                book=book, ladders=ladders, intel=intel, checks=checks(wv["Data_Checks"]))
    return slate, data, expected, log


def import_moba(path):
    wv = openpyxl.load_workbook(path, data_only=True)
    cfg = kv(wv["Config"], 4, 9)
    slate = str(kv(wv["Config"], 11, 12)["SLATE_DATE"])
    built = kv(wv["Config"], 11, 12).get("BUILT_UTC")
    players = [pick(p, dict(pid="PID", player="Player", team="Team", matchup="PF matchup", maps="Maps", q="Map win rate", k="K", d="D", a="A", kd="K/D", gl_maps="Gamelog maps",
                            gl_kpm="Gamelog kills/map", identity="Identity", url="PickFinder page", title="Title", role="Role", od_w="OpenDota W", od_l="OpenDota L",
                            own_ratio="Own W/L ratio", with_team="With current teammates")) for p in table(wv["Players"])]
    mcols = dict(id="A", event="B", start="C", bo="D", a="E", b="F", pA="G", tp_total="H", tp_a="I", tp_b="J", tp_dur="K", tp_markets="L", pm1="M", pm2="N", pm3="O",
                 p2="P", p3="Q", env="R", tag_a="S", tag_b="T")
    wsm = wv["Matches"]
    matches = []
    for r in range(5, wsm.max_row + 1):
        if wsm.cell(r, 1).value:
            m = {k: clean(wsm.cell(r, CI(c)).value) for k, c in mcols.items()}
            m["default"] = dict(pm=[m["pm1"], m["pm2"], m["pm3"]], p2=m["p2"], p3=m["p3"], env=m["env"])
            matches.append(m)
    wsp = wv["Projections"]
    legs, expected = [], []
    for r in range(2, wsp.max_row + 1):
        if not wsp.cell(r, 1).value:
            continue
        g = lambda c: clean(wsp.cell(r, CI(c)).value)
        legs.append(dict(match=g("A"), player=g("B"), team=g("C"), market=g("D"), line=g("E"), tp=g("N"), avg10=g("Q"), l5=g("R"), l10=g("S"), l15=g("T"), h2h=g("U"),
                         streak=g("V"), exact=g("W"), key=g("Y"), code=g("Z"), flags=g("X")))
        expected.append(dict(key=g("Y"), code=g("Z"), proj=g("F"), sigma=g("G"), p_over=g("H"), p_under=g("I"), p_push=g("J"), side=g("K"), naive=g("L"), p_over_naive=g("M")))
    gl = [dict(player=r["Player"], date=r["Date"], opp=r["Opponent"], m1=r["M 1K"], m2=r["M 2K"], m3=r["M 3K"], m12=r["M 1-2K"], m13=r["M 1-3K"]) for r in table(wv["Gamelog"])]
    book = [dict(match=r["Match"], name=r["TP player name"], m1=r.get("Map 1 median"), m2=r.get("Map 2 median"), m3=r.get("Map 3 median"), rungs=r.get("Rungs (M1)"), pid=r.get("Matched PID")) for r in table(wv["Book_Props"])]
    data = dict(slate=slate, built=built, config=cfg, players=players, matches=matches, legs=legs, gamelog=gl, book=book, checks=checks(wv["Data_Checks"]))
    return slate, data, expected, table(wv["Log"])


LOG_KEY = lambda r: (r.get("Match"), r.get("Player"), r.get("Market"))


def merge_log(old, new):
    """Frozen fields stay as first imported. Actual / Result are taken from the new rows when they hold a value. Rows only in one side are kept."""
    idx = {LOG_KEY(r): r for r in old}
    out = list(old)
    for r in new:
        k = LOG_KEY(r)
        if k not in idx:
            out.append(r)
            continue
        o = idx[k]
        if isinstance(r.get("Actual"), (int, float)) and not isinstance(r.get("Actual"), bool):
            o["Actual"] = r["Actual"]
            if r.get("Result") not in (None, ""):
                o["Result"] = r["Result"]
    return out


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def require_stored_results(tag, expected):
    """A workbook saved without calculating holds formulas but no results; importing it would silently drop everything calculated in the sheet."""
    have = sum(1 for e in expected if isinstance(e.get("proj"), (int, float)) and not isinstance(e.get("proj"), bool))
    if expected and have < 0.5 * len(expected):
        raise SystemExit(f"the {tag} workbook has no stored results ({have} of {len(expected)} projections): it was saved without being calculated. "
                         f"Run `python -m pipeline.recalc <file>` (or open and re-save it in Sheets or Excel) and upload it again. Nothing imported.")


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", required=True)
    ap.add_argument("--moba", required=True)
    ap.add_argument("--site", default="site")
    ap.add_argument("--imports", default="data/imports")
    ap.add_argument("--slate", default=None, help="the slate the upload folder is named for; the workbooks must say the same")
    a = ap.parse_args()
    s1, fps, ex1, log1 = import_fps(a.fps)
    s2, moba, ex2, log2 = import_moba(a.moba)
    require_stored_results("FPS", ex1)
    require_stored_results("MOBA", ex2)
    if s1 != s2:
        raise SystemExit(f"the two workbooks are for different slates (FPS {s1}, MOBA {s2}): nothing imported")
    if a.slate and a.slate != s1:
        raise SystemExit(f"the folder is {a.slate} but the workbooks say {s1} (is this yesterday's workbook, or the Config SLATE_DATE not updated?): nothing imported")
    meta_path = f"{a.site}/data/meta.json"
    cur = (read_json(meta_path) or {}).get("slate")
    live = cur is None or s1 >= cur                                     # an older slate only feeds the Log
    if live:
        dump(f"{a.site}/data/fps.json", fps)
        dump(f"{a.site}/data/moba.json", moba)
        dump(f"{a.site}/test/expected.json", dict(fps=ex1, moba=ex2))
    else:
        print(f"note: {s1} is older than the live slate {cur}: only its Log was updated")
    # the frozen Log, per slate, kept apart from the live inputs
    lp = f"{a.site}/data/log/{s1}.json"
    prev = read_json(lp)
    if prev:
        log1, log2 = merge_log(prev["fps"], log1), merge_log(prev["moba"], log2)
    dump(lp, dict(slate=s1, fps=log1, moba=log2))
    idx = sorted(f[:-5] for f in os.listdir(f"{a.site}/data/log") if f.endswith(".json") and f != "index.json")
    dump(f"{a.site}/data/log/index.json", idx)
    if live:
        dump(meta_path, dict(slate=s1, fps_built=fps["built"], moba_built=moba["built"], fps_legs=len(fps["legs"]), moba_legs=len(moba["legs"]),
                             fps_matches=len(fps["matches"]), moba_matches=len(moba["matches"]), slates=idx))
    else:
        meta = read_json(meta_path)
        meta["slates"] = idx
        dump(meta_path, meta)
    for src, name in ((a.fps, "fps"), (a.moba, "moba")):
        dst = f"{a.imports}/{s1}/{name}.xlsx"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.abspath(src) != os.path.abspath(dst):                # the workflow imports straight from data/imports
            shutil.copyfile(src, dst)
    settled = sum(isinstance(r.get("Actual"), (int, float)) for r in log1 + log2)
    print(f"slate {s1}{'' if live else ' (log only)'}: FPS {len(fps['legs'])} legs / {len(fps['matches'])} matches / {len(fps['players'])} players; "
          f"MOBA {len(moba['legs'])} legs / {len(moba['matches'])} matches / {len(moba['players'])} players; log {len(log1)}+{len(log2)}, {settled} settled")


if __name__ == "__main__":
    main()
