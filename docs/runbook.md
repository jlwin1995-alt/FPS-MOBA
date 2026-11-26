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

## Seeing which legs fall under which rule

The Projections tab has a **Rules** column right after Market: one badge per registered play rule the leg falls under (H8 agree10, H11 under shortlist, H12 last-10 over, H13 agree20, H14 MOBA lean 20+, H15 headshot legs, H16 headshot overs with last-10 0.8+, H17 strong-lean overs with last-10 0.8+, H18 the daily top-12 shortlist; H10, every leg under, gets no badge because it is every leg, but it is still frozen and scored), filled for OVER and outlined for UNDER, with the rule's definition on hover. The **Rule** filter picks one rule (the count of legs is in the list) or "Any rule". `site/rules.js` mirrors `pipeline/evaluate.py`; `node site/test/parity.mjs` checks that it picks exactly the legs frozen in `data/plays/<slate>.json`, and fails if the two ever drift. The badges follow your edits on the Config and Matches tabs; the frozen lists in `data/plays/` are the record.

## Rolling breakdown on the Scorecard

The Scorecard tab ends its side-calls section with a **Rolling breakdown by rule**: for every registered rule, the hit rate in total and by call side (over / under) and prop type (kills / headshots), over the rule's test slates, the last 10 and last 5 of them, and (descriptive) all slates. It is built by `pipeline.breakdown` logic in `pipeline/evaluate.py` and written into `site/data/evaluation.json` with the rest of the pooled views. `python -m pipeline.evaluate --pooled` rebuilds just the pooled views and the breakdown from the stored per-slate files (faster, no recomputation of each slate; the pooled bootstraps still take a few minutes); `--all` redoes everything.

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

`python -m pipeline.plays --slate <date>` writes `data/plays/<date>.json`: the legs each rule in `pipeline/evaluate.py` (`RULES`) selects from the frozen Log. Commit it before the first start; settling never rewrites it. The Projections tab flags the same legs (`PLAY OVER/UNDER`, filter "rule plays only"). Rule `agree10` (base and round-differential models call the same side, both lean >= 10 pts) was found after seeing 2026-10-16 and 2026-10-17, so only slates from 2026-10-18 on test it (H8). The comparison is every leg on the board. Rule `all_under` (take the under on every leg) was added after 2026-10-19 and is scored forward as H10 (slates from 2026-10-20 on); its past record is descriptive only. Plays are frozen automatically when a live slate is imported (the slate workflow commits `data/plays`), so check `data/plays/<date>.json` holds its rules before the first start. Rule `under_core` (H11: the under where both models lean under, base P(over) < 40%, line outside 20-25, PF L10 0.3-0.7, not Maps 1-3 kills) was declared after 2026-10-21 and freezes in the plays file from 2026-10-22 on; 10-16..19 are where its cut-offs came from, 10-20 and 10-21 are descriptive only (10-20 was not used to set them). Rule `l10_over` (H12: take the OVER where the PrizePicks last-10 hit rate is 0.8 or higher, FPS legs) was declared on 2026-10-25 after reading 2026-10-16..24, so only slates after 2026-10-24 test it; it freezes in the plays file from the 2026-10-25 slate on. Rule `agree20` (H13: both models agree on a side and both lean 20 points or more, scored on the model's side) was declared on 2026-10-27 after reading 2026-10-18..25, so only slates after 2026-10-26 test it; it freezes in the plays file from the 2026-10-27 slate on. Rule `hs_side` (H15: every headshot leg, on the base model's own side) was declared on 2026-10-31 after reading the 1,203 settled HS legs of 2026-10-16..30, so only slates after 2026-10-30 test it; it was added to the 2026-10-31 plays file before the first start with `python -m pipeline.plays --slate <date> --add-rules`, which adds missing rules and touches nothing already frozen. Rule `moba_lean20` (H14: Dota and LoL legs where the model's P(over) is 20 or more points from 50%, scored on the model's side) was declared on 2026-10-28 after reading the 399 settled MOBA legs of 2026-10-16..26, so only slates after 2026-10-27 test it; it is frozen in the plays file's `moba_rules` section (`python -m pipeline.plays --slate <date> --add-moba` adds it to a file frozen before it existed, and touches nothing else).

## Kills-per-map shadow and the PROJ_MODE switch

Every import logs `Proj KPM` / `P(over) KPM` (career kills per map x the maps that count) beside the published projection; `python -m pipeline.kpm --backfill <date>` fills a slate that was imported before this existed. Scored forward as H9. To publish it, `python -m pipeline.patch_workbook` adds a `PROJ_MODE` switch to the workbook; see `docs/workbook-change.md`.

## Known gaps

* Capture is manual (your tab). The PickFinder receiving end is built and waiting: `docs/pickfinder-capture/README.md`.
* Dota is wired to the model but not to results (the OpenDota source is not connected yet; none on the board lately).
* HLTV and Leaguepedia refuse automated access and are not worked around.
* Both models are PAPER. The Scorecard is the first forward record, not proof.


## Player over/under-performer log

`python -m pipeline.players` (a second, no network) reads every settled leg in `site/data/log` and writes `data/players/players.json` (and a slim `site/data/players.json` for the Players tab and the over/under-perf tag on Projections): per player, the matches, the mean error against the line and against the published projection (actual / line - 1, actual / projection - 1, averaged per player-match so legs of one game count once), the share of legs over, kills and headshots apart, and an empirical-Bayes shrunk estimate toward zero. A player is flagged with at least 8 matches and a shrunk error 1.5 standard errors from zero. The same run walks forward through the slates and scores the next slate's legs of the players flagged by the slates before it, which is the test of whether a flag means anything. It is descriptive logging; a play rule would be declared in `pipeline/evaluate.py` first. Re-run it after each settle (it takes about a second).

