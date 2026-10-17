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
python -m pipeline.results --slate <date> --titles CS2,VAL,LOL
python -m pipeline.settle  --slate <date>
git add data/results site/data/log && git commit -m "Settle <date>" && git push
```

The push to `main` deploys (it touches `site/**`). Run it again later for matches still playing; settled values never change and re-runs are safe.
Every unsettled leg carries its reason in the Log's *Settlement* column. The usual one is `no player stats at source` (bo3.gg has the maps but no player tables): those need HLTV match-page totals from your tab.
Or type Actuals on the Log tab (kept in your browser only).

Matches left at `no player stats at source` can be filled from your own HLTV tab: run `docs/hltv-capture/capture.js` on each finished match page, save the JSON under `data/imports/<date>/hltv/`, then `python -m pipeline.hltv --slate <date>` and `pipeline.settle` again (see `docs/hltv-capture/README.md`). Re-run `pipeline.hltv` after any fresh results pull.

## Evaluate (after each settle)

```
python -m pipeline.evaluate --slate <date>     # -> data/evaluation/<date>.json and site/data/evaluation.json (Scorecard > Evaluation)
```

Needs `node` (it re-runs the model with the maps and rounds actually played). Hypotheses H1-H6 are pre-declared in `pipeline/evaluate.py`; 2026-10-16 is exploratory (they came from it), every later slate is confirmatory. Commit the two outputs with the settle commit. Do not change a hypothesis after seeing a confirmatory slate.

## Known gaps

* Capture is manual (your tab). The PickFinder receiving end is built and waiting: `docs/pickfinder-capture/README.md`.
* Dota is wired to the model but not to results (the OpenDota source is not connected yet; none on the board lately).
* HLTV and Leaguepedia refuse automated access and are not worked around.
* Both models are PAPER. The Scorecard is the first forward record, not proof.
