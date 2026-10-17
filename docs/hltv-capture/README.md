# HLTV capture for matches bo3.gg has no player stats for

The settle pull leaves a CS2 match as `no player stats at source` when bo3.gg has the maps but not the tables. This fills those matches from HLTV pages **you** open in your own browser. Nothing in the repo contacts HLTV.

1. Open the finished match's HLTV page (the one with the map-stats links).
2. Open the console, paste `capture.js`, press Enter. It prints one line of JSON (or `CAPTURE STOPPED: <reason>`; stop there, do not edit numbers by hand).
3. Send the JSON to the chat (one per match), or save it as `data/imports/<slate>/hltv/<anything>.json`.
4. `python -m pipeline.hltv --slate <slate>` validates, merges into `data/results/<slate>.json`, then `python -m pipeline.settle --slate <slate>`.

What is checked: bo3.gg numbers are never replaced; a map filled from HLTV must have 10 players (5 per team), kills within 0-10 of the other side's deaths, headshots <= kills, and agree with bo3.gg on map and score. A failure leaves the leg unsettled with the reason.

Run `pipeline.hltv` again after any fresh `pipeline.results` pull (a pull rewrites the results file). The selectors in `capture.js` were written from HLTV's page structure as I know it and have **not** been run against a live page from here: expect to adjust them on the first match.
