# Runbook: building and settling a slate

## Build (the morning of the slate)

1. Capture and build the two workbooks as usual (PickFinder, Thunderpick, HLTV in your tab).
2. **Check the Config tab's `SLATE_DATE` in both workbooks is today.** The upload is refused if it isn't.
   **Check the workbooks hold calculated results.** A workbook saved by a script has formulas but no results, and the importer refuses it (see the table). From a cloud session or any machine with LibreOffice:
   `python -m pipeline.recalc data/imports/<date>/fps.xlsx data/imports/<date>/moba.xlsx` (keep the untouched originals in `data/imports/<date>/original/`). GitHub's runners are not relied on to have LibreOffice, so recalculate before uploading.
3. Upload them as **`data/imports/<date>/fps.xlsx`** and **`data/imports/<date>/moba.xlsx`**, both in one commit, to `main` (GitHub: *Add file → Upload files*).
4. **Build slate** runs (Actions tab). It imports, runs the offline tests and the model-parity test, commits the data, deploys. The run's summary shows the import line:
   `slate <date>: FPS 281 legs ... MOBA 18 legs ... log 281+18, 0 settled`.
5. Open the site: the header should read `<date> slate`, and the Log tab's slate list should end with today.

If a run goes red, nothing was committed or deployed. The step that failed says why:

| Message | Meaning |
|---|---|
| `the folder is X but the workbooks say Y` | the wrong day's workbook, or `SLATE_DATE` not updated |
| `the two workbooks are for different slates` | one of the two is from another day |
| `the FPS workbook has no stored results` | saved without being calculated (formulas, no results); recalculate it as in step 2 and upload again |
| `needs both fps.xlsx and moba.xlsx` (a notice, not a failure) | the second file has not arrived yet; the run skips until it does |
| `MISMATCH ...` from the parity test | the model port no longer reproduces the workbook; do not publish, send me the lines |

## Settle (after the games, usually next morning)

