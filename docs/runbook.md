# Runbook: building and settling a slate

## Build (the morning of the slate)

1. Capture and build the two workbooks as usual (PickFinder, Thunderpick, HLTV in your tab).
2. **Check the Config tab's `SLATE_DATE` in both workbooks is today.** The upload is refused if it isn't.
3. Upload them as **`data/imports/<date>/fps.xlsx`** and **`data/imports/<date>/moba.xlsx`**, both in one commit, to `main` (GitHub: *Add file → Upload files*).
4. **Build slate** runs (Actions tab). It imports, runs 39 offline tests and the model-parity test, commits the data, deploys. The run's summary shows the import line:
   `slate <date>: FPS 281 legs ... MOBA 18 legs ... log 281+18, 0 settled`.
5. Open the site: the header should read `<date> slate`, and the Log tab's slate list should end with today.

If a run goes red, nothing was committed or deployed. The step that failed says why:

| Message | Meaning |
|---|---|
| `the folder is X but the workbooks say Y` | the wrong day's workbook, or `SLATE_DATE` not updated |
| `the two workbooks are for different slates` | one of the two is from another day |
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

## Known gaps

* Capture is manual (your tab). The PickFinder receiving end is built and waiting: `docs/pickfinder-capture/README.md`.
* Dota is wired to the model but not to results (the OpenDota source is not connected yet; none on the board lately).
* HLTV and Leaguepedia refuse automated access and are not worked around.
* Both models are PAPER. The Scorecard is the first forward record, not proof.
