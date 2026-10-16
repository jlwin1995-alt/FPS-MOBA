# Esports Model

Website to research and model esports matches — the esports sibling of the Hoops and Gridiron models: a static site (`site/`) fed by a small, dependency-free Python pipeline (`pipeline/`).
It covers the four titles on the PrizePicks esports board: **CS2 and Valorant** (FPS) and **LoL and Dota** (MOBA), on player kill / headshot props over Map 1, Maps 1-2 and Maps 1-3.

> **Status.** The site, pipeline, checks and scorecard loop are complete and run end to end. The projection is a clearly labelled **placeholder baseline** (`pipeline/model.py`), and the page runs on a **synthetic sample league** (bannered SAMPLE) until real captures are put in `data/raw`. See *Plugging in the real model and data*.

## What's on the site

| Tab | What it does |
|---|---|
| Projections | Every board leg: line, projection, model side + probability, edge over break-even, sample size, last-15 sparkline, PickFinder hit rates and flags. A shaded **Proj OVR** box lets you type your own projection; the probabilities recalculate and the number is saved on your device. |
| Match Board | Pick a match: Thunderpick moneyline with the vig removed, HLTV round margins (CS2), announced lineups (a flag, not a check), and both teams' legs ranked by how far the projection is from the line. |
| Lines | Each leg's line at PrizePicks, Underdog, Sleeper, Betr, ParlayPlay and DK Pick6; the best line to go over / under and the model's edge at that line. A "Try a line" calculator for any projection, spread and line. |
| Results | Projected → actual for every leg of a settled slate, with the model's side marked hit or miss. |
| Scorecard | Projections are frozen before lock and never rewritten, then scored on next-day box scores against the naive last-10 and the all-games mean; by slate, title, stat and lean strength. |
| Backtest | Walk-forward replay over the series history: each projection uses only earlier games. Scores projection error (the history has no posted lines). |
| Data | The data dictionary (sources, fields, reliability notes), this build's mechanical checks, and coverage by title and app. |
| Config | Break-even % per leg, hide started legs, clear your overrides. |
| Methodology | Exactly what the baseline does and does not model. |

## Run it

```bash
python -m pipeline.build            # no data/raw yet -> builds from a synthetic league and stamps SAMPLE on the site
python -m http.server -d site 8000  # http://localhost:8000
python -m pipeline.selftest && node site/test/parity.mjs   # maths + plumbing; the browser arithmetic must equal the pipeline's
```

## Inputs (`data/raw/`)

All readers are header-driven (case-insensitive, with aliases), so a capture with slightly different headers loads without edits.

| File | One row per | Columns |
|---|---|---|
| `legs.csv` | prop on the board | `leg_id, title, match_id, start, league, tournament, player, team, opp, pos, stat, line, alt, line_ud, line_sl, line_betr, line_pplay, line_dk, hr_l5, hr_l10, hr_l15, hr_season, h2h_hits, h2h_games, avg10, ml_team, ml_opp, fav_over, fav_under` |
| `logs.csv` | player series (a player-page row) | `title, player, team, opp, date, series, m1_k, m2_k, m3_k, m1_hs, m2_hs, m3_hs` and optionally `m12_k, m123_k` (enables the kill-sum identity checks). Blank = map not played. |
| `matches.csv` | match on the board | `match_id, title, start, team_a, team_b, bo, ml_a, ml_b` (decimal odds), `margin_a, margin_b` (HLTV, CS2), `lineup_a, lineup_b` (`\|`-separated) |

`stat` is one of `M1K`, `M12K`, `M123K`, `M1HS`, `M12HS` (`pipeline/config.py`).

## One slate

```bash
scripts/slate.sh 2026-10-16                     # project the board; FREEZES data/log/board_<date>.psv (first build only); rebuild site/data
# next day, once box scores are in:
python -m pipeline.settle --date 2026-10-16 --results data/raw/results_2026-10-16.csv
python -m pipeline.build --date 2026-10-17      # Results and Scorecard pick up data/log/settled_*.psv
```

`results_<date>.csv`: `title, match, player, market, actual, source`. The join key is the match id (which carries the team pair), so a player in several Bo1s a day can't cross-wire; legs without an actual stay unsettled and are listed, never scored as zero.
`settled_<date>.psv` has the dictionary's shape: `title|match|player|market|line|proj_a|proj_b|proj_c|naive|actual|result|registered|source`.

## Plugging in the real model and data

1. **Model.** Replace `project()` in `pipeline/model.py`. It takes a player's newest-first series totals and the title average, and returns `proj`, `sd`, `n`, `naive` and three `variants` (the settled file's `proj_a/b/c`). Nothing else in the pipeline or site has to change. Constants in `pipeline/config.py` (weights, shrinkage, sd floors, lean thresholds) move with it.
2. **Data.** Convert the daily captures (PickFinder board / player pages, HLTV, Thunderpick) to the three CSVs above and drop them in `data/raw/`; the next build stops being SAMPLE. Capture needs a real browser tab (Cloudflare on HLTV, tabs that reload mid-pass), so it is deliberately **not** automated here, and there is no scheduled refresh workflow as in the sport sites: run `scripts/slate.sh`, commit `data/` and `site/data/`, push.
3. **History.** Settled files from the earlier record (`settled_YYYY-MM-DD.psv`, 2,511 legs over 13 slates, 10-03 to 10-15) can be copied straight into `data/log/` and the Scorecard fills in.

## Publish

`.github/workflows/deploy.yml` runs the offline tests and publishes `site/` to GitHub Pages on every push to `main` that touches `site/**` or `pipeline/**` (enable Pages → Source: GitHub Actions in the repo settings).

## Layout

```
pipeline/   config · store · prob · model · sample_data · build · scorecard · backtest · settle · selftest
site/       index.html · app.js · common.js · model.js · dictionary.js · style.css · data/*.json · test/parity.mjs
data/       raw/ (captures)  log/ (frozen boards + settled files)  sample/ (generated, ignored)
```
