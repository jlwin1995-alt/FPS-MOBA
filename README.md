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

## Each slate

The workbooks are rebuilt from fresh captures (PickFinder, Thunderpick, HLTV) as before. To publish a slate:

```bash
pip install -r pipeline/requirements.txt          # openpyxl
python -m pipeline.import_xlsx --fps FPS_Player_Model.xlsx --moba MOBA_Player_Model.xlsx
node site/test/parity.mjs                         # the port must still match the workbooks
git add -A && git commit -m "Slate 2026-10-17" && git push
```

The importer writes `site/data/{fps,moba,meta}.json`, one frozen Log per slate in `site/data/log/<slate>.json`, refreshes `site/test/expected.json`, and keeps a copy of both
workbooks in `data/imports/<slate>/` (the raw record; the dictionary flags raw captures as at risk). After settlement, re-import a workbook whose Log has **Actual** filled in
and the Scorecard picks it up permanently.

Capture needs a real browser tab (Cloudflare on HLTV, tabs that reload mid-pass), so there is no scheduled refresh.

`python -m http.server -d site 8000` to run it locally.

## Layout

```
site/       index.html · app.js · common.js · stats.js · fps.js · moba.js · dictionary.js · style.css · data/ · test/parity.mjs + expected.json
pipeline/   import_xlsx.py
data/       imports/<slate>/{fps,moba}.xlsx
.github/    workflows/deploy.yml  (parity test, then GitHub Pages: Settings → Pages → Source: GitHub Actions)
```
