# PickFinder capture: what to produce

This is the brief for the session that does the capture. It runs on **your** computer, in **your** logged-in PickFinder tab (Claude Desktop's browser pane, or Claude in Chrome).
The repo then validates what it produced. Nothing in the repo talks to PickFinder.

## Ground rules

* **You sign in, not Claude.** Never ask for, read out, store or commit a password, cookie, token or API key. If a page needs a login or shows a challenge (Cloudflare, captcha), stop and tell the user.
* **Never route around a block.** A 401/403, a challenge page or a rate-limit message means stop and report. Do not call PickFinder's API directly with copied tokens, change headers, or retry in a loop.
* **Read the pages as a person would**: open the board, open each player's page, read what is shown. One player at a time with a short pause; this is about 150 page reads, not a crawl.
* **One pass, before the first lock.** The record must be what PickFinder showed before play started. `captured_utc` is when the capture finished.
* **Save after every player and resume.** A tab has reloaded or frozen mid-pass before. Write each `players/<pid>.json` as soon as it is read; on restart, skip the files that already exist.
* **Stop when the page changes shape.** If a table is missing, a column moved or a number does not parse, write nothing for that player and report it. A wrong number that looks right is worse than a gap.

## Where it goes

```
data/raw/pickfinder/<slate>/          # <slate> is the date, e.g. 2026-10-16
  capture.json                        # one small file about the capture
  board.json                          # every PrizePicks leg on the board
  players/<pid>.json                  # one file per player, <pid> is PickFinder's player id (the last part of the page URL)
```

`docs/pickfinder-capture/example/` holds a real, valid example (3 matches: CS2, Valorant, LoL). Copy its shape.

## capture.json

```json
{ "schema": 1, "slate": "2026-10-16", "captured_utc": "2026-10-16T06:47:00Z", "source": "pickfinder.app", "tool": "claude-in-chrome",
  "expected_legs": 299, "notes": [] }
```

`expected_legs` is the number of legs **the board page itself says it has** (its own count, not a count of what you saved). The check compares it with `board.json`; this is what catches a page cap that reset mid-pass.

## board.json

`{ "legs": [ ... ] }`, one object per prop (about 300 a day). Titles: `CS2`, `VAL`, `LOL`, `DOTA`.

| Field | Meaning |
|---|---|
| `title` | `CS2` / `VAL` / `LOL` / `DOTA` |
| `match` | **`<TITLE> · <A tag> vs <B tag>`**, e.g. `CS2 · EF vs BCA`. The two tags are the two teams, in the board's order. This is the join key: it carries the team pair, so a player in several Bo1s a day cannot be mixed up |
| `player`, `pid`, `team`, `opp` | player name as shown, PickFinder player id, his team tag, the opposing tag (`team` and `opp` must be the two sides of `match`) |
| `market` | exactly one of `Map 1 Kills`, `Maps 1-2 Kills`, `Maps 1-3 Kills`, `Map 1 HS`, `Maps 1-2 HS` |
| `line` | the PrizePicks line (a number) |
| `alt` | true for an alternate line |
| `start` | start time, ISO 8601 UTC |
| `league`, `tournament`, `pos` | as shown (may be null) |
| `hit` | `avg10` (average of the last 10), `l5`, `l10`, `l15` (hit rates as **fractions**: 0.2, not 20%), `season`, `h2h` (the text as shown, e.g. `67%/2/3`, or `-`), `streak` (a number, negative for under streaks) |
| optional | `apps` (other apps' lines), `ml` (team and opponent moneyline, book), `popularity` (favourite counts over/under), `def_rank`, `consensus` |

The same player can appear in several matches in one day, and a leg is `(match, player, market)`. Never merge them.

## players/\<pid\>.json

Common: `pid`, `player`, `title`, `team`, `matchup` (as PickFinder shows it, e.g. `100T vs SNG`), `url`, `captured_utc`.

**CS2 and Valorant** (Player Stats panel, Map Stats; the *Per Round* toggle for rates):

```json
{ "overall":   { "maps": 30, "kills_map": 15.37, "kpr": 0.73, "hs": 0.315, "hs_round": 0.23, "kd": 1.31, "rating": 1.18 },
  "map_stats": [ { "map": "Nuke", "n": 7, "kills": 16.4, "kpr": 0.67, "hs": 0.478, "kd": 1.06 } ],
  "map_picks": { "matchup": "100T vs SNG", "maps": [ { "map": "Dust2", "pct": 30 } ] } }
```

* `hs` is a fraction (0.315). Valorant has no HS % on PickFinder: leave `hs`, `hs_round` null. Valorant also has no per-map KPR: leave each map's `kpr` null (the model converts with kills per map ÷ average map length).
* `map_picks` is the Maps panel's Map Picks likelihood for the matchup (not the veto). CS2 only; omit when the panel is absent.
* **Do not "fix" numbers.** Copy what the page shows. The checks below are how a misread gets caught.

**LoL and Dota** (Player Stats, plus the 15-series game log):

```json
{ "role": "jun",
  "overall": { "maps": 30, "win_rate": 0.6, "k": 3.0, "d": 2.4, "a": 8.1, "kd": 1.2 },
  "gamelog": [ { "date": "2026-10-15", "opp": "KC", "m1k": 4, "m2k": 1, "m3k": 7, "m12k": 5, "m123k": 12 } ] }
```

* `gamelog` is newest first, 15 series at most. `date` is ISO (the page shows month/day: add the year). A map that was not played is `null`, not 0. `m12k` / `m123k` are the page's own combined columns.

## What the repo checks

`python -m pipeline.pickfinder --slate <slate>` (run automatically when you push). **Errors stop the slate; warnings are reported.**

| Check | Why |
|---|---|
| `expected_legs` equals the legs in `board.json` | the 20-row page cap has reset itself mid-pass |
| every leg's player has a `players/<pid>.json` | "board players with no stats page read" |
| per-map `n` sums to `overall.maps`, and the n-weighted `kills` equals `overall.kills_map` (±0.06) | the workbook's own identity: a misread table fails it |
| gamelog: `m1k + m2k = m12k` and `m12k + m3k = m123k` on every row | free check on every row; has passed every time |
| no duplicate `(match, player, market)` | one player, several matches a day |
| `team`/`opp` are the two sides of `match`; title and market are known | the join key |
| hit rates in [0, 1]; warning if not an exact k/5, k/10, k/15 | a shifted column |
| warnings: thin sample (<15 maps), gamelog rows older than 120 days, a stats page with no leg, a player's team differs from the leg's | the cases the data dictionary lists |

## After the capture

```bash
python -m pipeline.pickfinder --slate 2026-10-16 --crosscheck    # validates, and compares with the slate already on the site if there is one
git add data/raw/pickfinder/2026-10-16 && git commit -m "PickFinder capture 2026-10-16" && git push
```

Pushing to `main` runs the validation in GitHub (**Build slate**) and fails on any error. What PickFinder does not carry (Thunderpick win probabilities, round ladders, kill ladders; HLTV round margins) is a separate capture and is not in these files.
`--build-out DIR` writes a PickFinder-only `fps.json`/`moba.json` for inspection: rounds fall back to the Config defaults, there is no round-differential layer, and MOBA has no win probability, so it is **not** the model's full input. It is never written into `site/data`.

## A prompt to paste into the capture session

> Follow `docs/pickfinder-capture/README.md`. I am signed in to PickFinder in this browser. Capture today's board (CS2, Valorant, LoL, Dota: PrizePicks legs) and every board player's stats page into `data/raw/pickfinder/<today>/`, saving each player file as soon as it is read and skipping files that already exist. Use the board's own leg count for `expected_legs`. Do not ask me for credentials and do not work around any login, challenge or block: stop and tell me. When done, run `python -m pipeline.pickfinder --slate <today> --crosscheck`, fix nothing by guessing, and tell me every error and warning.
