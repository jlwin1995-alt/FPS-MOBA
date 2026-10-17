# HLTV capture for matches bo3.gg has no player stats for

The settle pull leaves a CS2 match as `no player stats at source` when bo3.gg has the maps but not the tables. This fills those matches from HLTV pages **you** open in your own browser. Nothing in the repo contacts HLTV.

1. Open the finished match's HLTV page, then each map's **Detailed stats** page (one tab per map; the page must load normally in your browser).
2. On each map-stats page open the console, paste `capture.js`, press Enter. It prints one line of JSON for that map (or `CAPTURE STOPPED: <reason>`; stop there, do not edit numbers by hand).
3. Send the lines to the chat (any order, one or more per message), or save each as `data/imports/<slate>/hltv/<anything>.json`.
4. `python -m pipeline.hltv --slate <slate>` joins the maps of each match (numbered from bo3.gg's map list, else by HLTV map-stats id), validates, merges into `data/results/<slate>.json`; then `python -m pipeline.settle --slate <slate>`.

The script does not fetch other pages: HLTV returns 403 to background requests from a page, and that is not worked around. Whole-match captures (`maps: [...]`) are still accepted.

What is checked: bo3.gg numbers are never replaced; a map filled from HLTV must have 10 players (5 per team), kills within 0-10 of the other side's deaths, headshots <= kills, and agree with bo3.gg on map and score. A failure leaves the leg unsettled with the reason.

Run `pipeline.hltv` again after any fresh `pipeline.results` pull (a pull rewrites the results file). The selectors in `capture.js` come from memory of HLTV's map-stats page and have **not** been checked against a live page: if it stops, it prints the classes of the tables it did find so they can be fixed.