From any machine with internet (works in a cloud session; no workbook needed, it reads that slate's own workbooks):

```bash
python -m pipeline.results --slate <date> --titles CS2,VAL,LOL,DOTA
python -m pipeline.settle  --slate <date>
git add data/results site/data/log && git commit -m "Settle <date>" && git push
```

Dota comes from OpenDota (`pipeline/sources/opendota.py`): a series is read only once one team has the wins its series type needs, and each player's kills are checked against his own recent-match list. A LoL team gol.gg names differently from the board (for example `Los Grandes` for `LOS`) goes in `data/imports/<date>/lol_aliases.json` as `{"gol.gg name": "board name"}`. A handle the board and OpenDota spell differently (for example `miCKe` / `m1CKe`) goes in `data/imports/<date>/dota_aliases.json` as `{"board name": "OpenDota name"}`; a player who is on no roster is reported as `did not play`, never guessed.

The push to `main` deploys (it touches `site/**`). Run it again later for matches still playing; settled values never change and re-runs are safe.
Every unsettled leg carries its reason in the Log's *Settlement* column. The usual one is `no player stats at source` (bo3.gg has the maps but no player tables): those need HLTV match-page totals from your tab.
Or type Actuals on the Log tab (kept in your browser only).

Matches left at `no player stats at source` can be filled from your own HLTV tab: run `docs/hltv-capture/capture.js` on each map's HLTV map-stats page, save the JSON under `data/imports/<date>/hltv/`, then `python -m pipeline.hltv --slate <date>` and `pipeline.settle` again (see `docs/hltv-capture/README.md`). Re-run `pipeline.hltv` after any fresh results pull.

## Odds (market check, optional)

After the board is built, near the first start time: run the **Odds** workflow with the slate date (needs the `ODDSPAPI_KEY` secret). It saves the raw bookmaker odds as an artifact; commit it under `data/raw/odds/<slate>/` and run `python -m pipeline.odds build --slate <slate>`. The Matches tab then shows a *Market check*: series win probability, chance of a third map and the per-map rounds line next to the model's inputs. OddsPapi lists player kill/headshot markets but no book had priced them a day out (2026-10-17); they appear in the table if one does.

## Evaluate (after each settle)

```
python -m pipeline.evaluate --slate <date>     # -> data/evaluation/<date>.json and site/data/evaluation.json (Scorecard > Evaluation)
```

Needs `node` (it re-runs the model with the maps and rounds actually played). Hypotheses H1-H6 are pre-declared in `pipeline/evaluate.py`; 2026-10-16 is exploratory (they came from it), every later slate is confirmatory. Commit the two outputs with the settle commit. Do not change a hypothesis after seeing a confirmatory slate. H7 (side calls clear the flex breakeven) was written after 2026-10-17, so only slates after it count toward it; its payouts live in `PAYOUTS` in `pipeline/evaluate.py` and should be checked against the app.

## Play rules (frozen before the games)

`python -m pipeline.plays --slate <date>` writes `data/plays/<date>.json`: the legs each rule in `pipeline/evaluate.py` (`RULES`) selects from the frozen Log. Commit it before the first start; settling never rewrites it. The Projections tab flags the same legs (`PLAY OVER/UNDER`, filter "rule plays only"). Rule `agree10` (base and round-differential models call the same side, both lean >= 10 pts) was found after seeing 2026-10-16 and 2026-10-17, so only slates from 2026-10-18 on test it (H8). The comparison is every leg on the board. Rule `all_under` (take the under on every leg) was added after 2026-10-19 and is scored forward as H10 (slates from 2026-10-20 on); its past record is descriptive only. Plays are frozen automatically when a live slate is imported (the slate workflow commits `data/plays`), so check `data/plays/<date>.json` holds its rules before the first start. Rule `under_core` (H11: the under where both models lean under, base P(over) < 40%, line outside 20-25, PF L10 0.3-0.7, not Maps 1-3 kills) was declared after 2026-10-21 and freezes in the plays file from 2026-10-22 on; 10-16..19 are where its cut-offs came from, 10-20 and 10-21 are descriptive only (10-20 was not used to set them). Rule `l10_over` (H12: take the OVER where the PrizePicks last-10 hit rate is 0.8 or higher, FPS legs) was declared on 2026-10-25 after reading 2026-10-16..24, so only slates after 2026-10-24 test it; it freezes in the plays file from the 2026-10-25 slate on. Rule `agree20` (H13: both models agree on a side and both lean 20 points or more, scored on the model's side) was declared on 2026-10-27 after reading 2026-10-18..25, so only slates after 2026-10-26 test it; it freezes in the plays file from the 2026-10-27 slate on. Rule `moba_lean20` (H14: Dota and LoL legs where the model's P(over) is 20 or more points from 50%, scored on the model's side) was declared on 2026-10-28 after reading the 399 settled MOBA legs of 2026-10-16..26, so only slates after 2026-10-27 test it; it is frozen in the plays file's `moba_rules` section (`python -m pipeline.plays --slate <date> --add-moba` adds it to a file frozen before it existed, and touches nothing else).

## Kills-per-map shadow and the PROJ_MODE switch

Every import logs `Proj KPM` / `P(over) KPM` (career kills per map x the maps that count) beside the published projection; `python -m pipeline.kpm --backfill <date>` fills a slate that was imported before this existed. Scored forward as H9. To publish it, `python -m pipeline.patch_workbook` adds a `PROJ_MODE` switch to the workbook; see `docs/workbook-change.md`.

## Known gaps

* Capture is manual (your tab). The PickFinder receiving end is built and waiting: `docs/pickfinder-capture/README.md`.
* Dota is wired to the model but not to results (the OpenDota source is not connected yet; none on the board lately).
* HLTV and Leaguepedia refuse automated access and are not worked around.
* Both models are PAPER. The Scorecard is the first forward record, not proof.
