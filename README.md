# Esports Model

Website to research and model esports matches: the esports sibling of the Hoops and Gridiron models. A static site (`site/`) that runs the
two slate workbooks' models in the browser, fed by a small importer (`pipeline/`).

* **FPS Player Model — CS2 + Valorant.** Kills and headshots map by map: per-map KPR (shrunk toward overall KPR) × the rounds expected on that map; plus an
  HLTV round-differential layer for CS2 (the "adj" columns).
* **MOBA Player Model — LoL + Dota 2.** Kills from the win/loss effect (players score ~2× the kills in map wins): k_win / k_loss from his map win rate q, a
  P(win) per map from Thunderpick, and a spread that adds the win/loss mixture variance.

Both models are **PAPER**: model side and P(over) are an ordering, not an edge, until the Log has a forward record.

## What's on the site

| Tab | What it does |
|---|---|
| Projections | Every board leg (281 FPS + 18 MOBA on 10-16): line, projection, adj projection, P(over / under / push), model side (paper), Thunderpick's own kill-line median, PickFinder L5/L10/L15/H2H/streak, maps and rounds used, flags. |
| Board | Pick a match: both rosters ranked by projected kills, with the PrizePicks line, P(over), TP book and PF L10 beside it (the workbook's Board tab). |
| Matches | The shaded cells. FPS: Map 1/2/3 and Rounds M1/M2/M3 per match. MOBA: P(win) per map, whether maps 2 and 3 are played, kills environment. Edit any of them and every projection in the match recalculates. |
| Intel | Per match: HLTV recent form, margins, ranks, pistols, map pools and vetoes; HLTV team analytics; Thunderpick total-rounds ladders and player kill ladders. |
| Log | The projections frozen as values when each workbook was built (the forward record). Type the **Actual** after settlement; Result fills itself. |
| Scorecard | Every settled leg: model-side hit rate, every-leg hit rate, MAE for the base, adj, map-free and naive projections, by market, slate and title. |
| Data | The workbooks' integrity checks and issues, live checks on the model in the browser, and the data dictionary (sources, fields, ways each has produced a wrong number). |
| Config | The workbooks' shaded constants (SHRINK_MAPS, dispersions, win/loss ratios, EDGE_MIN, DIFF_WEIGHT, ...). Edits recalculate everything. |
| Methodology | The model, in plain words, with its caveats. |

Your edits (Matches, Config, typed Actuals) are saved on your device only and never change the record.

## Verified against the workbooks

`site/fps.js` and `site/moba.js` are line-for-line ports of each workbook's Calc and Projections tabs. `node site/test/parity.mjs` reproduces every projection, sigma,
P(over), P(under), P(push), side and adj value the workbooks computed (299 legs, 3,519 values, worst difference 6e-9; `site/test/expected.json` holds the workbook's numbers). It runs before every deploy.

## PickFinder capture (receiving end)

PickFinder is behind a login, so the capture runs in **your** logged-in tab, not in the cloud. `docs/pickfinder-capture/README.md` is the brief for that session: the exact files and fields to produce,
the ground rules (you sign in, never route around a block, save after each player), a real worked example, and a prompt to paste.
This repo is the receiving end: `python -m pipeline.pickfinder --slate <date> --crosscheck` validates `data/raw/pickfinder/<slate>/`, converts it, and compares it with the slate already on the site; pushing the files runs the same validation in **Build slate**.
It never talks to PickFinder, and a PickFinder-only build (`--build-out`) is written outside `site/data` because it lacks the Thunderpick and HLTV inputs.

## Results (settling a slate)

After the games, pull the box scores and settle the Log. This runs from any machine with internet, no workbook needed:

```bash
python -m pipeline.results --slate 2026-10-16 --titles CS2,VAL,LOL     # -> data/results/<slate>.json
python -m pipeline.settle  --slate 2026-10-16                           # -> adds Actual/Result/Source/Note to site/data/log/<slate>.json
python -m unittest pipeline.test_results pipeline.test_import && node site/test/parity.mjs
```

| Title | Source | Check |
|---|---|---|
| CS2 | bo3.gg per-map player tables | the match-level table equals the sum over maps; 10 players a map; a team's kills never exceed the other side's deaths (and by at most 10); HS ≤ kills |
| Valorant | vlr.gg match overview | the all-maps tab equals the sum of the maps (the dictionary's identity); the same kill/death and roster checks |
| LoL | gol.gg per-game tables | the team kill header equals the sum of its players, per game |

A leg gets an **Actual** only when its match is finished, the player is in the map tables, and the checks pass. Everything else keeps its reason in the Log's *Settlement* column:
`match not found / not finished` · `void: map not played` (a Bo1 has no map 2) · `no player stats at source` · `did not play` (a stand-in, or a player who missed a map a market needs) · `identity check failed`.
Frozen projections are never touched, an Actual already on a row is never overwritten (a disagreement is reported), and re-running either step changes nothing.

Not used, by design: HLTV and Leaguepedia refuse automated access (Cloudflare / rate limits) and are not routed around, so matches bo3.gg has no player stats for stay unsettled until a second source (an HLTV capture) fills them.

## Each slate

The workbooks are rebuilt from fresh captures (PickFinder, Thunderpick, HLTV) as before. Publishing a slate is one upload:

1. Put the two workbooks in `data/imports/<slate>/` as **`fps.xlsx`** and **`moba.xlsx`** (GitHub: *Add file → Upload files*, both in one commit, or push them).
2. The **Build slate** workflow (`.github/workflows/slate.yml`) runs on that push: it imports the workbooks, runs the import tests and the model-parity test against the workbooks' own numbers,
   commits the refreshed `site/data`, and deploys to Pages. If either test fails nothing is committed or deployed.
3. **Settling.** After the games, upload the same workbooks again with the Log's **Actual** column filled in (same folder, same names). Actuals are added to the frozen Log; the frozen
   projections are never rewritten, and a later upload with no Actual never erases one. The Scorecard picks them up.

Guarantees (tested in `pipeline/test_import.py`): importing twice changes nothing; a re-upload of an **older** slate only updates that slate's Log (the live inputs stay on the newest slate);
a slate with only one of the two workbooks waits until the other arrives.

Run it by hand instead:

```bash
pip install -r pipeline/requirements.txt          # openpyxl
python -m pipeline.import_xlsx --fps FPS_Player_Model.xlsx --moba MOBA_Player_Model.xlsx
python -m unittest pipeline.test_import && node site/test/parity.mjs
```

The importer writes `site/data/{fps,moba,meta}.json`, one frozen Log per slate in `site/data/log/<slate>.json`, refreshes `site/test/expected.json`, and keeps a copy of both
workbooks in `data/imports/<slate>/` (the raw record).

Capture needs a real browser tab (Cloudflare on HLTV, tabs that reload mid-pass), so there is no scheduled capture: the upload is the trigger.

`python -m http.server -d site 8000` to run it locally.

## Layout

```
site/       index.html · app.js · common.js · stats.js · fps.js · moba.js · dictionary.js · style.css · data/ · test/parity.mjs + expected.json
pipeline/   import_xlsx.py · pickfinder.py · results.py · settle.py · sources/{bo3,vlr,gol,http}.py · names.py · test_*.py
data/       imports/<slate>/{fps,moba}.xlsx
.github/    workflows/slate.yml (upload workbooks → import, test, commit, deploy) · deploy.yml (site code changes)   Settings → Pages → Source: GitHub Actions
```