## H16: headshot overs with last-10 0.8+ (`l10_hs_over`)

Declared 2026-11-14 after a sweep of every combination of H8/H11/H12/H13/H15 over the forward slates 2026-10-18..11-13: the over side of H15 together with H12 (a headshot leg, the base model's side over, PrizePicks last-10 hit rate 0.8 or higher) went 17 of 31 (54.8%, interval 34-74%). That is a multiple-comparison pick on a small sample, so it is registered as a test, not a finding. Only slates after 2026-11-13 count; it was added to the 2026-11-14 plays file with `python -m pipeline.plays --slate 2026-11-14 --add-rules` at 05:21 UTC, before the first start (09:00 UTC). Earlier slates are descriptive only.

## H17: strong-lean overs with last-10 0.8+ (`lean25_l10_over`)

Declared 2026-11-15 after a look at how the lean, the adjusted model and the PrizePicks last-10 line up over the 3,885 settled FPS legs of 2026-10-16..11-14: legs where the base P(over) is 75% or higher, the round-differential model also calls over, and the last-10 hit rate is 0.8 or higher went 14 of 22 (63.6%, interval 42-84%). That is one cell of many on a small, match-clustered sample, so it is registered as a test, not a finding; no other alignment cut (lean + adjusted + last-10 aligned, any side) beat H8 alone. Only slates after 2026-11-14 count; it was added to the 2026-11-15 plays file with `python -m pipeline.plays --slate 2026-11-15 --add-rules` at 05:16 UTC, before the first start (09:00 UTC). Earlier slates are descriptive only.

## Daily lean ranking tally

`python -m pipeline.ranktally` (about a second, no network) scores the daily lean ranking on every settled slate and writes `data/ranking/tally.json`: all FPS legs of a slate sorted by the base model's lean (|P(over) - 0.5|, largest first), scored on the model's own side, for the top 10 / 20 / 30 legs, by lean bucket (0-10, 10-15, 15-20, 20-25, 25+ points) and for the H8 definition (lean 10+ and the adjusted model on the same side), per slate and cumulative. The ranking is fixed by the frozen Log, so earlier slates are scored exactly as they would have been on the day; a slate with open legs is partial and counts only its graded legs. Run it after each settle. It is descriptive: the ranking is not a registered rule.

## H18: the daily top-12 shortlist (`top12`)

Declared 2026-11-18 after reading the settled legs and rule records of 2026-10-16..11-17; only slates after 2026-11-17 test it. Unlike the other rules it is decided over the whole board, not leg by leg: `top12()` in `pipeline/evaluate.py` (mirrored line for line in `site/rules.js`, checked by the parity test) takes the FPS legs that are on H8 (`agree10`) or H16 (`l10_hs_over`), keeps those where every registered per-leg rule that selects the leg takes the same side, the adjusted model is on that side and the base lean is 15+ points, scores each as `lean in points + 100 x sum over its rules of (the rule's frozen forward hit rate on that side and prop type - 50%)`, and takes the best 12 with at most 2 legs per match and 1 per player. The cell rates are frozen in `TOP12_CELLS` (evaluation through 2026-11-17) and are never updated; a change of the score would be a new hypothesis. The list is frozen into the plays file with the other rules (import does it; `python -m pipeline.plays --slate <date> --add-rules` adds it to an earlier file before the first start) with each leg's score and rules, and `top12_record` in `evaluate.py` scores it from the plays file and the Log: the hit rate of the listed side over all settled legs, pushes dropped, 95% interval by matches, against the flex breakeven. First slate frozen: 2026-11-18, at 07:45 UTC, before the first start (09:30 UTC).

## A forfeited map (`forfeits.json`)

A map one team forfeited is listed by the source with a 1-0 score and no player table, but it was not played, so a leg that needs it (any Maps 1-2 leg, if map 2 was the forfeit) has no result. `pipeline.results` only voids a leg when the map is missing from the source's list, so a forfeit is named by hand in `data/imports/<slate>/forfeits.json`: `[{"match": "CS2 · A vs B", "map": 2, "why": "..."}]`. The match record then carries `forfeits` (re-applied after every pull) and every leg that needs that map is `void: map not played` with detail `forfeit`; a leg that needs only the played map still settles. Used once so far: 2026-11-21 INF v BAKS, map 2 (Dust2), confirmed by the user.

## Shadow projections (variant workbooks)

A variant workbook (for example `FPS_Player_Model_<date>_vetosim_SHADOW.xlsx`, same board with a different map assumption) is never imported as the slate. Before the first match starts: copy it to `data/imports/<slate>/shadow_<variant>/`, extract its Log rows with `pipeline.import_xlsx.import_fps` into `data/shadow/<variant>/<slate>.json` (Match, Player, Market, Line, Proj, P(over), P(over) adj, Maps used, Rounds used; `registered: false`) and commit and push, so the commit time is the record. After each settle run `python -m pipeline.shadow` (about a second, no network): it scores live against shadow per slate (Brier of P(over), hit rate on each model's own side, and who was right where the two sides differ) and writes `site/data/shadow.json` for the Shadow tab. A shadow is not a rule: it feeds no plays, no Scorecard and no evaluation; a rule built on it would be registered in `pipeline/evaluate.py` first.
